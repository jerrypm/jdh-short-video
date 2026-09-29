# Task 08 — pemeriksaan Shorts dan paket unggah

24 September 2026. Implementasi **0.2.8 build 10**, Apple Silicon/macOS 26+. Task 09–11 belum dimulai. Provider tetap **Gemini Nano lokal**, tanpa cloud, API key atau penggantian model. Panduan: [shorts-quality-and-upload.md](shorts-quality-and-upload.md).

## Hasil implementasi

- Panel ekspor memisahkan temuan teknis yang diukur dari saran editorial Nano. Pemeriksaan mencakup media hilang, narasi terpotong/usang, risiko puncak audio, jeda panjang, layout caption dan overlap caption/callout, serta rencana dimensi/durasi output.
- Ambang produk dapat diedit; label menjelaskan bahwa ambang tersebut bukan aturan YouTube. Metrik audio menggunakan float PCM stereo 48 kHz dan jendela 10 ms. Puncak sampel bukan true peak/LUFS atau bukti distorsi.
- Nano menerima teks English dari naskah, caption, deskripsi visual pengguna dan konteks scene. Model tidak menerima frame/audio. Schema menolak field tambahan, rentang waktu di luar scene dan respons operasi yang salah. Saran tidak menjadi kesalahan teknis, skor viral atau janji views.
- Metadata dan perbaikan dipresentasikan sebagai usulan. Preview sebelum/sesudah, partial scene selection, exact reviewed selection, revision/media guards, atomic save, backup, retry idempoten dan Undo/Redo melindungi penerapan.
- Ekspor menghasilkan metadata yang dapat diedit, catatan unggah, laporan dan `upload.zip` berisi MP4/SRT bila ada. Arsip sumber `project.zip` tetap tersedia. Tidak ada koneksi akun atau unggah YouTube otomatis.
- File hasil diverifikasi dengan probe, jumlah frame/30 fps, decode penuh dan pengukuran audio. Perubahan media selama render membatalkan hasil.
- QA native menemukan dan memperbaiki input angka yang membatasi digit terlalu dini. Input kini mempertahankan ketikan sementara, commit saat blur/Enter, dan langsung membatalkan review lama saat diedit.

## Verifikasi

| Pemeriksaan | Hasil |
| --- | --- |
| Backend | **145 tes lulus**: PCM/stereo, silence, mixing, media/narasi/layout/overlap, invalid edits, stale revision/media/report, expiry/restart, review/apply/backup/retry, editorial schema/cancel/language, Host/Origin/CSRF/body limits dan paket output nyata. |
| Frontend | **25 tes lulus**, termasuk regresi audio controller, default manifest lama, pembatalan editorial saat respons submit tidak pasti dan proposal tanpa penulisan proyek otomatis. |
| Build | TypeScript, Next production, Swift release dan Ruff F lulus. Frontend tests/typecheck diulang setelah perbaikan input. |
| Bundle | Codesign deep/strict lulus; **117 file** backend, companion dan frontend output cocok byte-for-byte. Info.plist: 0.2.8, build 10, macOS 26.0. |
| Bundled runtime | **9 pemeriksaan lulus** menggunakan Python/FFmpeg/Kokoro dari bundle, storage sementara dan companion fixture berlabel. Metadata/settings tetap sama setelah restart sidecar. |

Total unit/regression tests: **170**. Dua warning deprecation TestClient/httpx tetap ada tanpa kegagalan. Harness tersedia di `script/verify_quality_runtime.py`; keluaran terstruktur sesi ini disimpan sementara di `/tmp/jdh-quality-runtime.json`, `/tmp/jdh-quality-bundle-verification.json` dan `/tmp/jdh-quality-native-final.json`.

## File hasil dan audio

Fixture dua scene menggunakan gambar portrait, zoom, callout dan **Kokoro English nyata (`af_heart`)**. Durasi timeline **9 detik / 270 frame**. Metadata dan posisi caption diterapkan sesudah review; pemeriksaan lama ditolak setelah proyek berubah.

| Preset | Dimensi/fps/frame | Decode audio | Puncak sampel | Sampel dekat/pada full scale |
| --- | --- | --- | --- | --- |
| Draft | 360×640 / 30 / 270 | 9,002667 detik | −14,290 dBFS | 0 / 0 |
| Final | 1080×1920 / 30 / 270 | 9,002667 detik | −14,290 dBFS | 0 / 0 |

Durasi container kedua MP4 9 detik. Tambahan sekitar 2,67 ms pada audio decode adalah padding akhir AAC. Gap fixture 2,75–9,002667 detik terdeteksi. Sampel final pada detik 7,5 diperiksa secara visual: caption dan callout terlihat lengkap dan terpisah sesudah posisi caption diubah dari 78% ke 65%. Arsip unggah dibuka dan isinya diverifikasi, termasuk metadata yang disimpan dan laporan hasil.

Pengukuran ini bukan penilaian subjektif suara melalui speaker dan bukan jaminan codec/perangkat lain. Perbaikan audio preview sebelumnya tetap dilindungi delapan tes controller; Task 08 tidak menambah seek/play per frame.

## QA aplikasi native

Mac tersedia untuk computer use pada Task 08. Pengujian menggunakan **jendela JDH Shorts Studio · QA, AppKit/WebKit**, CUA dan data sementara; tidak membuka proyek pengguna, akun kerja atau tab/history Chrome personal. Screenshot tampil inline, bukan disimpan sebagai tangkapan layar lokal.

| Alur | Bukti yang teramati |
| --- | --- |
| Temuan terukur | Hook tail 2,75 detik, overlap caption/callout pada scene Demo, dan gap mix ditampilkan dengan scene/rentang waktu. |
| Editorial | Companion fixture mengembalikan judul `QA FIXTURE — One focused idea` dan deskripsi yang jelas menyatakan bukan hasil Nano nyata. Hasil muncul terpisah; metadata tidak berubah otomatis. |
| Review/apply | Judul diubah menjadi `QA native reviewed short`; posisi caption 78% → 65% ditinjau lalu diterapkan. Pemeriksaan ulang menghapus peringatan overlap, mempertahankan peringatan jeda. |
| Undo/Redo | Undo mengembalikan metadata asli, Redo memulihkan metadata yang ditinjau. |
| Ekspor native | Draft revisi 7 selesai, sembilan tautan file tersedia. Verifikasi menampilkan 270 frame dan peak −12,379 dBFS pada fixture native yang memakai gain 100%; angka berbeda dari harness yang menerapkan gain berbeda. |
| Playback output | Tombol Play beralih Pause, visual/caption dirender, lalu player mencapai 9 detik dan kembali Play. |
| Build final | Ketikan `65` bertahan sebagai 65; review menampilkan 78 → 65. Mengetik digit sementara `6` segera menghilangkan review/apply lama. Enter mengesahkan 65; membatalkan usulan mengembalikan 78. |
| Log | Log sidecar QA final tidak mengandung error/exception/traceback. Console JavaScript WebKit tidak diinspeksi terpisah. |

Sesi companion dan aplikasi QA dihentikan setelah pengujian. Runtime QA otomatis membersihkan storage miliknya; artefak MP4/ZIP pemeriksaan disimpan sementara terpisah untuk inspeksi.

## Batas yang masih ada

- **Inference Nano nyata pada build terintegrasi belum terverifikasi.** Kendala Chrome `ERR_BLOCKED_BY_CLIENT` dari task sebelumnya belum diselesaikan. Fixture Task 08 menguji protokol/UI/schema, bukan kualitas keluaran model.
- AI saat ini hanya teks English; bukan pemeriksaan frame, pendengaran audio atau riset tren. Review/manual metadata tetap tersedia tanpa Nano.
- Overlap memakai bounding box dan guide editor, bukan deteksi piksel/aturan safe-area resmi platform. Risiko clipping perlu ditinjau dengan mendengarkan hasil.
- Laporan aktif berlaku 15 menit, maksimal delapan dalam memori, dan harus dibuat ulang sesudah restart atau perubahan proyek/media. API render lama masih menerima request tanpa laporan, dengan penanda `pre_export_checked: false` yang eksplisit.
- Mac mini tujuan belum diuji. Bundle masih ad-hoc signed. **DMG, notarization dan validasi distribusi merupakan Task 09**, belum dijalankan pada task ini.
