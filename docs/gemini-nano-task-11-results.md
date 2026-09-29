# Task 11 — sumber riset untuk ide lokal

Tanggal: 28 September 2026. Implementasi **0.2.11 (13)** selesai. Ini adalah task fitur terakhir dari rencana 01–11; pemeriksaan rilis yang belum selesai tercatat di bawah. Provider tetap **Gemini Nano lokal melalui companion Chrome**.

## Perubahan

- Halaman **Sumber riset**: catatan manual offline, fetch HTTPS eksplisit dengan pratinjau, tinjau/edit sebelum simpan, metadata sumber dan batasan, serta pustaka sumber yang bisa dikecualikan.
- Mode **Referensi riset** terpisah dari ide berbasis riwayat/performa dan selalu manual. Hanya tiga sumber layak terbaru, masing-masing 700 karakter awal, dikirim ke companion lokal.
- Sumber lebih dari 30 hari, duplikat dan konflik yang ditandai pengguna dikeluarkan dari konteks. Tanggal publikasi yang tidak diketahui tidak dianggap sebagai bukti keterkinian. Penghapusan pasangan konflik mengharuskan peninjauan sumber yang tersisa.
- Output ide wajib membawa klaim, ID sumber dan kutipan persis dari catatan yang diberikan. Kartu menampilkan sumber/tanggal/URL/batasan. Kecocokan teks divalidasi backend dan companion; kebenaran dan dukungan semantik tetap harus diperiksa pengguna.
- Perubahan sumber membatalkan ide riset aktif/cache, menandai kartu tersimpan sebagai usang dan mencegah penyusunan storyboard dari bukti usang. Perubahan riset tidak membatalkan ide riwayat. Tidak ada perubahan proyek otomatis.
- SQLite katalog v3 → v4 menambah pustaka riset. Revisi sumber dan invalidasi ide ditulis dalam satu transaksi. Format masa depan/rusak ditolak tanpa ditimpa.
- Pengambilan URL dibatasi ukuran/waktu/redirect/konkurensi. DNS harus seluruhnya publik, IP dipasang ke koneksi, hostname serta pemeriksaan TLS tetap aktif, dan deadline mencakup handshake/header/body. Tidak membaca sesi browser, proxy lingkungan, cookie atau akun.

Panduan lengkap, batas produk, dan pemulihan versi: [research-sources.md](research-sources.md).

## Validasi

- **273 tes lulus**: 223 backend, 29 frontend, 21 companion JavaScript. Mencakup alur riset, review gate, konflik dua arah, duplikasi, kedaluwarsa, mode terpisah, rollback, migrasi, invalidasi, kutipan palsu, ID asing, URL/DNS privat, ukuran/jenis respons dan deadline TLS. Tes regresi audio preview tetap lulus. Dua warning deprecation berasal dari dependensi TestClient/AnyIO.
- `ruff check backend script`, TypeScript, Next production static build dan Swift release build berhasil.
- **15 pemeriksaan runtime bundle** lulus melalui Python bawaan `.app`, HTTP loopback nyata, dan restart proses: penolakan URL privat, review wajib, sumber tersimpan, mode manual, konteks tanpa riwayat/performa, respons fixture dengan kutipan, sumber pada kartu, feedback, invalidasi, manifest proyek tetap utuh, serta persistence setelah restart. Laporan: `dist/JDH-Shorts-Studio-0.2.11-research-check.json`.
- Satu smoke test HTTPS nyata ke halaman publik `https://example.com/` berhasil, menghasilkan judul dan 127 karakter teks dalam sekitar 0,26 detik, tanpa menyimpan sumber atau memakai cookie. Ini membuktikan jalur koneksi/TLS dasar, bukan kompatibilitas semua situs.
- Aplikasi diluncurkan dengan `--isolated-qa` dan data sementara. **Computer Use tertahan karena Mac terkunci**; permintaan buka kunci disampaikan. UI WebKit Task 11 belum dapat diverifikasi, sehingga tidak ada klaim mengenai screenshot, layout atau kesehatan console frontend.
- Pemeriksaan tanda tangan dan kesamaan source/bundle dicatat dalam `dist/JDH-Shorts-Studio-0.2.11-task11-check.json`.

## Batas dan pekerjaan rilis yang tersisa

Tes Nano pada task ini menggunakan fixture transport dan fake LanguageModel. **Inference Gemini Nano nyata, kualitas kutipan/rekomendasi dan ketahanan model terhadap instruksi berbahaya belum terverifikasi pada integrasi ini.** Percobaan Chrome pada Task 10 menghasilkan `ERR_BLOCKED_BY_CLIENT`; Task 11 tidak mengubah proteksi browser atau menambahkan cloud fallback. Task 01 pernah memverifikasi inferensi English pada prototipe, bukan seluruh alur aplikasi terbaru.

Masih perlu: buka kunci dan periksa UI Task 11, selesaikan validasi companion Nano nyata, perbarui DMG dari bundle terbaru, lalu uji instalasi pada Mac mini tujuan. **DMG yang sudah ada tetap 0.2.9**, belum memuat Task 10–11. `.app` terbaru 0.2.11 masih ad-hoc signed, bukan Developer ID/notarized. Jangan downgrade katalog v4 menggunakan aplikasi lama; gunakan cadangan pra-migrasi yang terpisah.

Tidak ada pencarian web otomatis, verifikasi fakta otomatis, deteksi konflik semantik otomatis, atau klaim bahwa satu artikel adalah tren. Pengujian dan runtime menggunakan proyek disposable, tanpa mengakses akun kerja, channel YouTube atau proyek pribadi.
