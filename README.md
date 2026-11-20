# gta6-trophy-rarity-forecast

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/eskrimkonelo/gta6-trophy-rarity-forecast/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/eskrimkonelo/gta6-trophy-rarity-forecast/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

Program Python stdlib-only yang memprediksi earn rate 55 trofi GTA VI (PS5) di Exophase pada 26 Nov 2026, lima kuantil per trofi. Modelnya memfit tren logit terhadap log-waktu sejak rilis dengan weighted least squares berbobot recency, lalu men-shrink slope tiap trofi ke arah slope populasi — setelah plateau basi dari Exophase (read berurutan yang ratenya tidak berubah karena halamannya belum di-refresh) dibuang dulu lewat dedup. Dinilai dengan mean pinball loss pada skala logit atas semua trofi dan kuantil; program berjalan deterministik, tanpa network, dan selesai jauh di bawah batas 8 detik.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=s3aw5cdd&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
