# Pemeriksaan Shorts dan paket unggah

Tersedia mulai **0.2.8 build 10**. Semua pengukuran dan ekspor berjalan lokal. Gemini Nano lokal hanya dipakai saat pengguna meminta saran editorial melalui companion Chrome yang dipasangkan.

## Alur pengguna

1. Buka **Ekspor**, pilih Draft 360×640 atau Final 1080×1920, lalu **Periksa Shorts**. Pemeriksaan memakai revisi proyek yang sudah disimpan dan tidak mengubah proyek.
2. Tinjau temuan per scene/rentang waktu. Kesalahan harus diperbaiki; peringatan perlu ditinjau sesuai tujuan video. Perubahan preset, proyek, media, atau pengaturan memerlukan pemeriksaan ulang.
3. Opsional: **Minta saran Nano lokal** untuk hook, pengulangan, pacing dan maksud visual berdasarkan teks. Setiap saran memiliki scene, rentang waktu dan alasan. Judul/deskripsi AI hanya masuk ke usulan setelah **Gunakan sebagai usulan metadata**.
4. Edit judul/deskripsi, posisi caption, volume narasi/musik, atau pilih scene yang ingin diperbaiki durasi/caption-nya. **Tinjau perubahan** menampilkan nilai sebelum/sesudah; **Terapkan perubahan yang ditinjau** menyimpan usulan yang sama secara atomik. Edit sesudah review membatalkan review sebelumnya. Undo/Redo tersedia di editor.
5. Periksa ulang sesudah apply, centang konfirmasi tinjauan, lalu ekspor. File MP4 diverifikasi dengan probe, jumlah frame dan decode penuh. Periksa video/suara hasil sebelum unggah manual.

Input angka mempertahankan ketikan sementara, lalu memvalidasi batas ketika fokus berpindah atau Enter ditekan. Ini memungkinkan mengetik nilai seperti 65 tanpa mengubah digit pertama menjadi batas minimum.

## Pengukuran dan batasnya

| Pemeriksaan | Metode dan batas |
| --- | --- |
| Media | Memeriksa seluruh aset terdaftar, termasuk media yang belum dipakai, karena arsip proyek harus lengkap. |
| Narasi terpotong | Durasi PCM hasil decode dan source trim dibandingkan dengan frame scene. Narasi usang atau tidak dapat diukur dilaporkan; pemendekan yang memotong audio ditolak. |
| Audio | Decode float PCM stereo 48 kHz; puncak absolut dihitung pada kedua kanal. Campuran diperiksa dengan gain, trim dan loop musik proyek, sebelum limiter musik ekspor. Hasil ekspor diukur kembali. |
| Jeda | Maksimum level pada jendela 10 ms; bagian di bawah ambang cukup lama diberi rentang waktu. Sisa waktu setelah akhir narasi juga ditandai. Ini bukan pengenalan kata atau penilaian jeda yang artistik. |
| Caption | Font/layout yang sama dengan renderer, batas dua baris, lebar/canvas, posisi relatif terhadap guide editor dan karakter per detik. |
| Caption/callout bertumpuk | Bounding box, termasuk pointer, diperiksa pada seluruh frame dengan entrance motion. Kotak transparan tidak diuji sebelum terlihat. Bounding box dapat memberi peringatan meski piksel teks tidak bersentuhan. |
| Output | Sebelum ekspor: rencana dimensi/durasi. Sesudah ekspor: dimensi file, 30 fps, jumlah frame timeline, durasi container, decode penuh dan metrik audio aktual. |

Puncak sampel **bukan true peak, LUFS atau bukti distorsi**. Gain rendah tidak memperbaiki rekaman yang sudah terdistorsi. Audio AAC dapat memiliki padding kecil di akhir; durasi PCM decode dicatat terpisah dari durasi video. Tidak ada analisis objek, OCR isi gambar, alignment kata atau penilaian estetika visual otomatis.

| Pengaturan produk | Default | Rentang |
| --- | --- | --- |
| Jeda panjang | 1,5 detik | 0,5–10 detik |
| Ambang sunyi | −40 dBFS | −60 sampai −20 dBFS |
| Peringatan puncak sampel | −0,1 dBFS | −6 sampai 0 dBFS |
| Kecepatan caption | 20 karakter/detik | 5–40 |

Angka ini adalah pengaturan produk yang dapat diedit dan disimpan per proyek, bukan aturan YouTube atau jaminan kelayakan publikasi. Tidak ada skor viral atau janji views.

## Saran Gemini Nano lokal

Provider tetap companion **Gemini Nano lokal**, tanpa cloud fallback atau API key. Dukungan yang dipakai saat ini hanya teks English. Nano menerima konteks JSON terbatas: naskah, caption, scene/rentang frame, deskripsi visual yang ditulis pengguna dan ringkasan temuan. Naskah panjang dipotong dengan penanda; konteks terlalu besar ditolak.

Nano **tidak melihat frame dan tidak mendengar audio**. Catatan `visual_intent` hanya membahas deskripsi visual pengguna. Output harus lolos schema ketat: judul, deskripsi, maksimal delapan saran dengan kategori, scene, rentang waktu dalam scene, isi dan alasan. Field tambahan seperti skor ditolak. Temuan teknis tidak berasal dari model.

Pembatalan mengirim ID request yang sama meski respons submit belum diterima. Render/TTS/analisis teknis dapat menunda pekerjaan editorial aktif. AI tidak mengubah proyek atau memublikasikan apa pun secara otomatis. Pengujian inference nyata pada build terintegrasi masih perlu diselesaikan; lihat [hasil Task 08](gemini-nano-task-08-results.md).

## Konsistensi dan penyimpanan

Metadata dan pengaturan bersifat tambahan pada schema proyek v1; proyek lama mendapat default. Review terikat ke revisi proyek, preset dan signature stat seluruh aset. Laporan aktif hanya disimpan dalam memori: maksimal delapan, berlaku 15 menit, dan tidak dapat dipakai untuk apply sesudah restart. File laporan hasil ekspor tetap tersedia di folder job.

Apply mensyaratkan pilihan yang persis sama dengan preview terakhir. Atomic save, backup, optimistic revision check dan retry idempoten mempertahankan perlindungan penyimpanan yang sudah ada. Render mengecek signature media sebelum dan sesudah bekerja. Signature ini tidak menggantikan hash isi untuk perubahan file yang sengaja mempertahankan seluruh atribut stat.

UI mewajibkan laporan terbaru tanpa kesalahan dan tinjauan pengguna. API render lama tetap menerima request tanpa `check_id` untuk kompatibilitas; paketnya mencatat `pre_export_checked: false`. Validasi renderer dan verifikasi file hasil tetap berjalan.

## File hasil

- `draft.mp4` atau `final.mp4`: H.264/AAC, 30 fps.
- `narration.wav`, `captions.srt`, `project.json`, `project.zip`: keluaran editor/arsip sumber yang sudah ada; SRT berisi cue per scene.
- `upload-metadata.json`: judul/deskripsi yang disimpan, bahasa, revisi, preset dan verifikasi file. Judul kosong memakai nama proyek.
- `upload-notes.txt`: judul/deskripsi untuk disalin saat unggah manual.
- `quality-report.json`: temuan sebelum ekspor dan verifikasi output, dipisahkan secara eksplisit.
- `upload.zip`: MP4, metadata, catatan dan laporan; SRT disertakan bila tidak kosong.

`project.zip` untuk melanjutkan editing beserta media sumber; `upload.zip` untuk menyerahkan hasil akhir. Tidak ada login, koneksi akun, penjadwalan atau unggah YouTube otomatis.
