# Rencana Pengembangan Invoice & Tax Management

Dokumen ini menjadi acuan pengembangan pemindahan fitur Invoice & Tax Management dari BSS Project ke aplikasi Flask baru.

## Status saat ini

- Modul legacy Streamlit sudah tersedia di `modul_keuangan/`, tetapi belum terhubung ke UI/API Flask.
- Route `/modul/invoice-tax` masih berupa placeholder.
- Migration `migrations/001_normalisasi_kontrak_po_keuangan.sql` sudah menyediakan fondasi tabel invoice dan pembayaran normalized.
- Migration Step 1 sudah disiapkan di `migrations/002_invoice_tax_step1_data_quality.sql`, tetapi belum dieksekusi karena konfigurasi/koneksi database belum tersedia di environment development.
- File Excel legacy tetap dipertahankan sebagai sumber migrasi/kompatibilitas sampai seluruh alur baru tervalidasi.

## Cakupan fitur target

1. Invoice resmi: relasi kontrak–PO–PI–WAN/SA, customer, NPWP, DPP, jatuh tempo, Professional Sum, Estimated Sum, PPN, PPh, total netto, edit, update, Save As, rekap, dan kontrol role.
2. Dokumen invoice: preview, print/download, logo BSS, logo ISO, tanda tangan direktur, dan kuitansi.
3. Faktur pajak: referensi invoice, NPWP, NSFP, tanggal faktur, DPP, keterangan, daftar tersimpan, dan tautan Coretax DJP.
4. Pembayaran: status, tanggal penyerahan/jatuh tempo/pelunasan, TOP, potongan PPh, PPN WAPU, pembayaran aktual, selisih, aging, piutang, dan rekap per kontrak.
5. Arsip keuangan: invoice, faktur pajak, SSP PPN, SSP PPh, bukti potong, serta dokumen pendukung pembayaran.

## Tahapan pengembangan

### Step 1 — Fondasi data invoice normalized

Tujuan: memastikan struktur database target dan pemetaan data legacy siap dipakai oleh API Flask.

Pekerjaan:

- Jalankan dan validasi migration normalized.
- Validasi tabel `database_master_invoice`, `database_invoice_allocation`, dan `database_invoice_payment`.
- Validasi relasi invoice ke `master_kontrak`, `database_master_pi`, dan `database_master_po`.
- Audit hasil migrasi dari `database_billing_tax` dan `database_status_pembayaran`.
- Catat data yang belum tertampung: customer/NPWP, flag dan tarif pajak, referensi faktur pajak, serta metadata arsip/logo/tanda tangan.
- Tetapkan kontrak JSON API untuk list, detail, create, update, dan save-as invoice.

Kriteria selesai:

- Tidak ada invoice legacy valid yang kehilangan relasi kontrak.
- Nomor invoice unik dalam satu kontrak.
- Nilai DPP, PPN, PPh, dan total netto dapat direkonsiliasi dengan data legacy.
- Data pembayaran dapat ditautkan ke invoice normalized.
- Hasil audit tersimpan dan dapat diulang tanpa menggandakan data.

### Step 2 — API Invoice Resmi

Status: fondasi API dan halaman daftar sudah diimplementasikan.

- Ganti route placeholder dengan halaman Flask.
- Tambahkan endpoint list/detail/create/update/save-as/delete.
- Terapkan `can_write()` untuk role read-only.
- Tambahkan validasi kontrak, PI, PO, nomor invoice, tanggal, dan nominal.

Implementasi saat ini:

- Route halaman: `/modul/invoice-tax`.
- API list: `GET /api/modul-3/invoices`.
- API detail: `GET /api/modul-3/invoices/<invoice_id>`.
- API create: `POST /api/modul-3/invoices`.
- API update: `PUT/PATCH /api/modul-3/invoices/<invoice_id>`.
- API Save As: `POST /api/modul-3/invoices/<invoice_id>/save-as`.
- API pembatalan: `DELETE /api/modul-3/invoices/<invoice_id>`; data tidak dihapus fisik, status menjadi `DIBATALKAN`.
- Halaman awal daftar invoice: `templates/invoice_tax.html`.

### Step 3 — UI Invoice & kalkulasi pajak

Status: form dasar dan kalkulasi server-side sudah diimplementasikan.

- Form input invoice berbasis HTML/JavaScript.
- Kalkulasi Professional Sum, Estimated Sum, PPN 11%, PPh, pembulatan, dan total netto.
- Preview invoice dan download/print.

Implementasi saat ini:

- Form input tersedia di `templates/invoice_tax.html`.
- Endpoint kalkulasi preview: `POST /api/modul-3/invoices/calculate`.
- Kalkulasi memakai `Decimal` dan pembulatan `ROUND_HALF_UP`.
- Professional Sum menghitung `At Cost + Management Fee`.
- Estimated Sum menghitung diskon 10% dari gross.
- PPN dihitung 11% dari DPP jika diaktifkan.
- PPh dihitung dari management fee untuk Professional Sum, atau dari DPP untuk skema normal.
- Create/update invoice selalu menghitung ulang nilai pajak di server.

Catatan deployment: `routes.py` dan `templates/invoice_tax.html` harus di-deploy sebagai satu paket, lalu Passenger/application di-restart. Endpoint kalkulasi yang wajib tersedia adalah `/api/modul-3/invoices/calculate`.

### Step 4 — Faktur Pajak dan dokumen pembayaran

Status: referensi Faktur Pajak dan preview kuitansi sudah diimplementasikan.

- Migrasikan referensi faktur pajak ke tabel normalized.
- Tambahkan alur Coretax, NSFP, NPWP, dan tanggal faktur.
- Bangun kuitansi dan preview dokumen.

Implementasi saat ini:

- API daftar faktur pajak: `GET /api/modul-3/tax-references`.
- API simpan/update faktur pajak: `POST /api/modul-3/tax-references`.
- API hapus faktur pajak: `DELETE /api/modul-3/tax-references/<reference_id>`.
- Form referensi pajak terhubung ke halaman Modul 3.
- Tautan Coretax DJP tersedia dari halaman Modul 3.
- Preview kuitansi: `/modul/invoice-tax/receipt/<invoice_id>`.
- Kuitansi memiliki tombol cetak dan layout print dasar.

### Step 5 — Monitoring pembayaran dan aging

Status: API dan form dasar monitoring pembayaran sudah diimplementasikan.

- Form status pembayaran.
- Rekap piutang, aging, potongan, pembayaran aktual, dan selisih.
- Dashboard per kontrak dan per invoice.

Implementasi saat ini:

- API daftar monitoring: `GET /api/modul-3/payment-monitoring`.
- API simpan/update monitoring: `POST /api/modul-3/payment-monitoring`.
- Status normalized: `BELUM DIBAYAR`, `PROSES`, `DIBAYAR`.
- Perhitungan saldo piutang dan netto bank seharusnya.
- Aging dasar: `LUNAS`, `OVERDUE`, dan `BELUM JATUH TEMPO`.
- Ringkasan jumlah invoice dan total piutang tampil di halaman Modul 3.

### Step 6 — Arsip, role, audit, dan cutover

Status: implementasi arsip dan audit trail sudah disiapkan; menunggu eksekusi migration database dan uji di server.

Implementasi saat ini:

- Migration `migrations/003_invoice_tax_archive_audit.sql` membuat metadata arsip dan tabel audit trail.
- Arsip disimpan pada `database_penyimpanan_aman/arsip_invoice_tax` dengan nama file UUID agar tidak bentrok dan tidak mudah ditebak.
- API daftar arsip: `GET /api/modul-3/archives`.
- API upload arsip: `POST /api/modul-3/archives` dengan validasi role, tipe dokumen, ekstensi, dan batas ukuran 15 MB.
- API download arsip: `GET /api/modul-3/archives/<archive_id>/download`.
- API soft-delete arsip: `DELETE /api/modul-3/archives/<archive_id>`.
- API audit trail: `GET /api/modul-3/audit-log`, dibatasi untuk role pengelola/management/direksi/finance/tax.
- Operasi create/update/save-as/cancel invoice, faktur pajak, pembayaran, dan arsip mencatat audit trail.
- Halaman Modul 3 sudah memiliki form upload dan daftar arsip aktif.

Urutan cutover:

1. Jalankan `003_invoice_tax_archive_audit.sql` pada database target.
2. Deploy `routes.py`, `templates/invoice_tax.html`, `templates/invoice_receipt.html`, dan migration terkait dalam satu rilis.
3. Buat/izinkan folder `database_penyimpanan_aman/arsip_invoice_tax` agar dapat ditulis oleh user proses aplikasi.
4. Restart Passenger/aplikasi, lalu uji upload, download, soft-delete, dan audit log.
5. Jalankan uji paralel dengan modul legacy dan lakukan rekonsiliasi sebelum API Flask dijadikan sumber utama.

### Step 7 — Integrasi sumber data BSS untuk input invoice

Status: sumber data master PI dan transaksi BSS sudah dihubungkan ke form invoice.

Implementasi saat ini:

- Endpoint `GET /api/modul-3/invoice-sources` mengambil daftar nomor kontrak dari `database_proforma_invoice`.
- Pemilihan nomor kontrak memuat daftar nomor PI dari master PI BSS.
- Pemilihan nomor PI memuat PO, customer, alamat, WAN/SA, detail transaksi, dan nilai gross sumber.
- Create invoice memvalidasi kombinasi kontrak + PI terhadap database BSS sebelum menyimpan.
- `kontrak_id` tidak lagi menjadi input utama pengguna; ID diselesaikan dari nomor kontrak pada `master_kontrak`.
- Nomor invoice resmi tetap diinput accounting karena diterbitkan setelah dokumen PI/proforma tersedia.
- Nilai gross awal, customer, alamat, nomor PO, dan WAN/SA mengikuti data sumber BSS; pengguna tetap dapat melengkapi parameter pajak dan tanggal invoice.

### Step 8 — Pencarian dan pengelolaan invoice resmi

Status: pencarian invoice, edit, dan Save As sudah ditambahkan ke UI Modul 3.

- Cari invoice berdasarkan nomor invoice, nomor PI, atau customer.
- Muat invoice tersimpan ke form untuk diedit.
- Tarif PPh dan flag PPN/PPh ikut dimuat kembali dan dapat disesuaikan.
- Simpan perubahan memakai `PUT /api/modul-3/invoices/<invoice_id>`.
- Buat salinan memakai `POST /api/modul-3/invoices/<invoice_id>/save-as`.
- Pencarian invoice memakai dropdown yang menampilkan seluruh invoice saat dibuka dan menyaring berdasarkan nomor invoice, kontrak, PI, atau customer ketika diketik.
- Invoice baru tetap menerima nomor invoice resmi yang diinput manual oleh Accounting.
- Halaman Modul 3 dibagi menjadi tab Invoice Resmi, Faktur Pajak, Pembayaran, dan Arsip Dokumen. Form pendukung memilih nomor invoice, bukan mengetik ID database.

### Step 9 — Pemilihan invoice sebagai pintu masuk

Status: UI selection-first sudah diterapkan.

- Daftar invoice resmi dan pencarian tampil terlebih dahulu saat halaman dibuka, sejalan dengan pola pemilihan data pada Modul Database dan Invoice & Dokumen.
- Pengguna dapat menekan nomor invoice pada tabel, memilih dari dropdown pencarian, atau mengetik nomor yang persis lalu menekan **Buka Invoice**. Tabel awal hanya menampilkan lima kolom data; tautan kuitansi muncul setelah invoice dibuka.
- Form dan tab pekerjaan baru ditampilkan setelah invoice dipilih. Pengguna read-only tetap bisa membuka detail.
- Form Faktur Pajak, Pembayaran, dan Arsip mengacu pada invoice aktif; daftar pembayaran dan arsip juga ditampilkan untuk invoice tersebut.
- **Invoice Baru** membuka form kosong untuk input nomor resmi secara manual; tab Faktur Pajak, Pembayaran, dan Arsip baru aktif setelah invoice tersimpan.
- Setelah create atau Save As, invoice hasil penyimpanan tetap menjadi invoice aktif sehingga pengguna dapat melanjutkan proses berikutnya tanpa memilih ulang.

### Step 10 — Daftar 10 per halaman dan tracking pembayaran per invoice

Status: implementasi UI/API lokal selesai; perlu validasi terhadap data produksi setelah deploy.

- Seluruh baris invoice dapat dibuka melalui klik atau Enter/Spasi. Daftar menampilkan maksimal 10 invoice per halaman dengan navigasi angka halaman seperti Modul Database.
- Tab Pembayaran hanya menampilkan ringkasan invoice aktif: tagihan, penerimaan bank, sisa piutang, dan aging. Header/tabel daftar invoice ganda di tab ini dihapus.
- Form tracking memuat satu catatan pembayaran terbaru per invoice dan mengisi otomatis nomor invoice, nominal tagihan, serta jatuh tempo. Pengguna hanya mencatat tanggal aktual, nominal diterima, potongan, dan catatan transfer. Status, selisih, dan durasi dihitung di server.
- Tagihan bruto mengikuti DPP + PPN dari invoice; potongan PPh/WAPU tidak mengurangi nilai tagihan, tetapi diperhitungkan dalam saldo dan perkiraan penerimaan bank. Nilai tagihan legacy 0 ditampilkan memakai nilai invoice tanpa mengubah database diam-diam.
- Status lama `DIBAYAR` dengan saldo masih terbuka diberi peringatan verifikasi dan tidak lagi otomatis diberi aging `LUNAS`.
- Skema saat ini adalah satu catatan ringkasan per invoice, bukan jurnal beberapa transfer/cicilan. Jika histori cicilan per transaksi dibutuhkan, perlu tabel/detail pembayaran terpisah pada tahap berikutnya.

## Pemetaan data awal

| Legacy | Target normalized | Catatan |
|---|---|---|
| `Nomor Invoice Resmi` | `database_master_invoice.nomor_invoice` | Unik per kontrak |
| `Kontrak No.` | `database_master_invoice.kontrak_id` | Resolusi melalui `master_kontrak` |
| `Nomor SA / WAN` | `nomor_sa_wan` | Disimpan sebagai referensi sumber |
| `Tanggal Invoice` | `tanggal_invoice` | Tipe DATE |
| `Jatuh Tempo` | `jatuh_tempo` | Tipe DATE |
| `Nilai Invoice` | `nilai_dpp` | DPP setelah skema diskon/fee |
| `At Cost` | `add_cost` | Perlu konfirmasi istilah bisnis |
| `Management Fee` | `management_fee` | Professional Sum |
| `PPN Nominal` | `ppn_nominal` | Legacy menggunakan 11% |
| `PPh Nominal` | `pph_nominal` | Tarif perlu disimpan terpisah pada tahap berikutnya |
| `Total Netto` | `total_netto` | DPP + PPN - PPh |
| Status pembayaran legacy | `database_invoice_payment` | Ditautkan melalui `invoice_id` |

## Catatan keputusan teknis

- Database MySQL normalized menjadi sumber data target.
- Excel legacy tidak langsung dihapus.
- Perhitungan nominal harus menggunakan `Decimal` pada layer aplikasi/API.
- Role Management/Direksi tetap read-only.
- Semua operasi tulis harus memakai transaksi database dan audit log.

## Review database terbaru — 13 Oktober 2026

Sumber review: `C:\Users\ThinkPad T14 G2\Downloads\ptba8489_invoice (1).sql`. File diperlakukan sebagai dump/schema referensi dan tidak dieksekusi selama review.

### Kondisi yang sudah baik

- Database sudah berisi tabel normalized `database_master_invoice`, `database_invoice_allocation`, dan `database_invoice_payment`.
- `database_master_invoice` sudah memiliki 5 invoice aktif dengan relasi `kontrak_id` dan unique key per kontrak/nomor invoice.
- `database_billing_tax` sudah memiliki `invoice_id` yang merujuk ke invoice normalized.
- `master_kontrak`, `database_master_pi`, `database_master_po`, dan item PO sudah memiliki relasi foreign key utama.
- View `vw_kontrak_summary` dan `vw_po_summary` sudah tersedia.
- Migration log menunjukkan `001_normalisasi_kontrak_po_keuangan` sudah dicatat pada 11 Oktober 2026.

### Temuan yang harus ditangani sebelum Step 1 selesai

1. `database_invoice_allocation` belum memiliki data. Relasi invoice langsung ke PI/PO belum dapat dipakai untuk rekonsiliasi allocation.
2. `database_invoice_payment` belum memiliki data. Data pembayaran masih berada di `database_status_pembayaran` legacy.
3. `database_status_pembayaran` memiliki satu baris header sebagai data (`Nomor Kontrak`, `Nomor Invoice`, dan seterusnya) sehingga wajib difilter saat backfill.
4. `master_kontrak` memiliki record dummy `id=6` dengan nomor `Nomor Kontrak`; record ini tidak boleh dihitung sebagai kontrak bisnis.
5. Nilai nomor faktur pajak legacy ada yang tersimpan sebagai notasi ilmiah (`3.0026E+15`), sehingga perlu audit sumber dan koreksi manual/aturan pemulihan sebelum dianggap valid.
6. `database_faktur_pajak_online` masih legacy: tidak memiliki primary key/unique key, tanggal dan nilai DPP disimpan sebagai `varchar`, dan `nilai_dpp varchar(9)` terlalu sempit untuk nominal invoice besar.
7. Data customer/NPWP, flag kena PPN/PPh, dan tarif PPh belum tersedia di `database_master_invoice`; saat ini masih berada di `database_billing_tax` atau tabel legacy.
8. Dump menggunakan beberapa tabel legacy dengan `latin1`, sedangkan tabel normalized menggunakan `utf8mb4`; standardisasi encoding perlu dipastikan sebelum API baru membaca seluruh data.
9. View memakai `DEFINER=ptba8489@localhost`; pada server target user tersebut harus tersedia atau view perlu dibuat ulang dengan definisi yang sesuai.
10. Dump menggunakan `SET time_zone = '+00:00'`, sementara aplikasi beroperasi untuk timezone Asia/Jakarta; timestamp audit perlu distandarkan.

### Keputusan untuk Step 1

- Jangan menghapus atau mengubah tabel legacy terlebih dahulu.
- Jadikan `database_master_invoice` sebagai sumber utama invoice normalized.
- Backfill `database_invoice_allocation` dari `pi_no` dan `nomor_po` dengan validasi keberadaan PI/PO.
- Backfill `database_invoice_payment` dari `database_status_pembayaran` setelah membuang baris header/dummy dan menormalkan tanggal, status, nominal, serta nomor faktur pajak.
- Tambahkan tabel/kolom normalized untuk referensi faktur pajak dan metadata customer sebelum UI faktur pajak dibuat.
- Buat laporan audit: invoice legacy, invoice normalized, allocation, payment, unmatched PI/PO, dummy data, dan data pajak bermasalah.

Status implementasi Step 1: migration SQL selesai dibuat dan telah melalui pemeriksaan statis. Eksekusi database menunggu `DB_HOST`, `DB_NAME`, `DB_USER`, dan `DB_PASSWORD` yang valid.
