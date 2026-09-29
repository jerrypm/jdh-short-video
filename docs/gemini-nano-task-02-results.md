# Task 02 — provider Nano untuk aplikasi Mac

22 September 2026. Implementasi selesai; verifikasi Nano nyata pada build terintegrasi masih tertahan. Tidak melanjutkan Task 03–11.

## Hasil implementasi

- Aplikasi Mac 0.2.2 (build 4) memiliki Setup pairing, status koneksi/model, serta bantuan hook/draf English melalui `AIProvider`.
- Provider tetap **Gemini Nano lokal**. Tidak ada API key, provider pengganti, inference cloud, atau Chromium yang disisipkan ke aplikasi.
- Jalur yang dipilih mengikuti bukti Task 01: tab companion Chrome + broker loopback terautentikasi. Native Messaging/extension dari rancangan awal **tidak diimplementasikan**; instalasi/registrasi host dan allowlist extension ID tidak berlaku pada transport ini.
- Pairing sekali pakai, masa berlaku, token sesi, ID dokumen/request, operasi dan ukuran terbatas, satu pekerjaan aktif, lease, batas waktu, cancel, reconnect, serta penolakan hasil lama tersedia.
- Saran divalidasi sebelum review. Penerapan hanya mengganti naskah utama lewat history/autosave yang sudah ada. Scene tetap utuh; saran ditolak jika proyek berubah setelah permintaan dimulai.
- Model diunduh melalui tombol persiapan di Chrome bila diperlukan; tidak dibundel dalam aplikasi. Chrome/tab perlu tetap terbuka selama AI digunakan.

Panduan lifecycle, keamanan dan setup: [Chrome AI](chrome-ai.md).

## Bukti pengujian — dipisahkan menurut jenisnya

| Pemeriksaan | Hasil | Jenis bukti |
| --- | --- | --- |
| Real Nano English, prototype broker, abort dan reconnect | PASS pada Task 01 | Inference nyata di Chrome; [laporan Task 01](gemini-nano-task-01-results.md). Bukan bukti ulang build terintegrasi. |
| Mac editor → Chrome → Nano → proposal pada build 0.2.2 | **TERTAHAN** | Chrome terhubung memblokir URL companion dengan `ERR_BLOCKED_BY_CLIENT` sebelum halaman berjalan. Tidak mengubah pengaturan keamanan, mencoba akun kerja, atau mengalihkan provider. |
| Pairing expiry/replay/revocation, auth/origin/CSRF, malformed/oversized payload | PASS | Tes HTTP/broker terisolasi. |
| Cancel sebelum POST, respons terlambat, disconnect, timeout, reload, credential restart | PASS | Tes broker dengan jam terkontrol; bukan restart Chrome nyata. |
| Held poll menerima request dan pembatalan dari app | PASS | Tes async HTTP melalui ASGI, tanpa model. |
| Validasi output, source cleanup, record retention, busy dan idempotency | PASS | Tes terisolasi. |
| Setup di aplikasi native dan pembuatan tautan pairing | PASS | UI WKWebView dalam `.app` QA. |
| Hook/draf → dialog review → apply → undo | PASS | Respons **QA FIXTURE** melalui broker aplikasi nyata. Scene tetap tiga; undo mengembalikan naskah awal. Bukan inference Nano. |
| Edit naskah saat request berjalan | PASS | UI native dengan fixture; dialog menampilkan proyek berubah, seluruh tombol apply nonaktif. |
| Batal dari editor | PASS | Fixture menerima pembatalan ID request yang sama; UI kembali siap, naskah tetap. |
| Companion fixture dihentikan saat request berjalan | PASS | UI berhenti memproses, menampilkan pesan koneksi terputus, tombol AI nonaktif. |
| Editing/simpan setelah disconnect | PASS | Catatan diedit di UI, tersimpan ke manifest QA revision 5; tiga scene tetap utuh. |
| Quit aplikasi QA | PASS | Jendela keluar melalui Cmd+Q; data tersimpan. |
| Model belum diunduh, download progress/cancel, Chrome restart penuh, offline OS, Mac mini tujuan | BELUM DIUJI | Memerlukan lingkungan yang sesuai; tidak disimpulkan dari mock/fixture. |
| Audio preview bersamaan dengan Nano nyata | BELUM DIUJI pada Task 02 | Tes regresi audio tetap lulus, tetapi bukan pemeriksaan pendengaran/performa saat inference. |

Tes otomatis: 15 tes broker/protokol Nano lulus, 14 tes frontend lulus (termasuk validasi AI dan regresi preview audio), serta 9 tes backend lama lulus pada suite awal, termasuk render FFmpeg. Total 38 kasus unik. TypeScript, syntax companion, lint Python dan build release Swift/Next lulus. Peringatan deprecation TestClient/httpx tidak menyebabkan kegagalan.

## Lingkungan dan artefak

Pengujian pada Mac sesi ini (Apple M1 Pro, macOS 26.0.1), bukan Mac mini tujuan. `.app` dijalankan dengan `--isolated-qa`: proyek dan log berada di folder sementara `JDHShortsStudio-QA-*`, terpisah dari proyek pengguna. Fixture menolak penyimpanan non-QA dan tidak dibundel sebagai fallback.

- Aplikasi: `dist/JDH Shorts Studio.app`, versi 0.2.2 build 4, Apple Silicon/macOS 26+, ad-hoc signed.
- [Catatan UI fixture](qa/nano-task-02-ui.json).
- [Fixture khusus QA](../script/qa_nano_fixture.py).
- Aplikasi di `/Applications` dan DMG 0.2.1 tidak diganti. Tidak membuat DMG baru pada Task 02.

## Pemeriksaan yang masih diperlukan

Buka build 0.2.2, buat tautan baru dari Setup, dan buka pada Chrome personal yang mengizinkan halaman loopback. Pastikan companion melaporkan English siap, lalu jalankan hook/draf dari editor dan periksa proposal nyata. Ulangi cancel, penutupan/reload tab dan pairing setelah restart aplikasi. Sampai itu berhasil, integrasi belum dinyatakan tervalidasi menyeluruh untuk rilis.
