# Task 05 — proposal naskah dan storyboard

24 September 2026. Implementasi tersedia pada **0.2.5 build 7**, tetap menggunakan **Gemini Nano lokal melalui companion Chrome**. Task 06–11 belum dimulai.

## Yang ditambahkan

- **Susun draft** pada kartu ide harian/tersimpan dan **Draft dari ide** di editor English, dengan pemilihan proyek tujuan.
- Proposal hook dan scene: narasi, caption singkat, perkiraan frame 30 fps, visual yang diperlukan, ID media, status media tersedia/belum ada, sumber proyek dan maksud framing.
- Review per scene: edit teks/durasi/media, pilih sebagian scene, lalu append atau ganti seluruh scene/naskah. Ringkasan dan konfirmasi dihapus jika proposal diedit lagi.
- Apply atomik memakai revision guard, backup repository, retry idempotent dalam sesi, serta Undo/Redo editor. Sumber, media dan hasil yang kedaluwarsa ditolak.
- Durasi scene minimal sepanjang audio terukur yang transkripnya cocok. Audio tidak dipotong untuk mengikuti perkiraan. Video terlalu pendek ditolak.
- Efek yang diterima hanya **static**, memakai cut renderer yang sudah ada. Catatan framing tidak dieksekusi sebagai animasi/filter. Implementasi animasi tetap Task 07.
- Catatan proposal yang diterapkan disimpan pada field scene `planning` yang opsional dan terlihat di halaman Naskah & scene. Proyek lama tetap dapat dibaca oleh build baru; preview audio, media, volume, caption style dan atomic save dipertahankan.

Panduan lengkap: [storyboard-proposals.md](storyboard-proposals.md).

## Pengujian

| Pemeriksaan | Hasil | Bukti |
| --- | --- | --- |
| Backend | PASS | **85 tes**, termasuk **24 tes Task 05**. |
| Frontend | PASS | **17 tes**, termasuk **3 tes Task 05** dan regresi audio preview. |
| Generation gagal/invalid tanpa mengubah proyek | PASS | Asset/source palsu, durasi negatif/pecahan, efek tidak didukung, status media tidak cocok, hook tidak konsisten, payload tambahan dan total terlalu panjang ditolak. |
| Partial apply, append/replace, backup, retry dan Undo | PASS | Naskah/scene awal dipertahankan sampai apply; apply ulang identik tidak menduplikasi scene; sesudah Undo, replay ditolak. |
| Concurrent project/source/profile/exclusion/media change | PASS | Revalidasi sebelum review/apply menolak proposal lama. |
| Audio terukur dan video pendek | PASS | Audio memperpanjang scene tanpa trim; transkrip berbeda atau visual terlalu pendek ditolak. |
| Write gagal, cancel-before-submit, expiry/restart | PASS | Manifest sebelumnya tetap utuh; sesi proposal tidak dijalankan ulang. |
| Auth, CSRF, batas body, konteks tanpa path | PASS | Endpoint generik AI menolak input storyboard yang tidak dikurasi server. |
| Build Next/TypeScript/Swift, Ruff F, syntax companion | PASS | Bundle 0.2.5 build 7 melalui script proyek. |
| Integritas bundle final | PASS | `codesign --verify --deep --strict`; versi/build dan kesesuaian source backend bundle diperiksa. Signature ad-hoc, bukan notarization. |
| Runtime bundle dengan PNG/WAV sungguhan | PASS | **15 pemeriksaan**, dua proses Python bundle; [bukti runtime](qa/storyboard-runtime.json). |
| UI aplikasi native | PASS untuk alur fixture | Pemilihan ide/proyek, progress, edit caption, penerapan satu scene, invalidasi review, konfirmasi, apply, Undo, Redo, serta penutupan proposal tanpa apply. [Bukti UI](qa/storyboard-native-ui.json). |
| Inference Nano nyata pada build terintegrasi | BELUM TERVERIFIKASI | Percobaan membuka companion di Chrome personal kembali ditolak dengan `ERR_BLOCKED_BY_CLIENT`. Tab uji ditutup; pengaturan/proteksi Chrome tidak diubah. |

**102 tes otomatis lulus**, ditambah **15 pemeriksaan runtime bundle**. Dua warning deprecation TestClient/httpx tidak menyebabkan kegagalan. Runtime dan UI memakai output **QA FIXTURE**, bukan bukti kualitas atau inference Gemini Nano nyata.

## Batas dan artefak

- Bundle: `dist/JDH Shorts Studio.app`, versi 0.2.5 build 7, Apple Silicon/macOS 26+.
- Proposal berlaku maksimal 15 menit dan tidak dipersistenkan lintas restart. Catatan scene hasil apply dipersistenkan bersama proyek. Undo/Redo tetap mengikuti umur sesi editor; backup proyek tersedia terpisah.
- Shape/source validation tidak membuktikan kebenaran klaim. Review fakta, pengalaman pribadi, sumber dan media tetap diperlukan.
- Bahasa Indonesia, animasi, alignment kata, dan pemeriksaan Shorts tidak ditambahkan pada task ini.
- App QA dan companion fixture ditutup sesudah pengujian. Seluruh data uji berada di direktori sementara; tidak mengakses akun kerja, tab/riwayat browser lain atau proyek/media pengguna.
- App `/Applications` dan DMG lama tidak diganti. DMG baru tetap berada pada task distribusi berikutnya.
- Task 06 menunggu trigger berikutnya.
