# Timing dan caption lokal

Task 06, build 0.2.6. Di editor, pilih **Timing & caption → Analisis timing**. Analisis tidak mengubah proyek dan tidak memanggil model AI. Provider AI aplikasi tetap Gemini Nano lokal.

## Review

- Setiap scene menampilkan durasi file narasi yang tersisa setelah trim yang sudah ada, jeda yang terdeteksi, dan ruang kosong setelah file berakhir.
- Durasi usulan mempertahankan durasi scene saat ini; scene yang terlalu pendek diperpanjang hingga seluruh audio muat. Jeda awal, tengah, dan akhir **di dalam file audio tidak dipotong**.
- **Pas dengan seluruh audio** mengurangi ruang tambahan setelah file berakhir. Pengguna memilih tindakan ini secara eksplisit; tambah frame lagi untuk mempertahankan jeda kreatif. Field durasi menggunakan frame, dengan padanan detik ditampilkan (30 fps).
- Caption dapat diperbaiki manual. Enter mempertahankan pilihan pemisahan baris. Satu paragraf panjang dibagi berdasarkan lebar font aktual dan diseimbangkan jika dapat menjadi dua baris.
- Pilih scene, tekan **Periksa perubahan**, baca ringkasan durasi dan caption, lalu **Terapkan perubahan**. Edit apa pun menghapus review sebelumnya. Menutup dialog tidak menerapkan proposal.
- Apply memakai atomic save, backup versi sebelumnya, revision guard, dan Undo/Redo editor. Perubahan proyek atau file media membatalkan proposal. Proposal berlaku 15 menit, maksimal delapan dalam memori, dan hilang setelah sidecar dimulai ulang.

## Pengukuran dan batas

FFmpeg yang sudah dibundel mendekode sisa narasi menjadi PCM stereo 16 kHz. Durasi dihitung dari jumlah sampel dan dibulatkan ke atas ke frame 30 fps; minimum juga mempertahankan batas konservatif metadata impor. Analisis dibatasi 60 detik per scene, satu analisis bersamaan, maksimal 10 detik decode per file dan anggaran decode total 45 detik. File/trim yang gagal diukur ditandai; proposal untuk scene tersebut tidak dapat diterapkan.

Jeda adalah jendela peak 10 ms pada kedua channel dengan ambang −40 dBFS selama minimal 250 ms. Ini bukan deteksi kata atau pemahaman ucapan: suara pelan dapat ditandai sebagai jeda, musik/noise dapat menyembunyikan jeda. Tidak ada pemotongan berdasarkan hasil deteksi. Pengukuran stereo diuji dengan channel berlawanan fase agar suara tidak hilang karena downmix mono.

Caption memakai font bundled yang sama dengan PNG preview/ekspor, batas lebar 850 px pada kanvas 1080 px, dan maksimal dua baris. Lebih dari 20 karakter/detik atau tampil kurang dari satu detik menghasilkan peringatan, bukan keputusan otomatis. Angka ini heuristik produk, bukan standar aksesibilitas atau dukungan bahasa yang telah divalidasi. Panjang caption yang melampaui area dua baris menahan apply sampai teks/ukuran diperbaiki.

PNG dan SRT memakai layout baris yang sama. Timestamp SRT berasal dari penjumlahan frame scene, bukan prediksi Nano. Caption nonaktif tidak diekspor ke SRT. Koreksi manual dan caption per scene tetap menjadi alur utama; **tidak ada ASR, forced aligner, cue per ujaran, timestamp kata, atau model tambahan**. Dengan demikian tidak ada tambahan ukuran model, lisensi model, maupun dependency produk pada Task 06.

Durasi video yang kurang menahan apply; pengguna perlu mengganti visual atau menyesuaikan panjangnya. Batas proyek tetap 180 detik. Teks narasi yang berubah sejak audio dibuat ditandai dan preflight ekspor tetap meminta pembaruan narasi. Trim yang sudah dibuat pengguna dipertahankan, sehingga awal ucapan pada titik trim perlu diperiksa manual.

## Preview dan ekspor

Preview mempertahankan media clock native; tidak ada play/seek pada setiap render frame. Encoding per scene di ekspor kini menggunakan PCM dalam MOV, kemudian AAC satu kali setelah penggabungan. Ini mencegah delay AAC per scene menumpuk. Intermediate audio memerlukan sekitar 35 MB tambahan untuk proyek stereo 48 kHz sepanjang 180 detik; hasil akhir tetap H.264/AAC MP4.

Uji fixture membandingkan onset pada timeline preview dengan PCM/WAV dan MP4 draft/final. Pengukuran onset menggunakan jendela 10 ms; itu bukan bukti sinkronisasi speaker atau layar pada semua perangkat. Browser/OS dapat menambah startup latency, dan AAC dapat memiliki padding di akhir hasil decode. Native WebKit pada build ini serta Mac mini tujuan belum diuji ulang. Bahasa yang benar-benar diuji dengan suara adalah English Kokoro; tidak ada klaim alignment multilingual.

Jalankan pemeriksaan runtime dengan `.venv/bin/python script/verify_pacing_runtime.py`; script menjalankan Python bundle pada data sementara, membuat fixture PCM dan narasi Kokoro lokal, mengekspor draft/final, memeriksa seluruh waveform narasi dan SRT, lalu menguji restart. Tidak menggunakan proyek pengguna maupun inference Nano.
