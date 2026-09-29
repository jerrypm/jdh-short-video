# Task 09 — validasi release Mac dan DMG

24 September 2026. Paket personal **0.2.9 build 11**, Apple Silicon/macOS **26+**. Deployment target bundle tidak diubah. Task 10–11 belum dijalankan.

## Artefak

- `dist/JDH-Shorts-Studio-0.2.9-arm64.dmg` — **538.595.246 byte**, sekitar 514 MiB.
- `dist/JDH-Shorts-Studio-0.2.9-arm64.dmg.sha256` — checksum transfer, diverifikasi kembali dengan `shasum -a 256 -c`.
- `dist/JDH-Shorts-Studio-0.2.9-runtime-check.json` — first-start runtime dari salinan instalasi.
- `dist/JDH-Shorts-Studio-0.2.9-release-check.json` — audit native, offline dan 72 pemeriksaan workflow.
- `dist/JDH-Shorts-Studio-0.2.9-lifecycle-check.json` — migrasi, rendering, pembatalan, restart dan AI deferral.

SHA-256:

```text
b9c4dac36d57378796b988838ccc75c43c459113be44e2f044cda5164a84de7b
```

Image dikompresi LZFSE, diverifikasi `hdiutil`, dipasang read-only, kemudian aplikasi **disalin keluar dari DMG** ke `/private/tmp/jdh-install-check.RFWovL/JDH Shorts Studio.app` untuk pengujian. DMG berisi aplikasi, shortcut Applications dan `Install.txt` terbaru dengan petunjuk companion. Tidak mengganti aplikasi di `/Applications`, memasang extension, atau mengirim artefak ke notarization.

## Perbaikan audit release

Validasi awal JavaScript companion belum memasukkan operasi `editorial`, sehingga request Task 08 akan ditolak sebelum mencapai Nano. Allowlist dan pesan status diperbaiki. Ditambahkan 12 tes yang mengeksekusi **JavaScript companion aktual** dengan API model palsu: kelima operasi, schema dispatch, invalid output/operation, cancel, context limit, missing API/model, dan pelepasan sesi. Fixture broker pada task sebelumnya tidak mengeksekusi jalur browser ini.

`create_dmg.sh` kini memverifikasi native dependencies serta workflow dari salinan instalasi. `JDH_KEEP_INSTALL_CHECK=1` mempertahankan salinan sementara untuk QA tambahan. Script `verify_release.py` dan `verify_release_lifecycle.py` dapat dijalankan ulang pada aplikasi dari DMG; laporan utama mencatat versi bundle yang sebenarnya, bukan versi milestone harness lama.

## Lingkungan dan hasil

Host sesi ini **MacBook Pro M1 Pro, RAM 16 GB, macOS 26.0.1**. Ini bukan pengujian pada Mac mini pengguna.

| Pemeriksaan | Hasil dan tingkat bukti |
| --- | --- |
| Unit/regression | **185 tes lulus**: 148 backend, 25 frontend termasuk delapan regresi audio controller, 12 companion JavaScript. TypeScript, Next production, Swift release dan Ruff F lulus. Dua warning deprecation TestClient tetap ada. |
| Integritas bundle | Codesign deep/strict pada build, aplikasi di DMG dan salinan instalasi lulus. **117 file** backend/companion/frontend hasil build cocok dengan salinan instalasi. |
| Native dependencies | **166 Mach-O** memiliki arm64; minimum OS yang dideklarasikan tidak melampaui 26.0; tidak ditemukan link dependency ke Homebrew/folder pengguna. Symlink tetap di dalam bundle. LC_ID_DYLIB historis dibedakan dari link dependency. |
| First start | Sidecar dari salinan terpasang siap dalam **7,36 detik** pada pengukuran pertama, dengan working directory/data sementara dan PATH tanpa Homebrew. UI statis, session dan health token diperiksa. |
| Tanpa companion | Proyek kosong, penulisan manual, Kokoro nyata dan render berjalan dengan status AI disconnected. Tidak mematikan Chrome pengguna untuk pengujian ini. |
| Model belum ada | Kokoro: model directory kosong disimulasikan pada API, gagal dengan pesan dan proyek tetap utuh. Nano: API model tidak ada/downloadable/create gagal diuji dengan model double dan transport; tidak ada download otomatis/fallback. Model Chrome pengguna tidak dihapus. |
| Offline sesudah model tersedia | **Kokoro nyata** menghasilkan 85 frame audio dengan seluruh koneksi socket Python ditolak dan model dari bundle. Cache ide tetap tersedia saat transport Nano terputus. Ini bukan bukti Nano nyata offline atau pemutusan jaringan seluruh OS. |
| Disk rendah/penuh | Tes menginjeksikan free space 499 MiB: renderer ditolak sebelum encoder berjalan. Injeksi `ENOSPC` saat manifest ditulis mempertahankan file lama dan membersihkan file sementara. Disk host tidak sengaja diisi. Guard 500 MiB adalah batas minimum, bukan estimasi cukup untuk semua proyek besar. |
| Migrasi | ZIP fixture schema lama tanpa motion/upload/quality settings diimpor ke proyek baru; media terpelihara dan default tambahan benar. Proyek bertahan sesudah restart. |
| Render + AI | Request editorial transport aktif dibatalkan saat render nyata dimulai. Lima pembacaan proyek selama render tetap merespons, maksimum **10,47 ms** pada sampel ini. Ini bukan FPS editor/profiling Nano nyata. |
| Cancel/retry | Render dibatalkan, output parsial dihapus, proyek tetap sama; render berikutnya berhasil. Restart mencabut pairing dan mempertahankan proyek. |
| Audio timing | Draft dan final mempunyai onset tone **0,30 / 1,60 / 3,30 / 4,60 detik**, cocok dengan timeline pada resolusi 10 ms. WAV 10,5 detik; AAC decode sekitar 17 ms padding akhir. Musik loop mempertahankan timing. |
| Quality/export | Draft 360×640 dan final 1080×1920: 30 fps, 270 frame, 9 detik; probe/decode dan ZIP diperiksa. Peak sampel −14,284 dBFS, tanpa sampel near/full scale pada fixture. |
| Native launch | Proses aplikasi yang disalin dari DMG berjalan dengan `--isolated-qa` dan sidecar sendiri; API menunjukkan proyek kosong, semua komponen siap, dan log sidecar tanpa error. **QA tampilan/playback native release ini tertahan karena Mac terkunci.** Pengguna sudah diminta membuka kunci. Native QA 0.2.8 pada Task 08 bukan pengganti verifikasi UI 0.2.9. |

72 pemeriksaan workflow terdiri atas memori 12, ide 13, storyboard 15, pacing 14, quality 9 dan lifecycle 9. Fixture AI ditandai sebagai fixture; tidak ada klaim inference Nano nyata. Kokoro mengeluarkan warning upstream Torch (dropout/weight_norm/JIT deprecation), tanpa kegagalan render atau inference.

## Signing dan batas distribusi

Signature **ad-hoc**, tanpa TeamIdentifier atau entitlements tambahan; bukan Developer ID, tidak notarized dan tidak hardened-runtime audited. Keychain sesi ini melaporkan **0 signing identity valid**. `spctl --assess --type execute` pada salinan dari DMG menghasilkan **rejected**; codesign valid tidak berarti Gatekeeper menyetujui distribusi.

Saat dipindahkan ke Mac lain, macOS dapat meminta pengecualian per aplikasi. Jika sumber/checksum sudah dipercaya, ikuti [petunjuk Apple untuk aplikasi yang belum notarized](https://support.apple.com/en-us/102445). Pengujian ini tidak menambah pengecualian, menghapus quarantine atau menonaktifkan Gatekeeper. Jalur installer yang benar-benar terkena quarantine dari transfer internet belum diuji.

Provider tetap **Gemini Nano lokal melalui Chrome personal**. Nano tidak dibundel; Chrome menentukan eligibility dan download. [Dokumentasi Prompt API](https://developer.chrome.com/docs/ai/prompt-api) yang diperiksa 24 September 2026 menyebut kebutuhan ruang kosong profil dan perangkat tersendiri. Kesiapan aplikasi/Kokoro tidak menjamin kesiapan Nano.

**Batas terbuka:** inference Nano nyata pada build terintegrasi belum terverifikasi (`ERR_BLOCKED_BY_CLIENT` sebelumnya), UI native release 0.2.9 belum diperiksa karena Mac terkunci, dan Mac mini tujuan belum diuji. Paket personal sudah tersedia dengan batas tersebut; ini bukan pernyataan bahwa semua release gate telah lulus. Tidak membaca akun kerja, tab/history pengguna atau proyek pribadi.
