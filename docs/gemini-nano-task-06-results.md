# Task 06 — timing narasi dan caption

24 September 2026. Implementasi **0.2.6 build 8**, Apple Silicon/macOS 26+. Task 07–11 belum dimulai. Provider AI tetap **Gemini Nano lokal**; Task 06 menggunakan pengukuran audio deterministik tanpa inference, cloud, API key, maupun dependency model tambahan.

## Perubahan

- **Timing & caption** di toolbar: analisis file narasi, deteksi jeda, minimum durasi scene yang menjaga seluruh audio, pilihan mempertahankan/mengurangi ruang setelah file, dan review per scene.
- Caption dengan layout berdasarkan font aktual, baris otomatis seimbang, Enter manual, validasi maksimal dua baris, serta peringatan karakter/detik. Layout dipakai bersama oleh PNG preview, render, dan SRT. Timestamp tetap berdasarkan batas scene terukur; tidak ada klaim alignment kata.
- Apply sebagian scene dengan revision/media guard, atomic save, backup, idempotent retry, Undo/Redo. Edit setelah review mengharuskan pemeriksaan ulang. Menutup dialog tidak mengubah proyek.
- Ekspor memakai PCM/MOV sementara dan satu encoding AAC setelah penggabungan, menghilangkan akumulasi priming/padding AAC antar-scene pada fixture.
- Indikator save diperbaiki ketika Undo → Redo cepat kembali ke nilai tersimpan sebelum autosave berjalan.

Panduan dan batas implementasi: [pacing-and-captions.md](pacing-and-captions.md).

## Pengujian otomatis dan runtime

| Pemeriksaan | Hasil |
| --- | --- |
| Backend | **103 tes lulus**, termasuk 18 kasus Task 06. |
| Frontend | **18 tes lulus**, termasuk 8 regresi controller audio (seek, pause/resume, EOF, preload scene berikutnya, musik loop, readiness/error, render saat AI sibuk). |
| PCM/silence | Durasi aktual, trim, jeda awal/tengah/akhir, seluruh audio sunyi, stereo berlawanan fase, audio terlalu panjang/hilang diperiksa. |
| Perlindungan proyek | Penolakan pemotongan ucapan, video pendek, total lebih dari 180 detik, caption berlebih, scene/field invalid, revision/file berubah, expiry, request body/auth/CSRF; kegagalan atomic write dan retry diuji. |
| Build/checks | Next build + TypeScript, Swift release, Ruff F, signature ad-hoc dan kesesuaian backend bundle lulus. |
| Runtime Python bundle | **14 pemeriksaan lulus**: Kokoro English nyata, PCM, review/apply/backup, trim, draft/final, waveform lengkap, SRT, Undo/Redo, musik loop, restart dan shutdown. |

Bukti terstruktur: [pacing-runtime.json](qa/pacing-runtime.json). Jalankan ulang dengan `script/verify_pacing_runtime.py`; seluruh data bersifat sementara dan dibersihkan. Dua warning deprecation TestClient/httpx masih ada, tanpa kegagalan tes.

Uji awal menemukan drift onset **+20 ms** pada scene pertama dan **+50 ms** pada scene kedua. Setelah perbaikan renderer, onset tone draft/final dan campuran musik adalah **0,30 / 1,60 / 3,30 / 4,60 detik**, sesuai timeline preview pada jendela pengukuran **10 ms**. WAV narasi tepat 10,5 detik; semua sampel suara Kokoro yang diukur tetap ada pada posisi scene yang diharapkan. Decode AAC 10,5173125 detik mencakup padding akhir sekitar 17 ms; angka itu tidak berarti scene visual ditambah.

## QA UI

Alur yang diuji: beranda proyek QA → editor → Timing & caption → analisis → ubah/pilih scene → periksa → apply → Undo → Redo.

Environment: Codex in-app browser melalui **computer use/CUA**, URL loopback sementara `127.0.0.1:58862`, lalu fixture final `127.0.0.1:59162`. Browser plugin/skill terpisah tidak tersedia; seluruh interaksi tetap memakai CUA, bukan Playwright eksternal. Screenshot pertama berukuran 1024×961 dan menampilkan modal review dua kolom yang dapat digulir. Tab dan runtime sementara ditutup setelah QA; URL tersebut bukan server produk yang harus dijalankan pengguna.

| Pemeriksaan UI | Hasil dan bukti teramati |
| --- | --- |
| Identitas halaman | Judul JDH Shorts Studio dan nama proyek Task 06 · QA timing sesuai. |
| Halaman tidak kosong / overlay framework | Konten editor, modal, kontrol dan hasil analisis tampil; tidak ada overlay error framework. |
| Console | Tidak ada warning/error relevan pada tab yang diuji. |
| Screenshot | Modal terlihat dengan durasi asli, durasi audio, jeda, input frame, caption, serta pilihan scene. Screenshot ditampilkan inline saat pengujian, tidak diklaim sebagai file lokal. |
| Proteksi pemotongan | Durasi 89 frame untuk audio 90 frame menghasilkan pesan penolakan; tidak diterapkan. |
| Review dan partial apply | Satu dari tiga scene diubah 5 → 3 detik; dua scene lain tetap 5 detik. Caption manual dua baris dipertahankan. Total 15 → 13 detik. |
| Invalidasi review | Edit caption setelah review menghilangkan tombol Terapkan hingga pemeriksaan diulang. |
| Undo / Redo | UI kembali 5 detik, lalu 3 detik. Fixture final membuktikan indikator kembali Tersimpan setelah Undo/Redo cepat. |
| Tutup tanpa apply | Analisis kedua ditutup tanpa mengubah durasi scene yang tersimpan. |
| Tidak ada audio | UI menyatakan durasi ucapan belum terukur; durasi manual dan caption per scene tetap dapat direview. |
| Playback audio nyata | Media browser berada dalam keadaan playing, seek saat pause tepat ke 1,233333 detik; beralih ke narasi berikutnya dan selesai pada EOF 4 detik tanpa replay. |
| Playback ketika AI sibuk | Broker fixture berlabel QA berada pada status running selama playback/resume dan EOF; tidak ada error console. Ini tidak mengukur beban komputasi inference Nano nyata. |
| Native macOS/WebKit | **Belum diuji ulang**: computer use melaporkan Mac terkunci dan automatic unlock gagal. Pengguna telah diminta membuka kunci. Browser QA tidak menggantikan bukti WebKit native. |

Perintah/API utama: pytest, npm test, build_and_run.sh --build, verify_pacing_runtime.py, codesign; CUA createBrowserTab → AX/DOM snapshot → scoped click/fill/check → screenshot → read-only media state → console logs. Tidak membuka akun kerja, proyek pengguna, atau tab Chrome pengguna.

## Batas yang masih berlaku

- Tidak ada ASR/forced alignment atau timestamp per kata; penilaian jeda dapat keliru untuk suara pelan/noise. Audio tidak dipotong berdasarkan hasil deteksi.
- English Kokoro adalah satu-satunya fixture ujaran nyata pada pengujian ini. Bahasa Indonesia/multilingual, kualitas keterbacaan lintas bahasa, dan Mac mini tujuan belum divalidasi.
- Preview menggunakan media clock browser dan bisa memiliki startup latency; onset file ekspor yang sesuai timeline tidak membuktikan sinkronisasi speaker/layar native di semua perangkat.
- Inference Nano terintegrasi masih memiliki keterbatasan Task 05 (`ERR_BLOCKED_BY_CLIENT` pada Chrome personal); tidak ada klaim bahwa fixture membuktikan inference nyata.
- Bundle `dist/JDH Shorts Studio.app` tersedia untuk lokal. Installer DMG, notarization, dan pemasangan ke `/Applications` tidak diubah pada Task 06.
