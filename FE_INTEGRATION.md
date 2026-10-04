# Integrasi frontend

Frontend sebelumnya hanya berupa desain Figma, bukan repo kode. Pengguna kemudian memperluas scope untuk implementasi FE, proposal, dan publikasi GitHub. File Figma dan halaman Notion tidak diubah.

| Kondisi desain | Implementasi |
| --- | --- |
| Unggah awal | Pilih file dan drag/drop ke POST /api/v1/datasets/upload |
| Format salah / kosong | Error server FILE_FORMAT / FILE_EMPTY dan tombol pilih ulang |
| Koneksi gagal | Error fetch dan retry file yang sama |
| Sedang diproses | Indikator indeterminate selama upload/validasi, bukan persentase server fiktif |
| Validasi | Ringkasan CSV aktual; valid format dapat mencakup baris klinis belum lengkap |
| Data siap | Data upload nyata, lanjut membuka antrean |
| Antrean | GET /cases, filter tingkat/fasilitas/alasan/status, sort, pagination; pilihan lengkap dari /facets |
| Bandingkan | GET /cases/{id}; tujuh field sesuai layout desain, tanda sama/berbeda, kronologi |
| Alasan dan keputusan | Kontribusi, reducer berbukti, informasi kurang, catatan dan tiga keputusan |
| Tersimpan | Audit persisted, revisi dengan versi, retry idempotent, sisa antrean dan next case |
| Semua selesai | Tidak menampilkan next case kosong; kembali antrean atau evaluasi |
| Evaluasi | GET /evaluation; tanpa label memakai benchmark internal yang diberi keterangan sumber |

## Koreksi konten, bukan redesain

Warna, kartu, urutan layar, perbandingan dua kolom, pilihan keputusan, dan navigasi bawah mengikuti referensi. Angka 2.448/117/92 serta 30/85/82% pada mockup diganti hasil aktual. ID `SYN-` dan nama file datang dari CSV. Tidak ada pengakuan akurasi JKN atau label fraud terdeteksi.

Catatan keputusan menjadi textarea di panel yang sama. Indikator proses tidak mengarang 65%. Ketiadaan pembatalan bukan faktor penurun skor; hanya bukti yang memenuhi guardrail ditampilkan. Waktu per metode belum tersedia (N/A), terpisah dari median telaah dataset. Beranda mengarah ke titik awal unggah karena desain yang diberikan tidak berisi halaman Beranda terpisah; bel menampilkan penjelasan prototype, bukan notifikasi palsu.

## Sesi dan penyimpanan

UI dan API same-origin melalui satu FastAPI. Cookie HttpOnly berumur maksimal 8 jam, CSRF wajib untuk mutasi, origin dan host loopback diperiksa. Tidak ada bearer dalam frontend. `localStorage` hanya menyimpan metadata dataset aktif, bukan token atau isi klaim. Data/audit utama berada di SQLite; reload mengambil status dari API. Sesi kembali dibuat setelah restart server.

## Bukti dan keterbatasan

80 tes Python dan dua suite browser tersedia di docs/qa. Tampilan diperiksa pada 390 dan 1280 px; konten panjang bergulir di main sehingga navigasi tidak menutupinya. Tidak ada perubahan file Figma. Detail internal prototype dan ukuran piksel dari inspect Figma tidak tersedia pada viewer tamu, sehingga pixel-perfect tidak diklaim. Uji pengguna belum dilakukan.
