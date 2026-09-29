# Task 04 — Ide hari ini

23 September 2026. Implementasi tersedia pada **0.2.4 build 6**. Task 05–11 belum dijalankan. Provider tetap **Gemini Nano lokal melalui companion Chrome**; tidak ada API key, cloud inference, atau provider pengganti.

## Hasil implementasi

- Beranda memiliki tiga jenis kartu: lanjutan seri, sudut pandang baru, dan eksperimen relevan, dengan hook, konsep, alasan, perbedaan, durasi, kebutuhan media dan source project ID tervalidasi.
- Cache SQLite persisten berdasarkan tanggal/zona waktu, profil, bahasa, revision katalog dan feedback. Cache dibuka lebih dahulu; ide lama yang masih aman ditampilkan dengan tanggal dan status konteks sebelumnya.
- Mode harian/manual, **Ide baru**, **Batal**, **Simpan**, **Lewati**, **Urungkan**, dan alasan opsional. Ide tersimpan bertahan setelah batch diganti.
- Katalog kosong menggunakan preferensi onboarding. Provider tidak siap menampilkan cache atau panduan manual berlabel; tidak membuat riwayat fiktif. Generasi bahasa Indonesia belum diaktifkan.
- Pengecualian/penghapusan/perubahan sumber membatalkan permintaan aktif dan menghapus cache/feedback terkait secara transaksional. Manifest dan media proyek tetap dimiliki repository proyek.
- Inference ide ditunda saat editor/preview/render/TTS aktif. Dokumen ide rusak tidak menghalangi render. Implementasi timing audio preview tidak diubah.
- Migrasi SQLite v1 → v2 menambahkan tabel ide, mempertahankan katalog serta schema manifest proyek.

Panduan dan batas detail: [daily-ideas.md](daily-ideas.md).

## Bukti pengujian

| Pemeriksaan | Hasil | Bukti |
| --- | --- | --- |
| Suite backend | PASS | **61 tes**, termasuk **23** tes baru ide harian; suite lama tetap mencakup FFmpeg render dan roundtrip paket. |
| Suite frontend | PASS | **14 tes**, termasuk regresi audio preview dan pembatalan request AI. |
| Cache/reopen/restart/hari/zona waktu/profil/bahasa | PASS | Tes penyimpanan terisolasi, tanpa akun atau proyek pengguna. |
| Onboarding, daily/manual, cooldown, dedup paralel | PASS | Request ganda tidak menambah inference; provider unavailable tidak menghabiskan jatah harian. |
| Feedback, exclude/forget/QA/source revision | PASS | Cache dan feedback sumber invalid langsung terhapus; sumber proyek tetap utuh. |
| Cancel, hasil terlambat, schema invalid, provider gagal | PASS | Hasil ditolak sebelum caching; tidak ada fallback cloud. |
| Editor/render dan penyimpanan ide rusak | PASS | Ide dibatalkan/ditunda; render tetap dapat dimulai saat dokumen ide invalid. |
| Migrasi, optimistic revision, CSRF, body budget | PASS | Katalog lama dipertahankan; versi masa depan tidak diubah. |
| Runtime Python dari bundle final | PASS | **13 pemeriksaan**: [laporan runtime](qa/daily-ideas-runtime.json), dua proses sidecar, impor PNG sungguhan, cache/feedback restart, manifest dan media tetap identik. |
| Build Next/TypeScript/Swift dan lint Python/JS | PASS | Build aplikasi final, Ruff F, pemeriksaan syntax companion JS. |
| Integritas signature bundle | PASS | `codesign --verify --deep --strict` pada app final. Signature ad-hoc, bukan notarization. |
| Tampilan/interaksi native | BELUM TERVERIFIKASI | App QA terisolasi dijalankan, tetapi Computer Use gagal memulai capture: `ScreenCaptureKit -3811` / server `-10005`. App QA kemudian ditutup dengan SIGTERM. |
| Kualitas dan inference Nano nyata pada build terintegrasi | BELUM TERVERIFIKASI | Tes transport memakai keluaran **QA FIXTURE**, bukan model. Kendala live Chrome dari Task 02 belum dinyatakan selesai. |

**75 tes otomatis lulus**, ditambah 13 pemeriksaan runtime bundle. Dua peringatan deprecation TestClient/httpx tidak menyebabkan kegagalan.

## Artefak dan pekerjaan yang masih perlu diverifikasi

- Bundle: `dist/JDH Shorts Studio.app`, versi 0.2.4 build 6, Apple Silicon/macOS 26+.
- App di `/Applications` dan installer DMG lama tidak diganti. Task ini tidak membuat DMG baru.
- QA visual saat Computer Use berfungsi: onboarding/preferensi, tiga kartu, simpan/lewati/urungkan, cache setelah kembali ke beranda, dan pembatalan saat masuk editor.
- QA Nano nyata: pair companion personal, generate tiga ide dari referensi QA, tinjau kesesuaian konsep dan schema, lalu cancel/disconnect/reopen. Tidak mengakses akun kerja atau mengubah proteksi Chrome untuk melewati pemblokiran.
- Task 05 (proposal naskah/storyboard) menunggu trigger pengguna berikutnya.
