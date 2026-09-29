# Task 07 — preset animasi dan callout

24 September 2026. Implementasi **0.2.7 build 9**, Apple Silicon/macOS 26+. Task 08–11 belum dimulai. Provider tetap **Gemini Nano lokal**. Motion dirender secara deterministik di perangkat; tidak ada cloud, API key, provider pengganti atau model tambahan.

## Perubahan

- Preset visual none, zoom masuk/keluar dan pan empat arah, intensitas maksimum 12%, fokus X/Y, easing linear/lembut, serta rentang frame lokal.
- Caption fade/slide dan callout dengan teks, posisi, ukuran, pointer dan entrance yang dapat diedit. PNG/font digunakan bersama oleh preview dan ekspor.
- **Gerak seluruh proyek → Tanpa gerak** mematikan animasi sambil mempertahankan teks dan konfigurasi preset. Proyek lama tetap statis melalui default schema.
- Kontrol tersedia di inspector dan review storyboard. Proposal Nano memakai schema motion v1 dengan validasi parameter; apply tetap mengikuti revision guard, atomic save, backup dan Undo/Redo.
- Evaluasi gerak pada React dan FFmpeg, preload overlay scene berikutnya, serta geometri Fit/Fill/scale sebelum clipping. Frame tick tidak meminta PNG baru atau mengulang seek/play audio.
- Perbaikan QA: loop PNG ekspor ditetapkan 30 fps; slide memakai waktu timeline agar tidak bergeser satu frame; kontrol lebar callout dibatasi 800 px; entrance slide menyisakan ruang 48 px untuk kotak dan titik tujuan.

Kontrak dan panduan: [motion-presets.md](motion-presets.md).

## Pengujian otomatis dan bundle

| Pemeriksaan | Hasil |
| --- | --- |
| Backend | **126 tes lulus**, termasuk default proyek lama, batas schema, output AI invalid, callout, SRT dan penerapan storyboard. |
| Frontend | **22 tes lulus**, termasuk 8 regresi audio controller. |
| Paritas rumus | **140 kasus** evaluator TypeScript aktual dibandingkan dengan Python, mencakup setiap preset, dua easing, sebelum/di/antara/setelah keyframe. |
| Build/checks | TypeScript, Next production, Swift release, Ruff F dan codesign deep/strict lulus. |
| Kesesuaian paket | **105 file** backend, companion dan frontend hasil build cocok byte-for-byte dengan bundle. Info.plist: 0.2.7, build 9, macOS 26.0. |
| Runtime motion | **12 pemeriksaan lulus** dengan Python/FFmpeg dari bundle; data dan sidecar terpisah dari proyek pengguna. |
| Regresi timing | **14 pemeriksaan Task 06 lulus** pada bundle 0.2.7, termasuk Kokoro English nyata, trim, musik loop, draft/final, Undo/Redo dan restart. |

Total unit/regression tests: **148**. Dua warning deprecation TestClient/httpx tetap ada tanpa kegagalan. Semua tes menggunakan fixture; pengujian ini tidak menyatakan inference Nano nyata berjalan.

## Hasil render

Fixture mencakup delapan scene, total **177 frame / 5,9 detik**: gambar portrait/landscape/square, Fit/Fill, offset/scale, video dengan source trim satu detik, scene pendek sembilan frame, caption fade/slide dan callout. Awal, tengah dan akhir setiap scene diperiksa pada dua resolusi ekspor.

| Preset ekspor | Sampel | MAE piksel maksimum (0–255) | Waktu render + perbandingan |
| --- | --- | --- | --- |
| Draft 360×640 | 24 | 3,985 | 7,77 detik |
| Final 1080×1920 | 24 | 2,507 | 16,44 detik |

Semua 48 sampel berada di bawah ambang uji 8/255. Referensi numerik dibuat dengan **evaluator React/TypeScript yang sebenarnya lalu dikomposisikan memakai PIL**; angka tersebut bukan perbandingan otomatis screenshot browser. Perbedaan resampling/encoding tetap ada. Bukti: [motion-runtime.json](qa/motion-runtime.json), [zoom awal/tengah/akhir](qa/motion-zoom-comparison.png) dan [teks awal/tengah/akhir](qa/motion-text-comparison.png). Gambar perbandingan menampilkan referensi dan hasil ekspor secara berpasangan.

Mode tanpa gerak menghasilkan visual statis dan teks yang langsung terlihat. Hash WAV narasi identik antara render motion aktif/nonaktif. Total frame, source trim dan data motion setelah restart cocok. Decode draft/final berhasil.

Regresi audio [motion-pacing-regression.json](qa/motion-pacing-regression.json) mempertahankan onset tone **0,30 / 1,60 / 3,30 / 4,60 detik**, sesuai timeline pada resolusi pengukuran 10 ms. Narasi WAV tetap 10,5 detik; decode AAC mencakup sekitar 17 ms padding akhir seperti Task 06. Suite ini juga menjalankan Kokoro English lokal sebenarnya.

## QA UI dan playback

Dilakukan melalui **computer use/CUA, Codex in-app browser**, pada sidecar bundle dan data sementara. URL QA `127.0.0.1:59937` dan pemeriksaan batas final `127.0.0.1:60452` bukan server produk permanen. Screenshot ditampilkan inline, bukan disimpan sebagai bukti screenshot lokal. Ukuran screenshot penuh 1280×720.

| Pemeriksaan UI | Bukti teramati |
| --- | --- |
| Identitas/tampilan | JDH Shorts Studio, proyek Task 07 · QA motion, delapan scene, inspector/timeline/preview tampil tanpa halaman kosong atau error framework. |
| Zoom awal/tengah/akhir | Frame 0/4/8: scale 1 / 1,06 / 1,12; translasi 0/0, −1,8%/−4,2%, −3,6%/−8,4%. Screenshot menunjukkan posisi fiducial sesuai frame ekspor. |
| Caption/callout | Frame lokal 0/4/8 dengan entrance 2–8: opacity 0 / 1⁄3 / 1, slide 48 / 32 / 0 px. PNG lengkap, posisi dan keterlihatan sesuai frame ekspor yang diperiksa. |
| Tanpa gerak | Pada frame awal, caption/callout opacity 1 dan translasi 0; konfigurasi preset tersimpan. |
| Edit dan Undo/Redo | Callout Focus here → Look here → Undo Focus here → Redo Look here. Reload tetap menampilkan Look here dan status Tersimpan. |
| Batas final | Input lebar 900 dibatasi 800; memilih slide mengubah kotak Y 1450 → 1400 dan target Y 1612 → 1564. Screenshot frame tengah tetap berada pada guide bawah. |
| Playback | Putar memulai audio, timeline melewati scene bergambar/video dan berhenti pada 00:05:26 (frame akhir); tidak ada alert media atau console error/warning. |
| Performa | Smoke playback selesai dengan delapan scene dan overlay preload. Tidak ada profiler/frame-time native atau pengukuran beban inference Nano; angka render di atas bukan jaminan native 30 fps. |
| Native macOS/WebKit | **Belum dapat diverifikasi ulang**: computer use melaporkan Mac terkunci. Pengguna sudah diminta membuka kunci; QA browser tidak menggantikan pengujian WebKit native. |

Tab, sidecar dan data QA sementara ditutup/dibersihkan setelah pengujian. Tidak membaca akun kerja, riwayat browser, tab Chrome pengguna atau proyek pengguna.

## Batas yang tersisa

- Inference Nano nyata pada build terintegrasi masih tertahan oleh batas Task 02–06 (`ERR_BLOCKED_BY_CLIENT` pada Chrome personal). Schema/proposal diuji memakai fixture; bukan bukti kualitas ide atau hasil Nano nyata.
- Mac mini tujuan belum diuji. Audio/output parity di fixture tidak membuktikan sinkronisasi speaker/layar setiap perangkat.
- Tidak ada crossfade, overlap scene, arbitrary filters/keyframes, object tracking, transisi keluar teks atau alignment per kata. SRT tetap cue per scene.
- Safe-area adalah guide editor; pointer memiliki radius 6 px. Deteksi caption/callout bertumpuk dan quality checks tambahan masih merupakan Task 08.
- Bundle lokal tersedia di `dist/JDH Shorts Studio.app`, dengan ad-hoc signing. DMG, notarization dan pemasangan `/Applications` tidak diubah pada Task 07.
