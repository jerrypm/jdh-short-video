**Task 01 — Gemini Nano lokal: hasil kelayakan**

Selesai pada 22 September 2026. Pengguna memilih menyelesaikan Task 01 saja.
Provider yang ditetapkan: Gemini Nano lokal melalui Chrome. Tidak ada penggantian
provider atau inference cloud. Task 02–11 belum dijalankan.

**Keputusan**

GO untuk mengembangkan bantuan teks English dengan Gemini Nano lokal melalui
companion Chrome. Permintaan dari proses backend lokal sampai keluaran Nano
sudah dibuktikan menggunakan prototype terisolasi.

NO-GO untuk menjanjikan Bahasa Indonesia atau input audio pada konfigurasi yang
diuji: kedua capability mengembalikan unavailable. Input gambar baru lulus
availability check, belum lulus pengujian inference gambar.

GO ini belum berarti aplikasi Mac siap dirilis dengan AI. Integrasi editor,
lifecycle produksi, pemasangan companion, dan pengujian Mac mini tujuan masih
bagian task berikutnya.

**Lingkungan yang benar-benar diuji**

- MacBookPro18,3, Apple M1 Pro, RAM 16 GB, delapan core, macOS 26.0.1.
- Ruang kosong volume proyek saat pemeriksaan: sekitar 29 GiB.
- Browser yang terhubung melaporkan Chrome/151.0.0.0 melalui user agent.
- Bundle Google Chrome yang terpasang melaporkan 153.0.8010.53. Kedua nilai
  dicatat terpisah; versi bundle tidak dipakai sebagai bukti versi proses browser.
- Pengujian dilakukan pada Mac sesi ini, bukan pada Mac mini tujuan.
- Model English berstatus available saat pemeriksaan halaman lokal.

**Matriks hasil**

| Pemeriksaan | Hasil | Bukti / batas |
| --- | --- | --- |
| Teks English | PASS | Dua respons dengan masing-masing tiga ide, JSON divalidasi. |
| Bahasa Indonesia | UNAVAILABLE | Opsi bahasa id diperiksa secara eksplisit. Tidak dilakukan inference dengan bahasa yang disamarkan. |
| Input gambar | AVAILABLE saja | Belum menguji kualitas atau keluaran multimodal. |
| Input audio | UNAVAILABLE | Tidak menganggap dukungan audio mengikuti dukungan teks. |
| Session baru | PASS | Pembuatan session 2,8 ms; prompt pertama 20.480,1 ms. Model sudah tersedia sebelum uji. |
| Session dipakai ulang | PASS | Prompt kedua 50.172,5 ms. Sampel ini lebih lambat, sehingga warm session tidak diasumsikan selalu lebih cepat. |
| Abort + recovery | PASS | AbortError teramati; session baru menghasilkan JSON valid. Seluruh tes 21.925,3 ms, termasuk recovery. |
| Backend → companion → Nano | PASS | Inference 26.615,4 ms; perjalanan client 28.328,8 ms. |
| Companion ditutup saat bekerja | PASS | Job gagal dengan companion_disconnected; tidak ada hasil sukses palsu. |
| Companion dibuka kembali | PASS | Request baru selesai; inference 12.240,5 ms, perjalanan client 13.089,1 ms. |
| Validasi keluaran | PASS | Dua automated tests, termasuk field tambahan, duplikat, data kosong, panjang berlebih, dan JSON rusak. |
| Proteksi broker lokal | PASS | Sembilan pemeriksaan penolakan host, origin, token, path, payload, dan operasi yang tidak diizinkan. |
| Playback fixture saat inference | TERUKUR, terbatas | Video tetap berjalan; pemeriksaan rinci di bawah. Ini bukan pengujian audio aplikasi Mac. |
| Chrome seluruhnya ditutup/restart | BELUM DIUJI | Hanya tab companion milik pengujian yang ditutup; browser pengguna secara keseluruhan tidak dihentikan. |
| Offline tanpa jaringan OS | BELUM DIUJI | Inference memakai API model lokal; konektivitas seluruh OS/browser tidak dimatikan. |
| Native Messaging extension | BELUM DIUJI | Jalur yang terbukti menggunakan halaman companion lokal dan broker, tanpa memasang extension. |
| Editor Mac dan DMG baru | DI LUAR TASK 01 | Aplikasi utama belum diubah atau dikemas ulang. |

Angka waktu berasal dari sedikit sampel pada satu perangkat. Angka tersebut
bukan benchmark umum, SLA, atau jaminan waktu pada Mac mini.

**Playback yang diukur**

Fixture video hasil renderer aplikasi diputar selama dua permintaan Nano, sekitar
70,7 detik. Timer UI dengan interval 100 ms memiliki gap maksimum sekitar
101,9 ms. Ada dua event waiting pada waktu media 0 saat video mengulang,
diikuti playing sekitar 29,4 ms dan 13,1 ms kemudian.

Data ini mendukung bahwa halaman tidak mengalami stall main thread panjang
pada sampel tersebut. Data ini tidak membuktikan audio terdengar tanpa putus,
tidak menggantikan uji PreviewPlayer aplikasi, dan tidak membuktikan bahwa event
waiting disebabkan oleh Nano. Pemeriksaan audio Mac tetap diperlukan pada
integrasi berikutnya.

**Implikasi desain**

1. Ide harian perlu cache. Jangan membuat pengguna menunggu inference setiap
   aplikasi dibuka.
2. Mulai dengan teks English. UI aplikasi boleh tetap Indonesia, tetapi
   capability bahasa konten harus ditampilkan secara jujur.
3. Tetap gunakan keluaran terstruktur, validasi ulang, review, revision guard,
   dan undo pada integrasi berikutnya. JSON valid belum berarti klaimnya benar;
   misalnya salah satu output menyebut arrays sebagai elemen layout SwiftUI.
4. Companion lokal merupakan jalur awal yang sudah terbukti dan tidak
   memerlukan extension untuk spike ini. Native Messaging tetap pilihan
   lanjutan jika diperlukan, dengan pengujian lifecycle dan distribusi sendiri.
5. Request harus berakhir secara jelas saat companion hilang. Pemulihan
   dilakukan dengan request baru; hasil dari pekerjaan lama tidak diterapkan.
6. API key, Gemini cloud, Foundation Models, atau model pengganti tidak masuk
   jalur implementasi yang diizinkan pada task ini.

**Bukti yang disimpan**

- [Capability, timing, playback, dan abort](/Users/jeripurnamamaulid/Projects/01_PRODUCT-Claude/jdh-shorts-studio/docs/qa/nano-local-capabilities.json)
- [Permintaan backend yang berhasil](/Users/jeripurnamamaulid/Projects/01_PRODUCT-Claude/jdh-shorts-studio/docs/qa/nano-local-bridge.json)
- [Koneksi putus](/Users/jeripurnamamaulid/Projects/01_PRODUCT-Claude/jdh-shorts-studio/docs/qa/nano-local-disconnect.json)
- [Pemulihan koneksi](/Users/jeripurnamamaulid/Projects/01_PRODUCT-Claude/jdh-shorts-studio/docs/qa/nano-local-reconnect.json)
- [Cara menjalankan prototype](/Users/jeripurnamamaulid/Projects/01_PRODUCT-Claude/jdh-shorts-studio/experiments/nano-local-spike/README.md)

Pengujian diawali dengan demo resmi yang menghasilkan ide nyata, lalu diulang
dengan halaman milik proyek di localhost agar schema, timing, dan laporan dapat
dikontrol. Halaman internal chrome://on-device-internals diblokir oleh kebijakan
browser tool; halaman itu tidak diakses lewat jalur alternatif. Pengujian API
berjalan pada halaman biasa yang diizinkan. Akun kerja tidak dibuka atau dibaca.

Hanya prototype dan dokumentasi Task 01 yang ditambahkan. Tidak ada perubahan
pada kode editor, backend produksi, proyek video pengguna, aplikasi terpasang,
atau installer DMG.
