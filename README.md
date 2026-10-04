# KlaimKembar

Prototype lokal untuk memprioritaskan telaah kemungkinan repeat billing pada klaim fisioterapi sintetis. Skor bukan vonis kecurangan dan status Valid bukan persetujuan pembayaran.

## Jalankan dari nol

Prasyarat: Python **3.13** dan akses internet untuk instalasi pertama. Frontend tidak membutuhkan Node, npm, atau build terpisah.

1. Ekstrak ZIP, lalu buka terminal di folder yang berisi `run.py`.
2. Jalankan:

```bash
python run.py
```

Pada Linux/macOS, gunakan `python3 run.py` bila nama perintah Python adalah `python3`. Launcher membuat `.venv`, menginstal versi dependensi yang dipatok, membuat `.env` dengan dua token acak, menjalankan migrasi SQLite, dan menjalankan frontend serta API pada server yang sama.

3. Buka **http://127.0.0.1:8000**.
4. Unduh **http://127.0.0.1:8000/sample.csv**, lalu pilih file tersebut di halaman Unggah. Contoh ini berisi 5.000 klaim sintetis. Jangan memakai data pasien atau klaim JKN asli.
5. Lanjutkan validasi, buka antrean, bandingkan klaim, isi catatan, dan simpan salah satu dari tiga keputusan. Evaluasi tersedia dari navigasi bawah. Ctrl+C menghentikan server; keputusan tetap tersimpan dalam `var/klaimkembar.sqlite`.

Tidak ada akun atau token yang perlu diketik di UI demo. Sesi lokal memakai cookie HttpOnly, SameSite=strict, origin yang sama, dan CSRF. Adapter ini hanya aktif saat `LOCAL_UI=true`; `run.py` mengaktifkannya dan server diikat ke loopback. Bukan autentikasi produksi. Jangan mengubah host menjadi `0.0.0.0` untuk menyajikan prototype ini ke internet.

## Data dan hasil

- Maksimal 5 MiB/file, 10.000 baris, 100.000 kandidat, dan 200.000 pasangan eligible. CSV harus memakai ID sintetis berawalan `SYN-`.
- Sepuluh kolom wajib: `claim_id`, `participant_token`, `facility_id`, `service_date`, `submission_date`, `diagnosis_group`, `procedure_group`, `claim_amount`, `claim_status`, `original_claim_id`.
- Kolom opsional: `facility_group`, `episode_id`, `visit_id`, `scheduled_service`, `scheduled_date`.
- Kesalahan baris menolak seluruh batch. Diagnosis/tindakan kosong dicatat sebagai informasi kurang; valid format tidak berarti lengkap secara klinis.
- UI tidak mengunggah label. Tanpa label, metrik dataset tidak tersedia; layar Evaluasi menampilkan **benchmark lima seed internal**, dengan sumber yang disebut jelas. Angka pada desain Figma bukan hasil pengujian.
- Benchmark: seed 104, 211, 307, 409, 503, masing-masing 5.000 klaim. Label disimpan terpisah dari detector. Waktu per pendekatan belum diukur; median waktu keputusan pertama adalah catatan UI, bukan studi pengguna.

## Instalasi API manual

```bash
python -m venv .venv
# Linux/macOS
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m scripts.manage init-env
.venv/bin/python -m scripts.manage migrate
.venv/bin/python -m scripts.manage seed
.venv/bin/python -m scripts.manage benchmark
.venv/bin/python -m uvicorn klaimkembar.main:app --env-file .env --host 127.0.0.1 --port 8000 --no-access-log
```

Pada Windows, ganti `.venv/bin/python` dengan `.venv\Scripts\python.exe`. Mode manual di atas tidak membuka adapter UI; gunakan `run.py` untuk aplikasi lengkap. Jika mengubah `DATABASE_PATH`, muat `.env` sebelum perintah migrasi. Token tidak dicetak dan `.env` tidak disertakan dalam paket.

## Pengujian Python

```bash
.venv/bin/python -m scripts.build_contract
.venv/bin/ruff check klaimkembar tests scripts
.venv/bin/mypy
.venv/bin/python -m pytest -q --cov=klaimkembar --cov-report=term-missing
.venv/bin/python -m pip check
```

Hasil verifikasi: **80 tes lulus**, line coverage **98,18%**. Ini ukuran cakupan kode saat tes, bukan akurasi deteksi. Satu peringatan deprecation `httpx`/Starlette tidak menyebabkan kegagalan. Lihat `docs/qa` untuk bukti.

## Pengujian browser (opsional bagi pengembang)

Aplikasi harus berjalan pada port 8000. Tes memakai Chromium dan Playwright 1.63.0. Node hanya diperlukan untuk tes ini, bukan untuk memakai aplikasi.

```bash
npm install
npx playwright install chromium
npm run test:browser
```

Jika Chromium sudah tersedia, set `CHROMIUM_PATH` ke executable-nya. Tes mencakup unggah 5.000 baris, error format/kosong, retry jaringan, proses, filter, pagination, perbandingan, tiga keputusan, revisi, konflik dua sesi, reload, antrean selesai, evaluasi, serta viewport 390/1280 px. Bukti disimpan di `var/browser-qa`. Tes menambah dataset sintetis dan keputusan demo; gunakan database uji bila tidak ingin menambah data demo.

## Kontrak dan struktur

- `frontend/`: UI tanpa framework, mengikuti struktur 12 layar desain yang diberikan.
- `klaimkembar/`: API, aturan, validasi, detector, evaluasi, dan audit.
- `openapi.json`: kontrak publik, termasuk endpoint pilihan filter.
- `migrations/`: migrasi dari database kosong.
- `examples/`: klaim, label, benchmark, dan provenance.
- `FE_INTEGRATION.md`: pemetaan UI/API dan perbedaan data contoh.
- `ASSUMPTIONS.md`: asumsi sementara dan batas produksi.
- `docs/data-and-states.md`: diagram Mermaid; `docs/qa`: hasil pengujian.

## GitHub dan batas penerapan

Target yang disetujui: repo private `ShikinariShiki/KlaimKembar`. Pembuatan repo melalui koneksi GitHub ditolak dengan HTTP 403 (izin token), sehingga publikasi belum selesai. Source siap dipublikasikan setelah akses tulis tersedia. `.env`, database, cache, dan `.venv` dikecualikan. Tidak ada deployment online dalam scope.

Figma dibaca melalui viewer browser karena koneksi yang tersedia tidak menyediakan `get_design_context` untuk file Design. Viewer menampilkan 12 frame, tetapi inspect/present memerlukan login. Implementasi mengikuti referensi visual dan lampiran proposal; kesamaan piksel serta koneksi prototipe internal Figma tidak diklaim terverifikasi.

Belum diuji: verifikator nyata, usability study, data JKN asli, beban produksi, keamanan produksi, dan efektivitas penghematan. Jangan menyebut hasil simulasi sebagai performa klinis.
