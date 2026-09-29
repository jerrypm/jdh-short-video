# Task 03 — memori konten lokal

22 September 2026. Implementasi Task 03 tersedia dalam aplikasi 0.2.3 (build 5). Task 04 dan seterusnya belum dijalankan.

## Yang ditambahkan

- Halaman **Memori konten**: pemilihan proyek, include/exclude, kategori konten/QA/duplikat, koreksi label dan penghapusan referensi.
- Profil channel; tema, audiens, bahasa, seri, ringkasan, hook, format, durasi, asset ID, feedback ide, serta status draft/exported/published dengan asal data yang jelas.
- Katalog SQLite lokal dengan schema version, revision guard, transaksi dan pemulihan write yang terputus. Manifest dan media proyek tidak dimigrasikan atau ditulis oleh katalog.
- Retrieval lokal berdasarkan kata kunci, tema, bahasa, seri, recency dan keragaman, dengan jumlah referensi dan ukuran konteks dibatasi.
- Metadata terukur, konfirmasi pengguna dan dugaan AI dipisahkan. Task ini tidak menjalankan inference atau provider pengganti. Ringkasan kosong menggunakan cuplikan naskah yang diberi label secara jelas.

Panduan dan batas teknis: [content-memory.md](content-memory.md).

## Pengujian

| Pemeriksaan | Hasil | Bukti |
| --- | --- | --- |
| Katalog kosong, opt-in, proyek schema-v1 lama | PASS | Tes backend memakai folder sementara. Proyek tidak dipilih tidak masuk katalog. |
| Revision refresh, koreksi label, konflik form lama | PASS | Metadata sumber berubah, label pengguna bertahan, penyimpanan stale ditolak. |
| QA/duplikat/exclude/sumber hilang | PASS | Tidak ikut retrieval; duplikat konten didedup walau diberi kategori konten. |
| Export vs published | PASS | Receipt render completed membuat exported; publikasi memerlukan konfirmasi eksplisit. |
| Hapus referensi/feedback tanpa menghapus proyek/media | PASS | Manifest dibandingkan dan media dipastikan tetap ada. |
| Restart proses | PASS | Proses Python baru memuat profil, label dan feedback dari disk. |
| Write gagal dan proses berakhir sebelum commit | PASS | Transaksi rollback dan katalog sebelumnya tetap terbaca. |
| Database rusak, dokumen invalid, versi masa depan | PASS | Gagal jelas, tanpa reset ke katalog kosong. |
| Retrieval/filter/ranking/keragaman/batas konteks | PASS | Tes metadata terisolasi. Dugaan AI tidak dipromosikan menjadi fakta. |
| Auth/origin/CSRF, chunked body, input/output milik server | PASS | Tes API. |
| Runtime dari bundle `.app`, restart dan media asli | PASS | [12 pemeriksaan runtime](qa/content-memory-runtime.json), dua proses sidecar dari bundle, impor PNG sungguhan, manifest/media tetap identik setelah referensi dihapus. |
| Build Swift/Next, TypeScript, lint Python | PASS | Build 0.2.3 dan pemeriksaan kode. |
| Tampilan/interaksi native Task 03 | BELUM DIVERIFIKASI | Computer Use melaporkan Mac terkunci. Pengguna diminta membuka kunci; pemeriksaan runtime dilanjutkan secara terisolasi. |

Total tes otomatis: **52 lulus** — 38 backend (14 baru untuk memori) dan 14 frontend. Suite backend tetap mencakup render FFmpeg dan roundtrip paket; frontend mencakup regresi audio preview. Dua peringatan deprecation TestClient/httpx tidak menyebabkan kegagalan.

## Batas dan artefak

- Aplikasi: `dist/JDH Shorts Studio.app`, 0.2.3 build 5, Apple Silicon/macOS 26+, ad-hoc signed.
- Aplikasi `/Applications` dan DMG lama tidak diganti. Installer baru berada di task distribusi berikutnya.
- Tidak mengakses akun kerja, tab browser, riwayat browsing, proyek/media pengguna untuk fixture, analytics YouTube, atau layanan AI cloud.
- QA visual masih diperlukan saat Mac terbuka: pilih referensi, simpan profil/label, include/exclude, cari konteks, lalu hapus referensi dan cek proyek tetap ada.
- Ini fondasi memori; ide otomatis saat membuka aplikasi merupakan Task 04. Kendala verifikasi Nano nyata dari Task 02 tidak dinyatakan selesai oleh tes katalog ini.
