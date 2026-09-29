# Design handoff — JDH Shorts Studio

Sumber desain: Claude Design project `8dd64ea7-b86b-41e0-bbd3-df2363e9f4fb`
(`https://claude.ai/design/p/8dd64ea7-b86b-41e0-bbd3-df2363e9f4fb`).

| File di project desain | Ukuran (ListFiles) | Isi |
| --- | --- | --- |
| `JDH Shorts Studio.dc.html` | 168 484 B | Prototipe interaktif (layar A Proyek, B Short baru, C Naskah & scene, D Editor, F Tinjau & ekspor, G Setup) |
| `JDH Handoff.dc.html` | 33 067 B | Spesifikasi: token, layout, komponen, tabel interaksi, simulasi vs implementasi |
| `support.js` | 69 150 B | `dc-runtime` generik (template `x-dc` / `sc-for` / `sc-if` di atas React). Bukan logika aplikasi. |
| `uploads/01_JDH_Shorts_Studio_Design_Prompt.md` | 14 457 B | Prompt desain (tidak dibaca; tidak dibutuhkan untuk implementasi) |

Cara impor (19 Sep 2026): `DesignSync` ditolak karena `/design-login` belum pernah dijalankan dari
terminal interaktif. File dibaca lewat Connect RPC `ListFiles`/`GetFile` di tab Chrome pemilik yang
sudah login, lalu dibaca utuh dengan `get_page_text`. Isi prototipe dan handoff terbaca lengkap.
Byte-copy file desain **tidak** disimpan di repo ini; tabel di bawah adalah transkripsi manual.

## 1. Token warna

Aksen lime hanya untuk tindakan utama, playhead, dan seleksi. Status tidak pernah dibedakan hanya
lewat warna — setiap state punya label teks, badge peringatan selalu ikon + teks.

| Nama | Hex | Pemakaian | CSS var |
| --- | --- | --- | --- |
| Latar utama | `#101216` | Kanvas app, area preview | `--bg` |
| Panel | `#191D24` | Top bar, rail, panel kiri/kanan, kartu | `--panel` |
| Panel terangkat | `#242A34` | Tombol sekunder, kartu di dalam panel | `--raised` |
| Garis pembatas | `#343D49` | Semua border 1 px | `--line` |
| Teks utama | `#F4F6F8` | Judul, isi, nilai | `--text` |
| Teks sekunder | `#A9B3C2` | Label, meta, penjelasan | `--text-2` |
| Teks tersier | `#5E6B7C` | Catatan kecil, pemisah | `--text-3` |
| Aksen lime | `#C8F56A` | Tindakan utama, playhead, seleksi | `--lime` |
| Teks di lime | `#14200B` | Label di atas tombol lime | `--on-lime` |
| Visual — garis | `#4C7FB8` | Track Visual, chip warna | `--visual` |
| Visual — isi klip | `#2A4058` | Body klip di timeline | `--visual-body` |
| Narasi | `#3E9E91` | Track Narasi, waveform `#6FD3C4` | `--narr` |
| Musik | `#7E6BC4` | Track Musik, waveform `#A796E8` | `--music` |
| Caption | `#D8B44A` | Track Caption, chip frasa | `--caption` |
| Peringatan | `#E8A33D` | Perlu diperbarui, sedang menyimpan | `--warn` |
| Error | `#E2706A` | Media hilang, hapus, gagal | `--err` |

Warna turunan yang dipakai prototipe (pill/status):

| Kind | bg | fg | border |
| --- | --- | --- | --- |
| ready | `#1B2E2B` | `#6FD3C4` | `#2F5A53` |
| warn | `#2A2416` | `#F0C177` | `#6A5326` |
| err | `#2A1D1C` | `#F0938C` | `#7A413D` |
| idle | `#101216` | `#A9B3C2` | `#343D49` |
| lime-soft | `#1E2718` | `#C8F56A` | `#5A7A33` |
| selected card | `#2A3140` bg, border `#C8F56A` | | |

Status produksi: Ide (`#101216`/`#A9B3C2`/`#343D49`), Naskah (`#182432`/`#8FBDEC`/`#34506E`),
Editing (`#1E2718`/`#C8F56A`/`#5A7A33`), Siap ekspor (`#1B2E2B`/`#6FD3C4`/`#2F5A53`),
Diekspor (`#242A34`/`#DCE3EC`/`#4A5464`), Sudah diunggah (`#2A2440`/`#BCADF0`/`#4B3F77`).

Lain: timeline lane `#15181E`, ruler `#13161B`, header track `#161A20`, transport `#13161B`,
stage bg `#0D0F13` + radial lime 4.5 %, klip narasi `#22443F`, musik `#342C52`, caption `#4A3D1C`
(border `#6E5A28`, teks `#F6E4AE`), klip kosong `#241C1C` + border dashed `#7A413D`.

## 2. Tipografi

IBM Plex Sans + IBM Plex Mono (OFL 1.1). **Prototipe memuat dari Google Fonts; implementasi
mem-bundle file font lokal** (spec §2: tidak ada CDN runtime).

| Spec | Peran | Contoh |
| --- | --- | --- |
| 38 / 600 / −0.9 | Judul dokumen | One Idea, One Short |
| 19 / 600 / −0.2 | Judul layar | Lanjutkan proyek terakhir |
| 15 / 600 | Judul dialog | Tinjau & ekspor |
| 14 / 600 | Judul panel | Kesiapan komponen |
| 13 / 400 | Isi | Tulis satu pesan yang jelas… |
| 12 / 500 | Label kontrol | Target durasi |
| 11 / 600 / caps 0.06em | Label seksi | BINGKAI |
| 16 / 600 mono | Timecode | 00:11:12 / 00:30:00 |
| 11.5 / 400 mono | Meta & angka | 9:16 · 1080×1920 · 30 fps |

Semua timecode, durasi, ukuran file, angka tabel: Plex Mono + `font-variant-numeric: tabular-nums`.

## 3. Spasi, radius, garis

Spasi: 4 (ikon↔label), 8 (isi kartu kecil, antar chip), 12 (padding kartu, antar field),
16 (padding panel, grid kartu), 24 (margin halaman proyek/setup), 32 (antar seksi besar).

Radius: 6 px (chip, badge, tombol ikon), 8 px (input, tombol kecil), 10 px (tombol utama, kartu
dalam), 12 px (kartu, panel, dialog).

Pemisah panel: garis `1px #343D49` + beda tingkat terang. Bayangan hanya untuk elemen melayang:
dialog `0 34px 90px rgba(0,0,0,.66)`, menu `0 14px 34px rgba(0,0,0,.55)`.

Motion 140–180 ms untuk panel, drawer, dialog; `prefers-reduced-motion` mematikannya.
Focus ring: 2 px lime, offset 2 px.

## 4. Layout editor & aturan resize

| Area | 1440 × 960 | 1280 × 800 | Aturan |
| --- | --- | --- | --- |
| Top bar | 56 px | 56 px | Tinggi tetap. Tombol Ekspor selalu terlihat. |
| Rail alat | 56 px | 56 px | Tidak pernah disembunyikan; ikon + label 10 px. |
| Panel kiri | 252 px | 228 px, default tertutup | Dapat ditutup. Seleksi dipertahankan saat ditutup. |
| Area tengah | sisa lebar | sisa lebar | Minimal 520 px. Preview 9:16 selalu muat penuh tanpa crop. |
| Inspector | 288 px | 256 px | Dapat ditutup menjadi rail 40 px dengan tombol buka. |
| Timeline | 248 px | 248 px | Tinggi 180–400 px lewat handle di tepi atas. |
| Baris track | 60 / 46 / 36 / 32 | 52 / 42 / 32 / 28 | Visual / Narasi / Musik / Caption. Header track 132 px. |

Panel kiri/inspector memiliki header 40 px. Ruler timeline 22 px. Toolbar timeline 36 px.
Transport 52 px. Stage preview: `aspect-ratio: 9/16`, `max-height: 544px`, radius 12.

## 5. Komponen (nama dipakai sama di kode)

| Komponen | Layar | Props | States |
| --- | --- | --- | --- |
| `ProjectCard` | A | name, durasi, terakhirDiedit, status, langkahBerikutnya, sudahDiunggah, onOpen, onMenu | default, aktif, menu terbuka |
| `SceneRow` | C, D | no, nama, rentang, narasi, teksLayar, media, status, onPick, onDrop | terpilih, media kosong, narasi usang, drop target |
| `MediaTile` | D | nama, jenis, durasi, hilang, onDragStart, onPick | default, sedang diseret, hilang |
| `PreviewPlayer` | D | scene, caption, gayaCaption, waktu, playing, areaAman, zoomTampilan | putar, jeda, media hilang |
| `TimelineClip` | D | mulai, selesai, warna, label, terpilih, kosong, onPick, onDrop | default, terpilih, kosong, perlu diperbarui |
| `TrackHeader` | D | nama, warna, tinggi, muted, onMute | default, muted |
| `CaptionStylePicker` | D, E | gaya, ukuran, posisi, duaBaris, onChange | Tebal Putih, Blok Lime, Bar Gelap |
| `InspectorSection` | D | judul, konten, dapatDitutup | klip, caption, audio, kosong |
| `CapabilityStatus` | C, D, G | nama, status, ukuran, deskripsi, aksiUtama, aksiAlternatif | belum diperiksa, perlu unduhan, mengunduh, siap, tidak tersedia, error |
| `JobProgress` | E, F, G | judul, persen, fase, onBatal, onCobaLagi | berjalan, dibatalkan, gagal, selesai |
| `ExportPanel` | F | ringkasan, preset, pemeriksaan, fase, persen, files | idle, ada masalah, berjalan, dibatalkan, selesai |

Gaya caption (prototipe `CAP_STYLES`):

| Key | Nama | Catatan | bg | fg | shadow / outline | padding | radius |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `putih` | Tebal Putih | Outline gelap 2 px | transparan | `#FFFFFF` | `0 2px 0 rgba(10,12,15,.9), 0 0 6px rgba(10,12,15,.85)` | 2/4 | 4 |
| `lime` | Blok Lime | Blok penuh, teks gelap | `#C8F56A` | `#14200B` | — | 6/12 | 8 |
| `bar` | Bar Gelap | Latar gelap 72 % | `rgba(16,18,22,.78)` | `#F4F6F8` | — | 6/12 | 8 |

Caption: ukuran 24–60 px (skala 1080 px), posisi vertikal 40–92 % (top), opsi "Batasi maksimal dua
baris", weight 800, letter-spacing −0.2, line-height 1.18, lebar maksimal 84 % (left/right 8 %).
Area aman: inset 6 % kiri/kanan, 7 % atas, 16 % bawah (zona bawah digelapkan 28 %).

## 6. Tabel interaksi

| Kontrol | Aksi | Perubahan state | Kondisi gagal |
| --- | --- | --- | --- |
| MediaTile | Seret ke SceneRow / klip Visual | clip.media diisi; status scene “Narasi siap”; autosave “Menyimpan…” → “Tersimpan” | File tidak ditemukan: klip tetap kosong, badge “Media hilang” + aksi Pilih ulang |
| TimelineClip | Klik | seleksi pindah; inspector berganti tanpa kehilangan playhead | — |
| Ruler / lane | Klik & seret | playhead, timecode, preview mengikuti; snapping ke batas klip dalam 0,35 dtk | Snapping mati: garis panduan tidak muncul |
| Play / pause | Klik / Space | playhead berjalan; berhenti otomatis di akhir | — |
| Pisah | Klik / S | klip terpilih dipecah tepat di playhead | Playhead < 0,3 dtk dari batas klip: tidak ada perubahan, tidak ada toast |
| Trim awal / akhir | Klik | clip.start / clip.end dipindah ke playhead | Playhead di luar rentang klip: diabaikan |
| Teks caption | Ketik di inspector | caption & preview berubah langsung; masuk riwayat undo | Lebih dari dua baris: preview memotong sesuai aturan gaya |
| Volume narasi / musik | Geser slider | volume track tersimpan; ducking otomatis opsional | — |
| Undo / redo | ⌘Z / ⇧⌘Z | dokumen kembali ke snapshot sebelumnya (maks. 50) | Saat mengetik di input: diabaikan |
| Tutup panel | Klik | panel kiri / inspector ditutup; seleksi & playhead tetap | — |
| Buat narasi (per segmen) | Klik di panel Narasi | JobProgress berjalan; segmen kehilangan “Perlu diperbarui” saat selesai | Gagal/dibatalkan: kembali “Perlu diperbarui”, tanpa toast sukses |
| Aksi AI naskah | “Buat 3 hook” dsb. | draf muncul di drawer; naskah tidak berubah sebelum Terapkan | Buang: tidak ada perubahan |
| Ekspor | “Mulai ekspor” | pemeriksaan → progres → MP4, WAV, SRT, paket proyek | Ada masalah: final ditahan, hanya draft. Dibatalkan: tidak ada file |
| Unduh model suara | Klik di Setup | progres unduhan → “Siap” | Batal: kembali “Perlu unduhan”; editing manual tetap jalan |
| Bersihkan cache | Klik di Setup | dialog konfirmasi → cache dihapus | Konfirmasi hanya untuk tindakan yang bisa menghilangkan pekerjaan |

Shortcut: Space (putar/jeda), ←/→ (1 frame), ⇧←/→ (1 detik), S (pisah), ⌘Z, ⇧⌘Z, Esc (tutup
dialog/drawer/menu). Semua shortcut nonaktif saat fokus di input/textarea/contenteditable.

Alur: 1 Proyek → 2 Short baru (dari ide/naskah atau dari footage) → 3 Naskah & scene →
4 Editor → 5 Tinjau & ekspor → 6 Setup (bisa dibuka kapan saja).

## 7. Simulasi di prototipe vs implementasi

Disimulasikan di prototipe (tidak boleh dianggap implementasi): waveform dari data contoh, playback
tanpa audio/video, progres narasi/unduhan/ekspor pakai timer, daftar file ekspor contoh, daftar
proyek/ide/rencana contoh, thumbnail placeholder.

Di luar scope versi awal: transkripsi otomatis, highlight per kata, analisis referensi otomatis,
batch render, generasi gambar/video, integrasi unggah YouTube, login & langganan, grafik viewers.

## 8. Selisih desain ↔ spec (keputusan)

Urutan sumber kebenaran spec §1: instruksi pengguna → batas produk spec → desain (tampilan &
interaksi) → upstream. Selisih berikut diterapkan dengan perubahan sekecil mungkin; komponen dan
layout tetap.

| # | Desain | Spec / fakta teknis | Keputusan |
| --- | --- | --- | --- |
| D1 | Render “WebCodecs + muxer lokal” | §4/§8: FFmpeg native + ffprobe | Renderer = FFmpeg lokal. Kartu “Renderer video” tetap; label jadi “FFmpeg · lokal”, “Periksa sekarang” menjalankan probe encoder nyata. |
| D2 | Penyimpanan “File System Access API” | §4: direktori proyek via layanan lokal | Proyek disimpan backend lokal di `~/Movies/JDH Shorts`. Tech row diganti. |
| D3 | TTS “id-ID”, suara “Ardi/Nadia”, 180 MB | §6/§53/§165: Kokoro, English dulu, jangan anggap Indonesia tersedia | Suara & bahasa diambil dari provider Kokoro yang terpasang (English). Label ukuran dari file nyata. Bahasa Indonesia: tulis manual + narasi impor. |
| D4 | Dropdown bahasa “Indonesia — AI & suara didukung” | §53 | Label jujur per bahasa berdasarkan probe kemampuan. |
| D5 | Font dari Google Fonts | §49: tanpa CDN runtime | IBM Plex di-bundle lokal (OFL). |
| D6 | Caption burn-in (implisit) | FFmpeg lokal tanpa libass/drawtext/freetype | Caption dirender jadi PNG oleh satu rasterizer (Pillow + Plex) dan dipakai sama persis oleh preview dan ekspor (overlay). |
| D7 | Badge “Contoh prototipe”, “Data contoh”, “Ekspor simulasi” | §2/§10: tanpa dummy | Dihapus dari UI nyata. Fixture hanya muncul berlabel. |
| D8 | Nav bar prototipe (Proyek/Naskah/Editor/Ekspor/Setup + toggle viewport) | Alat bantu prototipe | Tidak dibawa ke aplikasi; navigasi lewat tombol di layar (Proyek, Buka editor, Ekspor, Setup). |
| D9 | Durasi total terkunci 00:30:00 | Target 15/30/45/60 dtk | Durasi = panjang timeline nyata; target ditampilkan terpisah. |
