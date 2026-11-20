"""Peramal rarity trofi GTA VI (make.fun gta6-trophy-rarity-forecast-01).

Model: untuk tiap trofi, logit dari earn rate dimodelkan sebagai tren linier
terhadap log-waktu sejak launch, difit dengan weighted least squares
(bobot recency), lalu slope-nya di-shrink ke arah slope populasi
(hierarchical shrinkage). Spread kuantil menggabungkan random-walk
starter dengan noise residual fit.

Python 3.13, standard library saja, tanpa network, deterministik.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# -P pada grader membuat direktori file ini tidak ada di sys.path; kembalikan
# agar import modul sampingan tetap bisa (program ini sendiri tidak butuh).
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LAUNCH = datetime(2026, 11, 19, 0, 0, 0, tzinfo=timezone.utc)

# Level kuantil yang dinilai, dan kuantil normal baku di tiap level.
Z_BY_LEVEL = {0.05: -1.645, 0.25: -0.674, 0.5: 0.0, 0.75: 0.674, 0.95: 1.645}
DEFAULT_LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]

# Konstanta model.
K_SHRINK = 5.0          # kekuatan shrinkage slope ke populasi
RW_SIGMA = 0.5          # spread random-walk starter, per akar hari
SIGMA_FIT_CAP = 1.0     # batas atas simpangan residual fit
FALLBACK_RATE = 1.0     # rate (%) bila trofi tak pernah terbaca

RATE_LO = 0.01
RATE_HI = 99.99


def parse_time(text):
    """ISO 8601 UTC (dengan 'Z' atau offset) -> datetime sadar zona."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def hours_since_launch(moment):
    return (moment - LAUNCH).total_seconds() / 3600.0


def clamp_rate(rate):
    return min(RATE_HI, max(RATE_LO, rate))


def logit_of(rate):
    r = clamp_rate(rate)
    return math.log(r / (100.0 - r))


def rate_of(y):
    """Sigmoid balik: logit -> persen, di-clamp ke [0.01, 99.99]."""
    if y >= 0:
        p = 1.0 / (1.0 + math.exp(-y))
    else:
        e = math.exp(y)
        p = e / (1.0 + e)
    return clamp_rate(100.0 * p)


def round4(value):
    """Bulatkan ke 4 desimal, half-up; bilangan bulat ditulis sebagai int."""
    scaled = value * 10000.0
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    out = whole / 10000.0
    return int(out) if out.is_integer() else out


def dedup_series(points):
    """Buang read berurutan yang ratenya identik dengan read sebelumnya.

    `points` adalah daftar (t_jam, rate) terurut waktu. Plateau basi dari
    Exophase yang tidak refresh tiap read dihapus; yang disimpan hanya
    kemunculan pertama tiap nilai distinct yang berurutan.
    """
    kept = []
    for point in points:
        if not kept or point[1] != kept[-1][1]:
            kept.append(point)
    return kept


def weighted_line(xs, ys, ws):
    """Least squares berbobot untuk y = a + b*x. Kembalikan (a, b) atau None."""
    sw = sum(ws)
    if sw <= 0.0:
        return None
    sx = sum(w * x for x, w in zip(xs, ws))
    sy = sum(w * y for y, w in zip(ys, ws))
    sxx = sum(w * x * x for x, w in zip(xs, ws))
    sxy = sum(w * x * y for x, y, w in zip(xs, ys, ws))
    denom = sw * sxx - sx * sx
    if denom == 0.0:
        return None
    # Tanpa variansi-x yang berarti (semua read menumpuk di satu waktu),
    # slope hasil bagi jadi tak stabil: perlakukan sebagai fit tak valid
    # supaya trofi itu jatuh ke fallback persistence, bukan ekstrapolasi liar.
    scale = sw * sxx
    if scale > 0.0 and denom <= 1e-9 * scale:
        return None
    b = (sw * sxy - sx * sy) / denom
    a = (sy - b * sx) / sw
    return a, b


def residual_sigma(xs, ys, a, b):
    """Simpangan baku residual fit (pembagi n, bukan n-2)."""
    n = len(xs)
    if n == 0:
        return 0.0
    total = 0.0
    for x, y in zip(xs, ys):
        diff = y - (a + b * x)
        total += diff * diff
    return math.sqrt(total / n)


def starter_quantiles(median_rate, horizon_days, levels):
    """Kuantil persistence: median = rate terakhir, spread random-walk."""
    sigma = RW_SIGMA * math.sqrt(horizon_days)
    y_med = logit_of(median_rate)
    return quantiles_from(y_med, sigma, levels)


def quantiles_from(y_med, sigma, levels):
    """Kuantil dari median logit + z*sigma, dibulatkan, dijamin tak menurun."""
    out = []
    prev = None
    for level in levels:
        z = Z_BY_LEVEL.get(level, 0.0)
        q = round4(rate_of(y_med + z * sigma))
        if prev is not None and q < prev:
            q = prev
        out.append(q)
        prev = q
    return out


def forecast_case(case):
    levels = list(case.get("levels") or DEFAULT_LEVELS)
    horizon_days = float(case["horizon_minutes"]) / 1440.0
    target = parse_time(case["target"])
    x_target = math.log(max(1.0 + hours_since_launch(target), 0.001))

    # Urutan case dipertahankan di sini: rates[i] pada tiap read milik
    # trophies[i] dalam urutan itu, jadi pengurutan dilakukan pada baris
    # hasil di akhir, bukan sebelum deret dikumpulkan.
    trophies = list(case["trophies"])
    history = case.get("history") or []

    # --- Kumpulkan deret (t_jam, rate) per trofi, lalu dedup plateau. ---
    series = []
    for idx in range(len(trophies)):
        points = []
        for read in history:
            rates = read.get("rates") or []
            if idx >= len(rates):
                continue
            rate = rates[idx]
            if rate is None:
                continue
            points.append((hours_since_launch(parse_time(read["at"])), float(rate)))
        series.append(dedup_series(points))

    # --- Fit tren per trofi (pass pertama: kumpulkan slope populasi). ---
    fits = []  # per trofi: (a, b, n, sigma_fit) atau None
    slopes = []
    for points in series:
        if len(points) < 3:
            fits.append(None)
            continue
        xs = [math.log(max(1.0 + t, 0.001)) for t, _ in points]
        ys = [logit_of(r) for _, r in points]
        ws = [1.0 + t / 24.0 for t, _ in points]
        fit = weighted_line(xs, ys, ws)
        if fit is None:
            fits.append(None)
            continue
        a, b = fit
        sigma_fit = min(residual_sigma(xs, ys, a, b), SIGMA_FIT_CAP)
        fits.append((a, b, len(points), sigma_fit))
        slopes.append(b)

    b_pop = sum(slopes) / len(slopes) if slopes else 0.0

    # --- Forecast per trofi. ---
    rows = []
    for idx, trophy in enumerate(trophies):
        points = series[idx]
        fit = fits[idx]
        if fit is None:
            # Fallback persistence: median = rate terakhir yang terbaca,
            # atau 1.0% bila trofi tak pernah terbaca / history kosong.
            last_rate = points[-1][1] if points else FALLBACK_RATE
            rows.append({"id": trophy["id"],
                         "q": starter_quantiles(last_rate, horizon_days, levels)})
            continue
        a, b, n, sigma_fit = fit
        # Hierarchical shrinkage pada slope; intercept tetap milik trofi.
        b_shrunk = (n * b + K_SHRINK * b_pop) / (n + K_SHRINK)
        y_med = a + b_shrunk * x_target
        sigma = math.sqrt((RW_SIGMA ** 2) * horizon_days + sigma_fit ** 2)
        rows.append({"id": trophy["id"],
                     "q": quantiles_from(y_med, sigma, levels)})
    return {"trophies": sorted(rows, key=lambda r: r["id"])}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case)
        text = json.dumps(forecast, separators=(",", ":")) + "\n"
        (OUTPUT_DIR / (path.stem + ".out")).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
