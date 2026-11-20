# Method — gta6-trophy-rarity-forecast

## Masalah

Memprediksi, untuk tiap dari 55 trofi GTA VI di PlayStation 5 (1 platinum,
2 gold, 6 silver, 46 bronze), earn rate-nya di halaman Exophase
(`exophase.com/game/grand-theft-auto-vi-psn/trophies/`) pada
**2026-11-26T00:00:00Z** — persen pemain yang dilacak Exophase dan sudah
mendapatkan trofi itu. Keluaran per trofi adalah lima kuantil
(0.05, 0.25, 0.5, 0.75, 0.95) dari earn rate tersebut, dalam persen.

Skornya adalah **mean pinball loss pada skala logit** atas semua trofi dan
kuantil: tiap item dikenai `2 * max(tau * d, (tau - 1) * d)` dengan
`d = logit(y) - logit(q)`, `y` rate jawaban, `q` kuantil yang ditulis,
`logit(x) = ln(p / (1 - p))`, `p = x / 100`, dan `x` di-clamp ke
0.01–99.99. Skala logit membuat selisih 1% → 2% semahal selisih
33% → 50%, jadi trofi langka sama pentingnya dengan trofi umum; kuantil
yang terlalu sempit membayar setiap trofi yang jatuh di luarnya, yang
terlalu lebar membayar di setiap trofi.

Horizon final adalah **6.510 menit (~4,5 hari)** setelah checkpoint
(2026-11-21T11:30:00Z). Practice hanya 90 menit — jauh lebih pendek,
dan seperti dijelaskan di bawah, practice tidak menguji jalur utama model
ini sama sekali.

## Data

Satu-satunya masukan adalah case yang diberikan grader: daftar trofi dan
`history`, yaitu setiap pembacaan halaman Exophase yang valid sebelum
checkpoint, tertua dulu. Tiap read berisi waktu, jumlah pemain yang
dilacak, dan satu earn rate per trofi. Program tidak punya network dan
tidak membaca Exophase sendiri; ia hanya memprediksi dari history itu.

Dua sifat data yang menentukan model:

1. **Exophase me-refresh hitungannya menurut jadwalnya sendiri, bukan
   tiap pemain mendapat trofi.** Pada malam rilis, halaman tidak berubah
   sama sekali dari 2026-11-18T23:48Z sampai read 2026-11-19T04:00Z
   (638 pemain, semua rate sama), lalu refresh di read 04:30Z (3.868
   pemain, hampir semua rate turun). Jadi read berurutan yang identik
   bukan berarti tidak ada yang mendapat trofi — itu plateau basi dari
   halaman yang belum di-refresh. History yang terlihat datar bisa
   menyembunyikan pertumbuhan nyata di antaranya.
2. **Practice tidak mewakili final.** Kedua case practice (checkpoint
   03:00 dan 03:30 UTC 19 Nov, target 90 menit kemudian) seluruh
   history-nya adalah plateau peluncuran yang belum pernah refresh, dan
   jawabannya adalah halaman sesudah refresh pertama. Jadi di practice,
   model tren apa pun tidak punya sinyal untuk difit — history-nya
   benar-benar flat — dan yang diuji hanyalah: program membaca case,
   menulis forecast valid, dan spread-nya menampung satu refresh yang
   belum pernah terlihat. Final berbeda: history-nya ~36 jam dengan
   banyak refresh, dan horizonnya 4,5 hari, bukan 90 menit. Model yang
   hanya mengandalkan practice akan salah menilai dirinya sendiri.

## Model

Per trofi, secara independen, lalu satu langkah bersama antar-trofi:

1. **Dedup plateau.** Dari deret `(t_jam, rate)` trofi itu, buang read
   berurutan yang ratenya identik dengan read sebelumnya; yang disimpan
   hanya kemunculan pertama tiap nilai distinct yang berurutan. Ini
   menghapus plateau basi (sifat 1 di atas) supaya fit tidak menganggap
   puluhan read identik sebagai bukti kuat bahwa rate tidak bergerak.
   Sisi buruknya dicatat di bawah: refresh yang kebetulan tidak mengubah
   suatu rate ikut terbuang.
2. **WLS logit vs log-waktu.** Ambil `y = logit(rate)` dan
   `x = ln(1 + t_jam)`, dengan `t_jam` jam sejak rilis
   (2026-11-19T00:00:00Z). Fit garis `y = a + b*x` dengan weighted
   least squares, bobot `w = 1 + t_jam / 24` — read yang lebih baru
   berbobot lebih besar, karena perilaku pemain minggu pertama berubah
   cepat. Skala `ln(1 + t)` dipilih karena earn rate game baru tumbuh
   cepat di awal lalu melambat: di skala ini, pertumbuhan yang melambat
   terlihat mendekati garis lurus, dan ekstrapolasi 4,5 hari ke depan
   tidak meledak seperti ekstrapolasi linier terhadap `t` mentah.
   Trofi dengan titik distinct kurang dari 3, atau tanpa variansi-x yang
   berarti, tidak difit dan jatuh ke fallback (langkah 4).
3. **Shrinkage slope hierarkis.** Slope tiap trofi di-shrink ke arah
   slope rata-rata populasi (semua trofi yang berhasil difit):
   `b_shrunk = (n*b + K*b_pop) / (n + K)` dengan `K = 5` dan `n` jumlah
   titik distinct trofi itu. Trofi dengan sedikit titik — yang slope-nya
   paling berisik — ditarik paling kuat ke perilaku umum; trofi dengan
   banyak titik mempertahankan slope-nya sendiri. Intercept `a` tetap
   milik trofi itu (level tiap trofi memang berbeda jauh), dan median
   forecast adalah `a + b_shrunk * ln(1 + t_target)`.
4. **Fallback persistence.** Bila trofi tidak bisa difit, median =
   rate terakhir yang terbaca (atau 1,0% bila tidak pernah terbaca).
   Ini persis house baseline — dan memang itulah yang seharusnya
   terjadi bila tidak ada sinyal tren yang bisa dipercaya.
5. **Spread kuantil.** Simpangan baku logit
   `sigma = sqrt((0,5^2) * horizon_hari + sigma_fit^2)`: suku pertama
   random walk (sama seperti house baseline, melebar dengan akar
   horizon), suku kedua simpangan residual fit (di-cap 1,0). Kuantil
   dihitung sebagai `rate(logit_median + z_tau * sigma)` dengan
   `z = -1,645 / -0,674 / 0 / 0,674 / 1,645`, dibulatkan half-up ke
   4 desimal dan dipaksa tidak menurun. Untuk fallback, `sigma_fit = 0`
   sehingga spread-nya sama dengan house baseline.

## Kenapa ini mengalahkan kedua baseline

- **Baseline persistence** (house baseline / starter): median = rate
  terakhir, spread random walk saja. Di practice ia mencetak loss
  ~1,51 karena refresh pertama mendorong semua rate keluar dari band
  90-menitnya yang sempit. Di final, dengan horizon 4,5 hari, ia
  mengabaikan seluruh tren pertumbuhan minggu pertama — median-nya
  diam di rate 21 Nov sementara jawaban 26 Nov sudah bergerak jauh.
  Model ini memakai median yang sama persis bila tidak ada sinyal tren
  (fallback), tetapi menggeser median mengikuti tren bila history
  menunjukkan pertumbuhan, dan melebarkan spread dengan residual fit.
- **Curve baseline** (house, tidak ada di kit): fit garis logit vs
  `ln(1 + jam)` hanya atas **24 jam terakhir**, tanpa dedup dan tanpa
  shrinkage. Tiga kelemahannya: (a) tanpa dedup, puluhan read plateau
  basi membebani fit seolah-olah rate sungguh konstan; (b) hanya 24 jam
  terakhir membuang sinyal awal rilis dan membuat fit goyah pada trofi
  yang jarang berubah; (c) tanpa shrinkage, trofi dengan 3–4 titik
  distinct bisa mendapat slope ekstrem dari noise lalu diekstrapolasi
  4,5 hari. Model ini memakai seluruh history dengan bobot recency
  (bukan jendela keras), dedup plateau sebelum fit, dan shrinkage slope
  ke populasi.

## Keterbatasan yang jujur

- **Practice tidak bisa memvalidasi jalur tren.** History practice
  sepenuhnya flat, jadi di practice model ini berperilaku identik
  dengan house baseline (median = rate terakhir). Jalur tren hanya
  dibuktikan lewat case sintetis (lihat Validasi), bukan lewat data
  nyata — karena data nyata dengan tren baru ada di final.
- **Refresh Exophase tidak bisa diprediksi.** Jawaban adalah rate pada
  halaman saat target, kapan pun Exophase terakhir me-refresh-nya.
  Bila refresh terakhir sebelum target sudah lama, jawaban bisa jauh
  dari tren mulus yang dimodelkan; spread random walk menampung sebagian
  risiko ini, tetapi tidak ada jaminan.
- **Dedup membuang informasi sebagian.** Refresh yang tidak mengubah
  suatu rate ikut terbuang, dan satu lompatan besar antar refresh
  (misalnya refresh pertama: hampir semua rate turun karena penyebut
  pemain melonjak 638 → 3.868) akan difit sebagai tren, padahal sebagian
  lompatan itu artefak penyebut, bukan perlambatan perolehan trofi.
- **Ekstrapolasi 4,5 hari dari ~36 jam data.** Slope yang difit dari
  dua hari pertama belum tentu bertahan sampai hari ketujuh; shrinkage
  dan spread yang melebar mengurangi kerusakan bila slope salah, tetapi
  hasil final bergantung pada pola pertumbuhan nyata 26 Nov yang tidak
  bisa diobservasi sekarang. Tidak ada margin yang dijamin.
- **Asumsi bentuk.** Tren logit-linier terhadap `ln(1 + t)` adalah
  pilihan bentuk yang masuk akal untuk minggu pertama, bukan hukum.
  Trofi dengan pola non-monoton (misalnya rate turun karena penyebut
  tumbuh lebih cepat daripada perolehan) hanya ditangkap sejauh garis
  lurus bisa menangkapnya.

## Menjalankan

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Membaca setiap `*.in` di `$MAKEFUN_INPUT_DIR` (default `/input`),
menulis `<id>.out` untuk tiap case ke `$MAKEFUN_OUTPUT_DIR` (default
`/output`). Python 3.13, standard library saja, tanpa network,
deterministik. `main.py` adalah satu-satunya entrypoint; tidak ada
dependensi lain.

## Validasi yang dilakukan

Validasi independen (bukan mengulang klaim pembangun pertama), semuanya
dengan `python3 -P -s` sesuai cara grader menjalankan program:

- **Practice (p00, p01):** kedua output terbentuk, 2.642 byte
  (< 65.536), JSON valid, tepat 55 baris, id 1–55 masing-masing sekali,
  tiap `q` lima angka 0–100 tidak menurun. Dua run ke direktori berbeda
  menghasilkan sha256 identik (`0a48f830…058d6d`), durasi ~0,05 detik
  per run (jauh di bawah batas 8 detik).
- **Median vs rate terakhir di practice:** median sama dengan rate
  terakhir untuk 54 dari 55 trofi. Satu-satunya pengecualian adalah
  id 2, yang rate terakhirnya 100% — di-clamp ke 99,99 karena logit
  tidak terdefinisi di 100%, sesuai aturan scoring. History practice
  memang flat, jadi fallback persistence adalah perilaku yang benar di
  sini; baris id 4 cocok persis dengan contoh house baseline di RULES
  (`[0.8974, 1.012, 1.1, 1.1955, 1.3477]`).
- **Case sintetis jalur tren:** history 6 read dengan rate trofi naik
  0,5% → 2,0% dan horizon 6.510 menit. Median hasil **3,0699%** —
  di atas rate terakhir 2,0% — membuktikan jalur tren bekerja;
  trofi kontrol yang flat tetap bermedian tepat 1,0%.
- **Edge case:** history kosong (median fallback 1,0%), hanya 2 nilai
  distinct setelah dedup (fallback ke rate terakhir), rate `null` dan
  daftar rate yang lebih pendek dari daftar trofi — semuanya berjalan
  tanpa crash dan bermedian sama dengan rate terakhir yang terbaca.
- **Revisi main.py:** satu perbaikan robustness — urutan trofi dari
  case kini dipertahankan saat deret dikumpulkan (karena `rates[i]`
  milik `trophies[i]` dalam urutan itu) dan pengurutan berdasarkan id
  dilakukan pada baris hasil. Sebelumnya trofi di-sort dulu, yang akan
  salah memetakan rate bila case datang dengan trofi tidak urut id.
  Diuji dengan case trofi tak urut: id 1 (naik) tetap median 3,0699,
  id 2 (flat) tetap 1,0. Output practice sesudah revisi byte-identik
  dengan sebelum revisi (sha256 sama).
