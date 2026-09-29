# Performa video lokal — Task 10

Buka **Performa video** dari beranda. Input manual atau impor CSV, petakan setiap baris ke proyek, lalu **Pratinjau** dan konfirmasi **Simpan pengukuran**. Tidak ada koneksi akun/OAuth, pembacaan channel, sinkronisasi, atau unggah data. Semua pengukuran berasal dari input yang ditinjau pengguna; aplikasi memvalidasi bentuk, rentang dan referensinya, bukan mengautentikasi angka ke YouTube.

## Isi data

Template CSV dapat diunduh dari halaman tersebut. UTF-8, pemisah koma, desimal titik, tanpa tanda persen/pemisah ribuan; maksimal 40 KB/100 baris sekali impor, 1.000 snapshot tersimpan. Header lain/duplikat ditolak agar ekspor Studio dengan definisi berbeda tidak dipetakan diam-diam. `project_id` boleh kosong saat parsing dan harus dipilih sebelum pratinjau.

| Kolom | Makna |
|---|---|
| project_id | ID proyek lokal, atau petakan lewat pilihan proyek setelah parsing |
| video_id | YouTube video ID 11 karakter; satu video hanya boleh dipetakan ke satu proyek |
| published_on | Tanggal publikasi menurut zona waktu laporan, YYYY-MM-DD |
| period_start / period_end | Tanggal pengukuran inklusif, bukan sebelum publikasi atau sesudah pengambilan |
| report_timezone | Zona IANA laporan; periksa sumber, jangan memakai zona perangkat secara otomatis |
| captured_at | Waktu pengambilan ber-offset, misalnya `2024-01-09T07:00:00+07:00` |
| definition | `youtube_engaged_views_v1` atau `custom` |
| definition_note | Wajib untuk `custom`; menjelaskan definisi/batas laporan |
| source | Nama sumber/ekspor yang dapat ditelusuri pengguna, maksimal 120 karakter |
| engaged_views | Bilangan bulat; **bukan** substitusi total Views |
| average_view_duration_seconds | Durasi tonton rata-rata dalam detik |
| average_view_percentage | Persentase ditonton; dapat lebih dari 100% |
| likes / comments / shares | Bilangan bulat jika tersedia dalam laporan |

Kosong adalah `null`/tidak tersedia; angka `0` adalah pengukuran nol. Minimal satu metrik harus tersedia. Jangan mengubah nilai kosong menjadi nol atau menurunkan rasio dari metrik yang definisinya berbeda. Sumber dan timestamp pengambilan tetap disimpan, ditambah asal manual/CSV dan waktu penyimpanan lokal.

Definisi metrik merujuk [dokumentasi YouTube Analytics](https://developers.google.com/youtube/analytics/metrics): engaged views, average view duration, dan average view percentage memiliki makna masing-masing; ketersediaan tergantung jenis laporan. Template ini merupakan kontrak impor aplikasi, bukan klaim kompatibilitas langsung dengan setiap ekspor YouTube Studio. Masukkan angka laporan tingkat video, bukan playlist/channel.

## Duplikat, koreksi dan anomali

Identitas snapshot memakai video, periode, zona, definisi dan catatan definisinya. Impor ulang angka identik dilewati meskipun nama file/waktu pengambilan berbeda; provenance lama tetap dipertahankan. Angka berbeda pada snapshot sama ditandai konflik. Pilih opsi koreksi, periksa data lama/baru, kemudian simpan. Periode lain adalah snapshot baru. Koreksi mengganti snapshot tersebut, tanpa riwayat versi angka yang lengkap.

Satu batch diterapkan atomik dengan revision guard. Pratinjau tidak menulis pengukuran dan kedaluwarsa setelah 15 menit atau restart. Retry penyimpanan dengan receipt yang sama bersifat idempoten. Impor gagal tidak menyimpan sebagian baris.

**Kecualikan video** menyimpan alasan dan mengabaikan seluruh periode video itu dalam ringkasan maupun konteks ide. Impor berikutnya mewarisi pengecualian sampai pengguna memilih **Sertakan video**. Data tetap terlihat. Penghapusan/pengecualian referensi Memori juga mencegah penggunaannya oleh Nano, tetapi tidak menghapus pengukuran manual yang dicatat terpisah.

## Membaca ringkasan

Hanya satu snapshot terbaru per video dipakai, berdasarkan tanggal akhir, lalu awal, waktu pengambilan, dan ID sebagai pemecah seri. Periode tumpang tindih tidak dijumlahkan. Kelompok hanya menggabungkan definisi/catatan, zona waktu, umur video pada awal pengukuran, dan panjang periode yang sama. Tanggal kalender, faktor musim, sumber trafik dan faktor lain tetap dapat berbeda; ini bukan kelompok eksperimen terkontrol.

Median per metrik baru muncul setelah **5 video berbeda dengan metrik tersebut tersedia**. Ini ambang konservatif produk, bukan signifikansi statistik. Median menggambarkan video, bukan rata-rata penonton gabungan. Sampel kecil hanya menampilkan pengukuran individual. Tidak ada skor viral, peringkat sebab-akibat, atau janji peningkatan performa.

## Ide Gemini Nano

Proyek harus dipilih sebagai referensi aktif kategori konten di **Memori konten**. Konteks ide memakai maksimal 5 snapshot terbaru yang disertakan dari referensi yang terambil, dibatasi 3.300 karakter. Proyek hilang, tidak dipilih, berbeda bahasa dari retrieval, kategori QA/duplikat, dan video yang dikecualikan tidak dikirim sebagai konteks.

Nano menerima teks angka/provenance saja melalui companion lokal yang sudah ada. Prompt memperlakukan semua kolom sebagai data, menuntut hipotesis yang hati-hati dan tetap tiga kategori: seri, sudut baru, eksperimen. Jika angka tersedia, minimal satu ide harus mencantumkan ID bukti performa dan proyek yang sesuai. Broker dan companion menolak ID bukti yang dibuat-buat. Kartu menampilkan angka sumber, periode, definisi, umur video dan waktu pengambilan; alasan model tetap perlu ditinjau, bukan fakta sebab-akibat yang telah terbukti.

Perubahan angka/pengecualian membatalkan inference aktif dan cache lama dalam transaksi penyimpanan yang sama. Ide yang sengaja disimpan tetap ada dengan tanda data berubah, dan tidak dapat dipakai untuk draft sampai dibuat ulang. Metadata ini tidak mengubah manifest proyek, preview audio, render, Undo/Redo, atau status publikasi.

## Penyimpanan dan pemulihan

Tabel `performance` berada di `_memory/catalog.sqlite3`, bersama katalog dan ide. Migrasi SQLite v1/v2 → v3 bersifat aditif dan atomik; schema JSON masing-masing tetap versi 1. Data rusak/versi database masa depan ditolak dan dipertahankan. Jangan membuka database hasil v3 memakai aplikasi 0.2.9: aplikasi lama menolak versi yang lebih baru. Cadangkan direktori proyek saat aplikasi berhenti sebelum mengganti versi jika perlu rollback. Pengukuran ini belum ikut ZIP ekspor proyek individual.
