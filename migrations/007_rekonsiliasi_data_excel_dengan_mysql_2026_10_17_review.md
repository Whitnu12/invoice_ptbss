# Tinjauan rekonsiliasi data 17 Oktober 2026

## Sumber yang diperiksa

- Dump MariaDB `ptba8489_invoice (4).sql` (dibuat 17 Oktober 2026 01:21, MariaDB 10.11.19).
- Seluruh file langsung di `database_penyimpanan_aman` dan berkas di subfolder arsip/dokumen.
- Struktur database aplikasi dan migrasi bernomor 001–006.

## Kandidat yang dimasukkan skrip 007

| Kelompok | Excel | Dump SQL | Kandidat di skrip | Cara rekonsiliasi |
|---|---:|---:|---:|---|
| Header proforma invoice | 79 | 59 | 27 | Tambah jika pasangan nomor kontrak + nomor PI belum ada; lalu isi `database_master_pi` |
| Billing/invoice | 8 | 5 | 3 | Tambah invoice di tabel ternormalisasi dan legacy jika kunci kontrak + nomor invoice belum ada |
| Status/pembayaran | 4 | 5 | 2 | Tambah 2 baris valid; satu baris berisi penanda `test` dikecualikan |
| Rincian transaksi | 215 | 137 | 143 | Tambah hanya kelompok identitas item yang sama sekali tidak ada di dump; duplikasi sumber dipertahankan menurut jumlah baris sumber |

Angka di atas membandingkan snapshot. Kondisi `NOT EXISTS`/jumlah baris di SQL membuat skrip aman dijalankan ulang dan mencegah baris yang sudah ada saat eksekusi dimasukkan kembali. Jika database sudah berubah setelah dump, jumlah aktual yang masuk dapat lebih kecil.

Untuk rincian transaksi, 143 baris kandidat mencakup 112 kelompok identitas item yang tidak ditemukan di dump. Kelompok yang sudah ada tetapi memiliki nilai berbeda sengaja tidak diubah; konflik itu memerlukan keputusan bisnis sebelum dibuat sebagai `UPDATE`.

Untuk `database_proforma_invoice`, 22 baris yang cocok memiliki cap waktu Excel lebih baru daripada cap waktu SQL, tetapi nilainya memuat ketidakkonsistenan (contohnya jangka waktu berisi tanggal akhir, scope/PO yang berbeda, dan tanda kutip ekstra). Karena itu nilai baris existing mengikuti dump SQL. Skrip menyelaraskan field header tingkat kontrak memakai nilai terbaru yang konsisten di dump, mengisi tanggal kontrak kosong, lalu menerapkan header tersebut ke 27 PI baru. Field khusus PI seperti lingkup, periode, PO, WCC/WO, progress, dan tanggal PI tetap per baris. Baris existing yang lebih baru dari snapshot tidak disentuh.

## Data yang diperiksa tetapi tidak dimigrasikan otomatis

- `database_master_referensi.xlsx` (453 baris), master alat (23), plafon kontrak (3), faktur pajak online (1), timesheet history (6), dan TKDN history (2): tidak ditemukan kandidat tambahan yang aman berdasarkan pemetaan kunci; sebagian tabel SQL juga memuat baris seperti header spreadsheet, jadi tidak dibersihkan otomatis.
- Master PO (39 baris Excel) memakai model berbeda dari pasangan tabel SQL `database_master_po` (6 header) dan `database_master_po_item` (53 item). Perlu rekonsiliasi per PO dan nomor item untuk menghindari item ganda.
- Opname (136 baris Excel) berisi `doc_key`/`payload`, sedangkan `database_opname` telah dinormalisasi (58 baris). Pemetaan payload ke kolom resmi perlu peninjauan sebelum impor.
- TKDN tersimpan (44 baris Excel) tidak sama bentuknya dengan tabel `database_tkdn.params_json`; tidak dikonversi otomatis.
- BAMP/BASP/BASTB, PI tersimpan/rincian tersimpan, WCC, dan arsip dokumen berupa snapshot/berkas. Tidak ada tabel SQL yang sepadan secara langsung untuk semuanya.
- File pengguna Excel berisi kata sandi lama; tidak dimasukkan. Tabel SQL memakai `password_hash`.
- Isi folder arsip dan logo adalah berkas filesystem; skrip SQL tidak menyalin file atau mengubah path Linux pada metadata arsip.

## Catatan penerapan

Skrip 007 menambahkan data yang hilang dan menyelaraskan header kontrak pada `database_proforma_invoice`; skrip tidak menghapus baris. Jalankan pada salinan database terlebih dahulu, tinjau hasilnya, lalu terapkan ke database tujuan. Untuk memindahkan seluruh arsip dokumen, salin berkas beserta struktur folder dan sesuaikan `storage_path` terhadap lokasi server tujuan secara terpisah.
