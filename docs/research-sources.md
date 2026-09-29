# Sumber riset untuk ide Nano lokal

Fitur ini tersedia pada **0.2.11 (13)**. Dari beranda, buka **Sumber riset**. Tambahkan catatan manual atau URL HTTPS publik, tinjau isinya, lalu simpan. Pada **Ide hari ini → Preferensi → Dasar ide**, pilih **Referensi riset · sumber pilihan** dan simpan preferensi. Tekan **Ide baru** ketika companion Nano lokal siap.

## Dua mode ide

- **Riwayat video & performa** memakai proyek yang dipilih dalam Memori dan pengukuran yang disertakan. Mode harian/manual yang sudah ada tetap berlaku.
- **Referensi riset** memakai catatan sumber yang ditinjau, topik/audiens, dan feedback riset yang masih berlaku. Mode ini selalu dijalankan manual. Tidak mencampur riwayat proyek atau angka performa, tidak mencari web otomatis, dan tidak mengambil URL saat membuat ide.

Kedua mode tetap memakai Gemini Nano lokal melalui companion Chrome yang dipasangkan. Tidak ada Gemini API/cloud, API key, akun, OAuth, pembacaan email/tab/cookie, unggah atau publikasi otomatis. Nano English tetap jalur yang tersedia pada integrasi ini; tidak ada model Indonesia baru. Catatan dan pengeditan manual dapat dipakai offline. Inferensi offline memerlukan model yang sudah tersedia serta companion lokal yang dapat diakses.

## Meninjau sumber

Catatan menyimpan judul, URL opsional, tanggal publikasi bila diketahui, tanggal akses/peninjauan, ringkasan atau cuplikan, batasan dan keputusan penyertaan. Tanggal publikasi tidak boleh sesudah tanggal akses; tanggal akses tidak boleh di masa depan. Jangan mengisi tanggal publikasi dengan tanggal akses bila tidak diketahui. Tanggal tak diketahui ditampilkan secara eksplisit dan bukan bukti keterkinian.

Tombol **Ambil cuplikan URL** menghubungi situs itu tanpa sesi browser. Hasilnya hanya pratinjau: metadata tanggal bisa tidak lengkap atau salah, dan isi hanyalah cuplikan awal halaman, bukan ringkasan terverifikasi. **Pakai di formulir untuk ditinjau** tidak menyimpannya. Periksa/edit formulir, centang konfirmasi pemeriksaan, lalu simpan. Setiap perubahan formulir menghapus centang konfirmasi sebelumnya. Jika fetch gagal, formulir dipertahankan dan catatan manual tetap tersedia.

Hanya sumber yang disertakan dan layak digunakan. Tanggal publikasi **atau** akses yang lebih dari 30 hari membuat sumber tidak layak untuk ide terkini; sumber tetap disimpan. Batas 30 hari adalah aturan produk, bukan penilaian mutu ilmiah. Paling banyak tiga catatan terbaru dikirim ke Nano, masing-masing 700 karakter awal dari maksimum 1.200 karakter yang disimpan. Simpan ringkasan singkat agar konteks penting tidak terpotong.

URL yang sama setelah normalisasi dasar ditolak; perbarui catatan yang ada. Isi identik pada URL berbeda diberi tanda duplikat sehingga tidak dihitung sebagai bukti tambahan. Aplikasi tidak dapat mendeteksi semua sindikasi, parafrasa atau duplikasi semantik.

Jika dua sumber bertentangan, pilih sumber pasangannya dan jelaskan konfliknya. Keduanya dikeluarkan dari konteks sampai pengguna menyelesaikan konflik melalui peninjauan. Menghapus salah satu pasangan tidak otomatis mengesahkan yang tersisa: sumber tersisa dikecualikan untuk ditinjau kembali. Konflik ditandai pengguna, bukan dideteksi otomatis oleh model.

## Kutipan pada kartu

Setiap ide riset wajib memiliki setidaknya satu klaim dengan ID sumber valid dan kutipan persis dari teks yang diberikan ke Nano. Buka **Dasar riset** pada kartu untuk membaca klaim, cuplikan, judul, URL, tanggal dan batasannya. Kutipan ringkasan pengguna diberi label berbeda dari cuplikan sumber.

Pemeriksaan otomatis memastikan ID dan kecocokan teks; pemeriksaan itu **tidak membuktikan bahwa klaim benar atau didukung secara semantik**. Semua klaim tetap perlu diperiksa. Prompt meminta model mengaitkan setiap pernyataan faktual dengan sumber, mempertahankan ketidakpastian, dan tidak menyebut satu artikel sebagai tren atau menjanjikan performa video. Konten sumber selalu ditempatkan sebagai data tidak tepercaya, bukan instruksi. Ketahanan model terhadap prompt injection masih perlu dibuktikan dengan Nano nyata.

Perubahan pustaka membatalkan permintaan ide riset yang aktif dan cache riset. Kartu yang disimpan tetap ada dengan tanda perlu diperbarui; penyusunan draft diblokir sampai ide dibuat ulang. Kedaluwarsa juga menghapus kelayakan tanpa perlu edit. Ide berbasis riwayat tidak dibatalkan hanya karena pustaka riset berubah. Proposal ide tidak langsung mengubah proyek; storyboard tetap melalui alur tinjau/terapkan yang sudah ada.

## Batas pengambilan URL

HTTPS port 443 saja; maksimal 256 KiB, 10 detik untuk keseluruhan fetch dan paling banyak tiga redirect. Ada batas dua fetch serta dua resolver bersamaan, dengan waktu tunggu DNS maksimal tiga detik. Setiap redirect dan seluruh alamat hasil DNS diperiksa; koneksi dipasang ke IP publik yang sudah divalidasi dengan hostname TLS asli dan pemeriksaan sertifikat tetap aktif. Watchdog menutup socket pada deadline, termasuk selama TLS/header/body dibaca.

Alamat privat, loopback, link-local, multicast, rentang nonpublik, skema file, URL berkredensial dan domain lokal ditolak. Tidak memakai proxy lingkungan, autentikasi, cookie, JavaScript atau browser. Hanya HTML/teks tanpa kompresi; PDF/media/login dinamis tidak diterobos. Parser membuang elemen script/style/navigasi umum tetapi bukan pembaca artikel penuh. Situs dapat menolak klien ini; tempel catatan manual bila halaman tidak terbaca.

## Penyimpanan dan versi

Pustaka lokal maksimal 200 sumber disimpan pada tabel `research` dalam katalog SQLite yang sama dengan memori, ide, dan performa. Migrasi menambah tabel dari v3 ke **v4** tanpa mengubah manifest proyek. Penulisan sumber dan invalidasi ide berada dalam satu transaksi dengan pemeriksaan revisi; kegagalan membatalkan keduanya. Format tidak dikenal/rusak ditolak dan dipertahankan untuk pemulihan.

Sebelum memakai versi baru pada proyek asli, tutup aplikasi dan cadangkan folder proyek lengkap. Aplikasi lama tidak mendukung katalog v4. Untuk kembali ke versi lama, gunakan salinan cadangan pra-migrasi yang terpisah; jangan mengubah nomor versi database secara manual. Hasil QA memakai folder sementara dan tidak memigrasikan proyek pribadi.
