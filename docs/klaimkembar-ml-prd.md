# Pipeline dan PRD Integrasi Machine Learning KlaimKembar

**Status:** Draft untuk penyelarasan scope  
**Basis:** Proposal KlaimKembar Healthkathon 2026, user flow KlaimKembar, dan inventaris folder Data Rilis 2025  
**Tanggal:** 30 Oktober 2026

## 1. Ringkasan keputusan produk

KlaimKembar tetap menjadi dashboard pendukung verifikator untuk memprioritaskan kemungkinan repeat billing pada klaim fisioterapi rawat jalan. Perubahan yang diusulkan adalah menambahkan model machine learning (ML) sebagai lapisan pemeringkat pasangan klaim di dalam pipeline deteksi yang sudah ada. ML tidak mengambil keputusan valid/fraud dan tidak menggantikan validasi, candidate blocking, guardrail, alasan yang dapat ditinjau, atau keputusan petugas.

**Keputusan desain awal:** pertahankan exact-match dan similarity rules sebagai baseline serta fallback; gunakan ML hanya setelah candidate blocking untuk mengurutkan pasangan kandidat. Model belum boleh dilatih dari data yang tersedia hanya karena folder berjudul “Data Rilis2025”. Label hasil pemeriksaan yang sah, definisi target, izin penggunaan, dan audit kualitas data harus disepakati lebih dulu.

**Kondisi sumber saat ditinjau:** proposal menggambarkan prototype lokal FastAPI + SQLite yang berjalan dengan sekitar 5.000 klaim sintetis dan aturan berbobot; proposal menyebut belum memakai ML, belum ada data klaim JKN riil, usability test, pilot, maupun integrasi BPJS. User flow yang ada mencakup upload CSV, validasi, antrean, perbandingan klaim, keputusan petugas, dan evaluasi. Source lokal belum ditemukan pada pencarian awal. Audit read-only menemukan repo privat GitHub `ShikinariShiki/klaimkembar`, branch `main` commit `115b94284ecad7fbbfa88699cc8e4bbd0d19ae49`. Source menunjukkan frontend HTML/JS, FastAPI, SQLite, migrasi, engine rules, dan tes; endpoint upload, antrean, detail, review dan evaluasi terdapat pada `app.py`. README membatasi demo pada loopback, autentikasi demo dan ID sintetis SYN-; penggunaan data pasien asli dan akses produksi belum didukung. Ini inspeksi source, bukan verifikasi runtime atau kesiapan deployment.

**Hasil cek data lokal:** paket berisi tujuh kelompok berlabel “Sampel ... Edisi 2025”. Metadata Stata dan agregat pada file reguler menunjukkan `202403_fkrtl.dta` memiliki 1.699.219 baris, `202402_fktpkapitasi.dta` 4.073.388 baris, dan `202404_nonkapitasi.dta` 258.201 baris. Rentang kolom tanggal datang/kunjungan yang diprofilkan berakhir pada 31 Desember 2024; beberapa tanggal pulang melampaui akhir tahun, paling jauh 7 Januari 2025 pada file FKTP. Jadi edisi rilis 2025 tidak sama dengan klaim layanan tahun 2025. Pencarian teks literal “fisioterapi/physiotherapy” pada kolom layanan yang diprofilkan tidak menemukan baris. Pemeriksaan ulang menemukan token `93.39` atau `9339` pada `FKL30` di 87.525 dari 174.026 record RJTL/poli IRM di file FKRTL reguler. Hitungan satu pada versi sebelumnya salah akibat pola pencarian kode bertitik yang keliru. Kode ICD-9-CM `93.39` dirujuk sebagai “Other physical therapy/physiotherapy” dalam [manual prosedur Kementerian Kesehatan Malaysia](https://www2.moh.gov.my/moh/resources/REFERENCE_MANUAL_FOR_PROCEDURE_DOCUMENTATION_CODING_ACCORDING_TO_ICD-9-CM_30082021.pdf), tetapi pemetaan `FKL30` ke sistem kode itu belum dikonfirmasi dengan kamus data rilis. Ini sinyal kandidat fisioterapi yang menjanjikan, tetapi perlu konfirmasi kamus data dan bukan label repeat billing. Audit ulang missingness pada seluruh FKRTL mendapati `FKL30` kosong atau null pada 708.359 dari 1.699.219 baris (41,69%); hitung null saja sebelumnya melewatkan string kosong. Kolom PSTV01, FKL02, FKL03/04, FKL10/11, FKL18 dan FKL47/48 tidak kosong/null dengan definisi ini; validitas nilai belum diuji.

**Kecocokan dan sensitivitas:** schema FKRTL memiliki nomor peserta, nomor keluarga, ID kunjungan, tanggal datang/pulang, tipe poli/prosedur, diagnosis, dan tarif; FKTP/non-kapitasi memiliki ID kunjungan dan field layanan masing-masing. Kolom peserta/keluarga adalah identifier yang sifat pseudonimisasinya belum dibuktikan; jangan menganggapnya sama dengan `participant_token` demo. Dari schema yang ditinjau belum tampak label adjudikasi repeat billing, status klaim active/cancelled/corrected, original claim link, submission date, atau `episode_id`; tersedia ID kunjungan FKRTL, namun belum tentu setara dengan visit ID granular di prototype. Kode FKRTL yang ditinjau tidak menampilkan facility ID eksplisit yang dibutuhkan blocking “fasilitas sama”. Ini temuan awal berbasis schema, perlu dicocokkan dengan dokumentasi rilis dan nilai kategori yang diperbolehkan sebelum keputusan final. Nilai baris atau identifier tidak dikeluarkan dalam audit ini.

## 2. Pipeline kerja yang disarankan

| Fase | Aktivitas | Hasil / gate keluar |
|---|---|---|
| 0. Konfirmasi aset dan otorisasi | Verifikasi branch dan runtime repo yang ditemukan; tetapkan pemilik data, dasar izin, klasifikasi, tujuan, masa simpan, dan lingkungan pemrosesan. Pastikan arti “data asli 2025” (tahun layanan, tahun rilis, atau keduanya). | Peta komponen existing; keputusan boleh/tidaknya data dipakai; inventaris dataset dan dokumentasi sumber tanpa menyalin isi sensitif. |
| 1. Profil skema dan kecocokan | Metadata dan agregat awal sudah dibaca untuk file `.dta`; lanjutkan validasi dokumentasi, mapping kode, relasi antar tabel, cakupan target, dan versi. Cocokkan dengan field produk: token peserta, facility ID, tanggal layanan/pengajuan, tindakan/diagnosis, nilai, status, visit/episode, pembatalan/koreksi. | Data dictionary dan mapping ke skema kanonis; daftar field tidak tersedia; keputusan subset uji yang relevan. Jangan lanjut jika identitas atau status klaim tidak bisa ditangani dengan aman. |
| 2. Definisi target dan label | Bersama verifikator/domain expert definisikan unit label (pasangan/kelompok), positive/negative/unknown, repeat billing vs layanan berulang sah, fragmentasi, koreksi/pembatalan. Label “tidak diketahui” tidak dipaksa menjadi negatif. | Labeling guide, adjudication workflow, label provenance, dan estimasi kecukupan label. Tanpa label yang dapat dipertanggungjawabkan, hanya evaluasi rules/synthetic dan desain data yang dilanjutkan. |
| 3. Data preparation aman | Proses pada lingkungan terbatas; tokenisasi/pseudonimisasi sebelum feature store; minimisasi kolom; validasi skema; deduplikasi; normalisasi tanggal/kode/nilai; audit akses; dataset versioning. Pisahkan data identitas dan data fitur. | Dataset analitik dengan ID internal, manifest sumber, transformasi yang dapat direproduksi, laporan kualitas agregat, dan kebijakan retensi/penghapusan. Tidak ada ekspor raw ke log, notebook bersama, atau layanan eksternal. |
| 4. Baseline dan eksperimen | Reproduksi exact-match dan rule-based score existing. Bangun candidate blocking yang sama agar pembanding adil. Uji model sederhana (mis. logistic regression) sebagai baseline ML; bandingkan model pohon/boosting hanya jika volume dan kualitas label memadai. | Laporan eksperimen berisi PR-AUC/average precision, precision, recall, F1 pada threshold, Recall@Top-K, false positives per 1.000 klaim, kalibrasi, interval/rentang, serta contoh error teranonimkan. Split waktu dan kelompok fasilitas untuk mengurangi leakage. |
| 5. Human review dan penjelasan | Tampilkan prioritas, kontribusi faktor, alasan rules, data yang hilang, versi model, serta disclaimer skor bukan vonis. Rekam keputusan petugas dan alasan koreksi sebagai umpan balik terkontrol. | UI review berdampingan tetap utuh; model dapat dimatikan; keputusan petugas tidak ditimpa skor. Penjelasan konsisten dan dapat ditelusuri. |
| 6. Shadow evaluation | Jalankan model pada data yang diizinkan tanpa memengaruhi antrean operasional; bandingkan rekomendasi dengan hasil adjudikasi petugas; ukur beban review, drift dan perbedaan performa antar kelompok yang layak diuji. | Persetujuan domain, keamanan, privasi, dan produk sebelum model dipakai untuk memprioritaskan kasus. Hentikan/rollback bila guardrail atau metrik minimum gagal. |
| 7. Pilot terbatas dan monitoring | Pilot terbatas dengan otorisasi formal, akses berbasis peran, audit, retensi, observability tanpa payload sensitif, runbook insiden, rollback ke rules-only. Review berkala bersama pemilik proses. | Catatan pilot, metrik operasional dan kualitas, keputusan lanjut/perbaiki/hentikan. Integrasi sistem resmi menjadi proyek terpisah setelah kontrak, keamanan, dan persetujuan tersedia. |

### Eksekusi kerja efisien dengan GPT-6.1 Terra dan subagents

Ini adalah pola orkestrasi prompt-level; tidak mengasumsikan kemampuan internal Terra tertentu. Satu orchestrator menjadi pemilik keputusan dan satu-satunya editor PRD. Jalankan tugas read-only paralel dengan scope terpisah:

| Worker | Scope | Output dibatasi |
|---|---|---|
| A — Data audit | Metadata/schema, jumlah baris, rentang waktu, missingness agregat, field layanan/label yang tersedia. Jangan keluarkan nilai identitas atau baris contoh. | Ringkasan field map, metode, batas audit, dan evidence path; maksimal satu halaman. |
| B — Repo discovery | Temukan repo, entrypoint, skema/API, tests dan status branch tanpa membuka data klaim. | Peta komponen existing + file/line evidence; maksimal satu halaman. |
| C — Product/spec review | Ekstrak proposal, user flow, risiko, asumsi dan acceptance criteria; tandai konflik. | Matriks kebutuhan/evidence/unknown; maksimal satu halaman. |

**Dependency DAG:** A + B + C berjalan paralel → orchestrator menggabungkan temuan dan menandai fakta/inferensi/unknown → gate izin dan kecocokan field/label → data contract & label guide → reproduksi baseline → eksperimen offline → review verifikator → shadow run → keputusan pilot. Jangan menjalankan eksperimen ML, shadow, atau pilot sebelum gate data/label lulus.

Setiap subagent menerima hanya folder yang diperlukan, larangan raw-row/PII, pertanyaan sempit, dan format keluaran tetap (`findings`, `evidence`, `method`, `unknowns`, `recommendation`). Orchestrator memangkas duplikasi, menyelesaikan konflik dengan bukti sumber, melakukan satu edit PRD, lalu meminta satu reviewer read-only memeriksa kontradiksi/acceptance criteria. Hindari beberapa agen mengedit file yang sama dan hindari mengirim dump dataset ke konteks model.

**Stop conditions:** hentikan jalur ML bila pemakaian data tidak disetujui; field wajib atau label yang defensible tidak ada; leakage tidak dapat dicegah; model tidak memberi perbaikan atas rules pada split yang sama; beban false positive tidak dapat diterima; atau audit, fallback, dan rollback tidak lolos. Lanjutkan pekerjaan dokumentasi/synthetic hanya dengan menyatakan batasnya.
### Alur runtime setelah ML ditambahkan

1. Petugas mengunggah file melalui alur existing.
2. Sistem memvalidasi format, kolom, tipe, status klaim, dan kualitas batch; batch gagal tidak disimpan sebagian.
3. Data dinormalisasi dan ditautkan ke identitas ter-tokenisasi sesuai kontrol akses.
4. Candidate blocking membatasi pasangan berdasarkan kunci yang disetujui (misalnya token peserta, fasilitas terkait, dan jendela waktu). Blocking menghasilkan kandidat, bukan kesimpulan.
5. Guardrail deterministik menandai kondisi yang punya bukti terstruktur: tautan batal-koreksi, visit berbeda, atau jadwal berulang yang tervalidasi. Data yang hilang tidak dianggap bukti bahwa klaim sah.
6. Rules baseline dan model menghitung skor/prioritas untuk pasangan eligible. Jika model tidak tersedia, versinya tidak cocok, atau input di luar dukungan, sistem turun ke rules-only dan mencatat fallback.
7. Antrean menyajikan prioritas dan reason codes; petugas memeriksa dua klaim, kronologi, persamaan/perbedaan, bukti guardrail, dan kelengkapan data.
8. Petugas memilih Valid, Perlu dokumen tambahan, atau Perlu pemeriksaan lebih lanjut, menambahkan catatan, lalu keputusan dicatat append-only dengan versi rules/model.
9. Evaluasi melaporkan hasil sesuai cakupan label dan dataset; data tanpa label tidak ditampilkan seolah-olah memiliki akurasi terukur.

## 3. PRD perubahan integrasi ML

### 3.1 Latar belakang

Prototype saat ini menggunakan validasi, candidate blocking, komponen skor kemiripan berbobot, reason codes, guardrail kasus sah, antrean prioritas, perbandingan berdampingan, keputusan manusia, audit, dan halaman evaluasi. Proposal menetapkan bobot, jendela tiga hari, dan ambang antrean sebagai parameter awal yang belum dikalibrasi klinis. Proposal juga menegaskan angka evaluasi berasal dari simulasi sintetis internal, bukan validasi pada data JKN.

Perubahan ini menambah jalur ML yang dapat dibandingkan dengan baseline dan dikendalikan. Tujuan awalnya meningkatkan urutan kasus yang relevan untuk ditinjau ketika pola lebih kompleks dari aturan eksplisit, sambil mengukur trade-off false positive dan beban petugas. Klaim manfaat harus menunggu evaluasi berlabel dan pilot.

### 3.2 Pengguna dan kebutuhan

- **Verifikator:** ingin menemukan kasus yang layak ditinjau lebih awal dan memahami alasan pengurutannya.
- **Auditor/supervisor:** ingin menelusuri versi data, model, aturan, dan keputusan tanpa skor berubah diam-diam.
- **Data/ML operator:** ingin melatih dan membandingkan model secara terkendali tanpa akses yang tidak perlu ke identitas.
- **Pemilik proses dan tata kelola:** ingin menyetujui tujuan, akses, retensi, ambang, serta syarat penggunaan sebelum pilot.

### 3.3 Tujuan

1. Menambahkan pemeringkatan ML sebagai opsi dalam alur existing dengan rules-only fallback.
2. Menjaga setiap rekomendasi dapat ditinjau, dilacak, dan dibatalkan oleh keputusan petugas.
3. Membandingkan model secara adil dengan exact-match dan rule-based baseline pada data berlabel yang penggunaannya diizinkan.
4. Mencegah penggunaan data tanpa label atau tanpa dasar/izin seolah-olah sudah tervalidasi.

### 3.4 Bukan tujuan

- Menentukan fraud, menolak/membayar klaim, atau memberi sanksi secara otomatis.
- Menggantikan verifikator, clinical/domain review, atau proses resmi BPJS.
- Melatih model dari seluruh file rilis tanpa pemetaan skema, pemeriksaan izin, dan label target.
- Memperluas fokus dari fisioterapi rawat jalan sebelum pilot awal dinilai.
- Menghubungkan langsung ke sistem produksi BPJS atau mengirim data ke API/model pihak ketiga pada fase ini.

### 3.5 Kebutuhan fungsional

| ID | Prioritas | Kebutuhan | Kriteria penerimaan |
|---|---|---|---|
| ML-01 | P0 | Tetap tersedia jalur rules-only dan exact-match sebagai baseline/fallback. | Operator dapat memilih mode eksperimen; kegagalan model tidak menghentikan antrean; mode dan penyebab fallback tercatat. |
| ML-02 | P0 | Candidate blocking berjalan sebelum scoring model. | Model hanya menerima pasangan eligible; jumlah kandidat dan alasan blocking tercatat agregat; tidak ada pembandingan semua baris secara tak terbatas. |
| ML-03 | P0 | Skor model berarti prioritas review dan tidak boleh disebut probabilitas fraud; bahkan probabilitas repeat billing hanya dapat disebut demikian jika label target dan kalibrasi mendukungnya. | UI menggunakan istilah prioritas; tidak ada label fraud otomatis; definisi skor dan batas interpretasinya terlihat. |
| ML-04 | P0 | Menampilkan alasan pasangan dan perbedaan yang dapat dipahami. | Detail menampilkan reason codes existing, faktor utama yang menaikkan/menurunkan prioritas, field berbeda, dan missing data; pengguna dapat membuka bukti sumber yang diizinkan. |
| ML-05 | P0 | Menjaga kontrol keputusan manusia dan audit append-only. | Status hanya berubah lewat tindakan petugas; audit menyimpan aktor/peran, timestamp, catatan, review ID, data/model/rules version dan fallback; retry idempoten dan konflik versi ditolak. |
| ML-06 | P0 | Mengelola versi dan rilis model. | Setiap model memiliki ID, checksum, skema fitur, waktu pelatihan, dataset/split manifest, metrik, threshold, owner, dan status draft/shadow/approved/retired. Versi aktif tidak tertimpa. |
| ML-07 | P0 | Melindungi data sensitif. | Tidak ada nilai identitas langsung di log; akses berbasis peran; dataset pelatihan dipisahkan dari data operasional; akses dan ekspor tercatat; masa simpan/penghapusan dikonfigurasi sebelum pilot. |
| ML-08 | P1 | Mendukung eksperimen dan evaluasi yang dapat direproduksi. | Laporan membandingkan exact-match, rules, dan ML pada split/label yang sama, melaporkan metrik per threshold dan top-K, rentang/ketidakpastian, missingness, serta false-positive review. |
| ML-09 | P1 | Menggunakan hasil keputusan petugas sebagai kandidat umpan balik, bukan label otomatis. | Label baru hanya masuk setelah proses adjudikasi/konfirmasi; keputusan belum final atau “dokumen tambahan” tetap unknown; perubahan label berversi dan beralasan. |
| ML-10 | P1 | Mendeteksi penurunan kualitas dan memungkinkan rollback. | Dashboard/runbook memantau volume kandidat, missingness, distribusi skor, fallback, drift fitur, metrik label tertunda, dan performa kelompok; rollback ke versi rules-only terdokumentasi. |

### 3.6 Kebutuhan data dan target

**Target yang diusulkan untuk eksperimen:** apakah satu pasangan klaim merupakan repeat billing yang sudah dikonfirmasi melalui proses verifikasi/adjudikasi yang dapat ditelusuri. Definisi final harus disepakati ahli proses. Klasifikasi ini tidak boleh disimpulkan dari kemiripan saja.

**Label:** `confirmed_repeat`, `confirmed_distinct_or_legitimate`, `unknown_or_pending` (di luar supervised training utama), dan status adjudikasi/asal label. Perlu definisi terpisah untuk klaim terkoreksi, layanan berkala, satu episode yang terfragmentasi, dan kunjungan terpisah. Label sintetis berguna untuk regression test, tetapi tidak menjadi bukti kinerja lapangan.

**Fitur kandidat:** jarak tanggal layanan/pengajuan; kemiripan tindakan/diagnosis terkelompok; nilai relatif; status klaim; hubungan fasilitas; tautan klaim koreksi; jadwal/visit/episode bila tersedia; indikator missingness. Identitas peserta dipakai untuk blocking dengan token, bukan sebagai sinyal target yang membuat identitas langsung tersedia untuk model. Daftar final bergantung pada data dictionary dan tinjauan domain.

**Pencegahan kebocoran:** seluruh pasangan dari satu episode/kelompok terkait harus tetap berada dalam satu split; utamakan split waktu dan, bila jumlah memadai, uji holdout fasilitas. Hilangkan field yang hanya diketahui setelah keputusan atau yang mengkodekan label. Transformasi, label, dan split harus disimpan berversi.

### 3.7 Kebutuhan nonfungsional

- **Privasi dan keamanan:** minimisasi data, pseudonimisasi, least privilege, enkripsi saat transit/tersimpan sebelum pilot, retensi terbatas, audit akses, secret management, dan prosedur insiden. Data kesehatan tidak dikirim ke layanan eksternal tanpa persetujuan dan kontrol formal.
- **Reliabilitas:** model timeout/error/versi tidak dikenal memicu fallback rules-only; unggahan dan audit tetap konsisten serta idempoten.
- **Keterlacakan:** skor yang dilihat petugas dapat direproduksi dari versi fitur, rules, model, dan konfigurasi yang tercatat.
- **Kegunaan:** alasan, batas skor, dan missing information muncul dalam konteks perbandingan klaim; model tidak menambah layar kerja wajib yang tidak perlu.
- **Kinerja:** tetapkan SLA setelah ukuran batch dan lingkungan target dikonfirmasi. Jangan mengekstrapolasi batas prototype 10.000 baris/100.000 kandidat ke data operasional tanpa uji beban.

### 3.8 Metrik dan kriteria go/no-go

Metrik minimum: average precision/PR-AUC, precision dan recall pada ambang yang dipilih, F1 sebagai metrik tambahan, Recall@Top-10% antrean, false-positive pairs per 1.000 klaim, kalibrasi jika skor disebut probabilitas, waktu inferensi, tingkat fallback, dan hasil per kelompok yang relevan serta layak secara privasi. Evaluasi perlu memperhitungkan unit kasus dan proporsi kandidat, bukan hanya jumlah baris.

**Belum menetapkan angka lulus baru.** Ambang penerimaan perlu ditetapkan bersama verifikator/pemilik proses setelah label dan kapasitas review diketahui. Go ke shadow hanya jika: data dan label disetujui; split bebas leakage; baseline dapat direproduksi; tidak ada regresi pada guardrail; penjelasan/audit/fallback lolos; serta privasi dan keamanan menyetujui. Go ke antrean pilot memerlukan hasil shadow yang disetujui dan rencana rollback. Klaim angka proposal (hasil 5 seed sintetis) tidak digunakan sebagai target kinerja data nyata.

### 3.9 Risiko utama

| Risiko | Dampak | Pengendalian awal |
|---|---|---|
| Rilis sampel disalahartikan sebagai data klaim layanan 2025 | Model dilatih/diklaim valid tanpa sumber atau periode yang tepat | Manifest sumber, cek metadata/tanggal, pemilik data, dan gate otorisasi sebelum pemakaian. |
| Label tidak tersedia atau bias | Model mempelajari keputusan yang tidak konsisten atau menganggap kasus belum selesai sebagai negatif | Adjudication guide, label unknown, audit antar-penilai, dan evaluasi error. |
| Leakage antar pasangan/episode | Skor offline tampak sangat tinggi tetapi gagal pada kasus baru | Group split berbasis episode/peserta dan holdout waktu/fasilitas; inspeksi fitur pasca-keputusan. |
| Automation bias | Petugas menerima ranking sebagai vonis | Bahasa prioritas, alasan yang seimbang, keputusan manual wajib, dan uji pemahaman pengguna. |
| False positive tidak merata | Beban pemeriksaan merugikan fasilitas/jenis layanan tertentu | Review metrik per kelompok yang layak, konsultasi domain, threshold dan guardrail yang dapat ditinjau. |
| Drift atau model gagal | Antrean kehilangan relevansi atau model tidak tersedia | Monitoring, version pinning, fallback rules-only, kill switch, dan rollback. |
| Paparan data kesehatan | Risiko privasi dan kepercayaan | Pemrosesan lokal/lingkungan terkontrol, minimisasi, pseudonimisasi, RBAC, enkripsi, retensi, dan audit. |

## 4. Urutan backlog implementasi

1. **Discovery (sebelum coding ML):** temukan repository dan jalur runtime existing; inventaris tabel/field tanpa menampilkan nilai; klarifikasi sumber dan periode data; tetapkan otorisasi serta data owner.
2. **Data contract:** buat kamus kanonis dan mapping dari file `.dta` ke struktur klaim; tandai field tersedia/tidak tersedia, kualitas, dan sensitivitas; jangan mengubah CSV contract publik tanpa rencana migrasi.
3. **Label dan evaluasi:** susun definisi target dan adjudikasi; buat split bebas leakage; reproduksi baseline existing pada label yang sama.
4. **ML offline:** implementasikan pipeline fitur dan model baseline yang sederhana; bandingkan hasil dan error; simpan artefak versi; review model dengan verifikator.
5. **Integrasi mode shadow:** tambahkan scoring service/interface, fallback, version metadata, audit, dan laporan tanpa mengubah antrean petugas.
6. **UX dan tata kelola:** tampilkan prioritas, alasan, kelengkapan, versi dan batas interpretasi; tambahkan kontrol aktivasi/rollback serta dokumentasi operator.
7. **Pilot terbatas:** setelah persetujuan tertulis dan gate penerimaan dipenuhi, jalankan dengan cakupan dan retensi minimum; ukur kualitas, waktu review, dan dampak distribusi.
8. **Keputusan scale-up:** perluasan layanan atau integrasi sistem hanya setelah evaluasi pilot, kontrak integrasi, keamanan, kapasitas, serta persetujuan pemilik proses.

## 5. Keputusan yang masih terbuka

1. “Data asli tahun 2025” berarti tahun pelayanan 2025, tahun rilis 2025, atau file yang diterima pada 2025? Inventaris yang terlihat menunjukkan rilis 2025 dengan beberapa nama file sampai 2024.
2. Apakah data tersebut secara resmi boleh dipakai untuk pengembangan model, dan siapa pemilik/pemberi persetujuannya?
3. Apakah ada data adjudikasi repeat billing, status koreksi/pembayaran, serta ID visit/episode yang dapat digunakan? Kalau belum, siapa yang akan membuat label dan melalui proses apa?
4. Apakah target produk awal tetap fisioterapi rawat jalan dan sumber datanya FKRTL, atau ingin mengubah cakupan setelah melihat data?
5. Repo privat dan commit telah ditemukan; apakah branch/commit tersebut versi yang ingin dikembangkan, dan bagaimana kontrak deployment, migrasi database, serta autentikasi produksi akan disepakati?
6. Siapa reviewer domain, data steward, dan penanggung jawab keamanan/privasi untuk gate shadow dan pilot?

## 6. Referensi kerja yang digunakan

- `Proposal KlaimKembar_Healthkathon2026.docx` — spesifikasi prototype, batas evaluasi, risiko, dan roadmap.
- `KlaimKembar_Healthkathon_2026_v2.pptx.pdf` — bahan presentasi tersedia di folder sumber; draft ini mengikuti uraian proposal.
- `C:\Users\USER\Downloads\Others\Userflow KlaimKembar.json` — alur upload, validasi, antrean, perbandingan, keputusan, dan evaluasi.
- `Data Rilis2025\2025\Data Sampel Reguler Edisi 2025\data` serta direktori edisi kontekstual — metadata dan agregat dihitung secara lokal dari baris data, tanpa keluaran nilai baris atau identifier.

---

**Status keputusan:** dokumen ini adalah rancangan pipeline dan PRD awal integrasi ML. Scope teknis rinci menunggu audit runtime repo, data dictionary, bukti otorisasi, dan keputusan label/data target.







## 7. Rekonsiliasi bahan presentasi dan proposal

**FACT:** PDF slide 13 halaman dan proposal menunjukkan alur upload hingga review. Ada konflik yang perlu diselesaikan sebelum presentasi: slide halaman 6 menempatkan CatBoost/Logistic Regression pada alur sekarang, sedangkan halaman 12 dan proposal Bagian 4 menempatkan ML sebagai rencana; slide halaman 5 menyebut satuan klaim untuk 6,36 per 1.000 dan satu pengujian, sedangkan proposal menyebut rata-rata lima seed dan pasangan false positive per 1.000 klaim; slide halaman 7 memiliki contoh prioritas yang tidak konsisten dengan ambang antrean 50, sedang 65, tinggi 85 dalam proposal. Slide halaman 4 menyebut Rp191,33 triliun sebagai anggaran, proposal menyebut pengeluaran layanan. Slide halaman 3/10 menyiratkan perlindungan terapi sah otomatis, sedangkan proposal mensyaratkan bukti; slide halaman 9–11 menyatakan log tidak bisa diubah, sementara proposal hanya menjelaskan append-only prototype. **OPEN:** selaraskan dengan implementasi dan sumber angka sebelum mengubah slide; jangan mengklaim ML sudah terintegrasi atau audit log aman untuk produksi tanpa bukti.

## 8. Kepemilikan dan keputusan

| Aktivitas | Penanggung jawab yang diusulkan | Keputusan / gate |
|---|---|---|
| Data dan izin | Pemilik data / data steward (belum ditentukan) | Tujuan, hak penggunaan, retensi, lingkungan dan data contract. |
| Label dan domain | Verifikator BPJS / ahli layanan (belum ditentukan) | Definisi target, adjudikasi, aturan kasus sah dan ambang beban review. |
| Produk dan UX | Puri Retno Nurlingga menurut proposal | Cakupan, alur petugas, acceptance criteria dan uji pengguna. |
| Backend dan data | Nathanael Kevin Irwanto menurut proposal | Mapping, baseline, model, audit, fallback dan dokumentasi. |
| Keamanan dan operasi | Penanggung jawab belum ditentukan | Akses, enkripsi, log, insiden, rollback dan keputusan pilot. |

Penugasan di atas mengikuti pembagian dalam proposal dan merupakan usulan untuk fase baru; komitmen serta kewenangan masing-masing belum dikonfirmasi. Produksi tetap menunggu gate data, label, evaluasi, keamanan, dan pilot. Sebuah demo memakai data sintetis dapat dirancang terpisah bila source dan lingkungan tersedia, dengan label demo yang jelas.



## 9. Kriteria tambahan evaluasi dan deployment

**Blocking:** evaluasi ranking pada kandidat bersama hanya mengukur performa di antara kandidat yang lolos. Ukur blocking recall dan recall ujung ke ujung pada sampel adjudikasi independen yang mencakup pasangan di luar blocking. Jika label belum ada, metriknya tidak terukur.

**Shadow acceptance:** mode shadow tidak mengubah urutan antrean rules, status, atau keputusan; skor ML disimpan terpisah dengan versi data/model dan tanpa payload sensitif di log. Saat timeout/gagal, hasil rules tetap tersedia dan status konsisten; pemadaman shadow dan rollback tercatat.

**Deployment:** demo publik sintetis dan pilot data riil memiliki gate terpisah. Demo membutuhkan konfigurasi aman, autentikasi sesuai tujuan, secrets, migrasi yang dapat dibalik dan smoke test. Pilot data riil menambahkan izin, label dan evaluasi domain, keamanan, RLS jika Supabase digunakan, retensi, monitoring dan persetujuan pemilik proses. Kesesuaian Vercel dan Supabase dengan FastAPI dan kebutuhan runtime harus diuji; login aktif tidak membuktikan kesiapan produksi. Supabase belum terverifikasi. Tidak ada deployment produksi yang sudah dibuktikan.

**RACI usulan:** Data contract: A pemilik data, R backend/data, C verifikator dan keamanan, I produk. Label: A pemilik proses verifikasi, R verifikator, C backend/data, I produk. Baseline dan ML: A dan R backend/data, C verifikator, I produk dan pemilik data. Shadow/pilot: A pemilik proses dan pemilik data sesuai kewenangan, R operasi/backend, C keamanan dan verifikator, I produk. Setiap peran A harus ditetapkan sebelum gate dijalankan.

