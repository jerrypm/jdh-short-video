# Task 10 — performa video sebagai konteks ide lokal

Tanggal: 28 September 2026. Implementasi dan build **0.2.10 (12)** selesai. Provider tetap **Gemini Nano lokal melalui companion Chrome**. Task 11 belum dijalankan.

## Perubahan

- Halaman **Performa video** dari beranda: input manual, CSV UTF-8, pemetaan proyek per baris, pratinjau dan konfirmasi penyimpanan.
- Snapshot menyimpan periode inklusif, tanggal publikasi, zona waktu, definisi, sumber, waktu pengambilan, asal input dan waktu impor lokal. Kosong dibedakan dari nol; persentase lebih dari 100 diterima.
- Impor identik dilewati; konflik angka harus dikoreksi secara eksplisit dengan tampilan sebelum/sesudah. Batch atomik, revision guard, receipt idempoten dan pratinjau kedaluwarsa.
- Pengecualian anomali berlaku untuk semua snapshot satu video, termasuk impor berikutnya. Alasannya tersimpan; video dapat disertakan kembali.
- Satu snapshot per video untuk ringkasan; tidak menjumlah periode tumpang tindih. Kelompok dipisah menurut definisi, zona, umur awal dan panjang periode. Median hanya untuk metrik yang tersedia pada minimal lima video; ambang ini bukan uji signifikansi. Tidak ada klaim sebab-akibat.
- Konteks Nano dibatasi pada referensi Memori yang dipilih dan pengukuran yang disertakan. Output wajib memakai ID bukti yang valid saat menggunakan performa, dengan data pendukung yang dapat dibuka pada kartu. Ide eksperimen tetap wajib ada.
- Perubahan performa membatalkan inference aktif/cache lama; ide tersimpan diberi tanda data berubah dan dicegah menjadi draft sampai dibuat ulang. Katalog/ide/pengukuran dimutasi dalam transaksi SQLite yang sama. Migrasi v1/v2 → v3 mempertahankan dokumen lama.

Panduan dan kontrak CSV: [video-performance.md](video-performance.md).

## Validasi

- **214 tes lulus:** 173 backend, 27 frontend, 14 companion JavaScript. Pengujian mencakup validasi angka/tanggal/definisi, null versus zero, konflik, pemetaan, duplikat, migrasi, rollback, invalidasi, pengecualian lintas periode, schema/citation dan lifecycle. Tes regresi audio preview yang mencegah seek/play setiap frame tetap lulus. Dua warning deprecation berasal dari dependensi TestClient/AnyIO.
- `ruff check backend script`, TypeScript, Next static production build, Swift release build dan packaging berhasil.
- **18 pemeriksaan runtime** menggunakan Python di bundle `.app`, loopback nyata dan restart sidecar: parsing, reviewed apply, duplicate/correction, provenance, small sample, evidence ke broker, respons fixture, eksperimen, pengecualian, saved-idea staleness, manifest tidak berubah, persistence dan receipt kedaluwarsa. Laporan: `dist/JDH-Shorts-Studio-0.2.10-performance-check.json`.
- **UI native WebKit** melalui Computer Use pada jendela `JDH Shorts Studio · QA`: proyek disposable dibuat, input manual dipetakan, tanggal/angka diisi, pratinjau memisahkan `0` dari `—`, tombol simpan menunggu konfirmasi, lalu riwayat tersimpan. CSV dibuka melalui NSOpenPanel, baris tanpa project_id dipetakan di UI, ditinjau dan disimpan. Impor ulang tampil sebagai duplikat. Pengecualian video menghapusnya dari ringkasan tetapi mempertahankan angka/alasan dalam riwayat. Screenshot formulir, pratinjau, ringkasan dan CSV diperiksa langsung dalam sesi ini.
- Data QA berada pada direktori sementara terpisah; tidak membuka proyek pribadi atau akun/channel. Pengujian runtime otomatis membersihkan direktori dan menghentikan sidecar miliknya.
- Bundle akhir lolos `codesign --verify --deep --strict`; 121 file backend/frontend identik dengan source hasil build. Aplikasi QA dihentikan dan direktori sementara miliknya dihapus setelah pengujian. Rekap: `dist/JDH-Shorts-Studio-0.2.10-task10-check.json`.

## Batas yang masih berlaku

Percobaan halaman companion `http://127.0.0.1:<port>/nano/` melalui tab Chrome khusus QA kembali menghasilkan **ERR_BLOCKED_BY_CLIENT**. Tab uji ditutup. **Inference Gemini Nano nyata pada integrasi ini belum terverifikasi.** Tes model di atas adalah fixture kontrak/transport dan eksekusi JavaScript dengan fake LanguageModel, bukan bukti kualitas rekomendasi model. Tidak ada perubahan proteksi browser atau fallback cloud.

Angka diperiksa pengguna dan divalidasi aplikasi, bukan diambil/diautentikasi otomatis dari YouTube. Output alasan model tetap hipotesis yang perlu ditinjau. Tidak ada OAuth, pembacaan channel, publikasi, sinkronisasi atau riset tren otomatis.

Build `.app` terbaru ada di `dist/JDH Shorts Studio.app`. **DMG Task 09 tetap 0.2.9** dan belum memuat Task 10. Bundle masih ad-hoc signed, bukan Developer ID/notarized. Mac mini tujuan belum diuji. Database v3 menolak downgrade ke aplikasi lama; lihat panduan backup/pemulihan sebelum kembali ke 0.2.9.
