-- ================================================================
-- BSS INVOICE - MIGRASI 001
-- Normalisasi Master Kontrak, PO, PI, Realisasi, Invoice, Pembayaran
--
-- Target : MariaDB 10.11 / MySQL 8+
-- Sifat  : additive dan kompatibel dengan database lama
--
-- KESELAMATAN
-- 1. Script ini TIDAK menghapus, mengganti nama, atau mengosongkan tabel lama.
-- 2. Kolom relasi baru sengaja nullable agar modul lama tetap berjalan.
-- 3. Nomor bisnis lama tetap dipertahankan sebagai sumber kompatibilitas.
-- 4. Jalankan backup database terlebih dahulu.
-- 5. Jalankan satu kali pada database yang sudah berisi dump saat ini.
-- ================================================================

SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO';
SET NAMES utf8mb4;

-- ================================================================
-- A. MASTER KONTRAK
-- ================================================================

CREATE TABLE IF NOT EXISTS master_kontrak (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    nomor_kontrak VARCHAR(100) NOT NULL,
    nomor_tender VARCHAR(100) NULL,
    judul_kontrak TEXT NULL,
    lingkup_pekerjaan TEXT NULL,
    customer VARCHAR(255) NULL,
    alamat_customer TEXT NULL,
    tanggal_kontrak DATE NULL,
    tanggal_mulai DATE NULL,
    tanggal_selesai DATE NULL,
    plafon_kontrak DECIMAL(20,2) NOT NULL DEFAULT 0.00,
    mata_uang VARCHAR(10) NOT NULL DEFAULT 'IDR',
    status_kontrak VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    versi_kontrak INT NOT NULL DEFAULT 1,
    keterangan TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_master_kontrak_nomor (nomor_kontrak),
    KEY idx_master_kontrak_status (status_kontrak),
    KEY idx_master_kontrak_customer (customer)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS master_kontrak_amendment (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    kontrak_id BIGINT UNSIGNED NOT NULL,
    nomor_amendment VARCHAR(100) NULL,
    tanggal_amendment DATE NULL,
    plafon_sebelum DECIMAL(20,2) NOT NULL DEFAULT 0.00,
    perubahan_nilai DECIMAL(20,2) NOT NULL DEFAULT 0.00,
    plafon_setelah DECIMAL(20,2) NOT NULL DEFAULT 0.00,
    dokumen_path VARCHAR(500) NULL,
    keterangan TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_kontrak_amendment (kontrak_id, nomor_amendment),
    KEY idx_amendment_kontrak (kontrak_id),
    CONSTRAINT fk_amendment_kontrak
        FOREIGN KEY (kontrak_id) REFERENCES master_kontrak(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ================================================================
-- B. ISI MASTER KONTRAK DARI DATA LAMA
-- ================================================================

INSERT IGNORE INTO master_kontrak
    (nomor_kontrak, nomor_tender, judul_kontrak, lingkup_pekerjaan,
     customer, alamat_customer, plafon_kontrak)
SELECT
    TRIM(p.`Nomor Kontrak`),
    MAX(NULLIF(TRIM(p.`Nomor Tender`), '')),
    MAX(NULLIF(TRIM(p.`Judul Kontrak`), '')),
    MAX(NULLIF(TRIM(p.`Lingkup Pekerjaan`), '')),
    MAX(NULLIF(TRIM(p.`Pihak Pertama`), '')),
    MAX(NULLIF(TRIM(p.`Alamat Pihak Pertama`), '')),
    COALESCE(MAX(CAST(NULLIF(TRIM(pk.total_nilai_kontrak), '') AS DECIMAL(20,2))), 0)
FROM database_proforma_invoice p
LEFT JOIN database_plafon_kontrak pk
    ON CONVERT(TRIM(pk.nomor_kontrak) USING utf8mb4) COLLATE utf8mb4_unicode_ci =
       CONVERT(TRIM(p.`Nomor Kontrak`) USING utf8mb4) COLLATE utf8mb4_unicode_ci
WHERE p.`Nomor Kontrak` IS NOT NULL
  AND TRIM(p.`Nomor Kontrak`) NOT IN ('', '-', '0')
GROUP BY TRIM(p.`Nomor Kontrak`);

INSERT IGNORE INTO master_kontrak (nomor_kontrak, plafon_kontrak)
SELECT TRIM(nomor_kontrak),
       CAST(NULLIF(TRIM(total_nilai_kontrak), '') AS DECIMAL(20,2))
FROM database_plafon_kontrak
WHERE nomor_kontrak IS NOT NULL
  AND TRIM(nomor_kontrak) NOT IN ('', '-', '0');

INSERT IGNORE INTO master_kontrak (nomor_kontrak)
SELECT DISTINCT TRIM(nomor_kontrak)
FROM database_master_po
WHERE nomor_kontrak IS NOT NULL
  AND TRIM(nomor_kontrak) NOT IN ('', '-', '0');

INSERT IGNORE INTO master_kontrak (nomor_kontrak)
SELECT DISTINCT TRIM(nomor_kontrak)
FROM database_transaksi_rincian
WHERE nomor_kontrak IS NOT NULL
  AND TRIM(nomor_kontrak) NOT IN ('', '-', '0');

INSERT IGNORE INTO master_kontrak (nomor_kontrak)
SELECT DISTINCT TRIM(nomor_kontrak)
FROM database_billing_tax
WHERE kontrak_no IS NOT NULL
  AND TRIM(kontrak_no) NOT IN ('', '-', '0');

-- Sinkronkan plafon lama ke master kontrak jika sebelumnya masih nol.
UPDATE master_kontrak k
JOIN database_plafon_kontrak p
  ON CONVERT(TRIM(p.nomor_kontrak) USING utf8mb4) COLLATE utf8mb4_unicode_ci =
     CONVERT(k.nomor_kontrak USING utf8mb4) COLLATE utf8mb4_unicode_ci
SET k.plafon_kontrak = CAST(NULLIF(TRIM(p.total_nilai_kontrak), '') AS DECIMAL(20,2))
WHERE k.plafon_kontrak = 0
  AND NULLIF(TRIM(p.total_nilai_kontrak), '') IS NOT NULL;

-- ================================================================
-- C. RELASI KONTRAK PADA TABEL LAMA
--    Semua kolom baru nullable untuk menjaga kompatibilitas.
-- ================================================================

ALTER TABLE database_master_po
    ADD COLUMN IF NOT EXISTS kontrak_id BIGINT UNSIGNED NULL AFTER id,
    ADD KEY IF NOT EXISTS idx_master_po_kontrak_id (kontrak_id);

ALTER TABLE database_master_referensi
    ADD COLUMN IF NOT EXISTS kontrak_id BIGINT UNSIGNED NULL AFTER id,
    ADD KEY IF NOT EXISTS idx_master_referensi_kontrak_id (kontrak_id);

ALTER TABLE database_transaksi_rincian
    ADD COLUMN IF NOT EXISTS kontrak_id BIGINT UNSIGNED NULL AFTER nomor_kontrak,
    ADD KEY IF NOT EXISTS idx_transaksi_kontrak_id (kontrak_id);

ALTER TABLE database_opname
    ADD COLUMN IF NOT EXISTS kontrak_id BIGINT UNSIGNED NULL AFTER id,
    ADD KEY IF NOT EXISTS idx_opname_kontrak_id (kontrak_id);

ALTER TABLE database_po_realisasi
    ADD COLUMN IF NOT EXISTS kontrak_id BIGINT UNSIGNED NULL AFTER id,
    ADD KEY IF NOT EXISTS idx_realisasi_kontrak_id (kontrak_id);

ALTER TABLE database_po_mapping_rule
    ADD COLUMN IF NOT EXISTS kontrak_id BIGINT UNSIGNED NULL AFTER id,
    ADD KEY IF NOT EXISTS idx_mapping_kontrak_id (kontrak_id);

ALTER TABLE database_billing_tax
    ADD COLUMN IF NOT EXISTS kontrak_id BIGINT UNSIGNED NULL AFTER nomor_invoice,
    ADD COLUMN IF NOT EXISTS invoice_id BIGINT UNSIGNED NULL AFTER kontrak_id,
    ADD KEY IF NOT EXISTS idx_billing_kontrak_id (kontrak_id),
    ADD KEY IF NOT EXISTS idx_billing_invoice_id (invoice_id);

ALTER TABLE database_status_pembayaran
    ADD COLUMN IF NOT EXISTS kontrak_id BIGINT UNSIGNED NULL AFTER nomor_kontrak,
    ADD COLUMN IF NOT EXISTS invoice_id BIGINT UNSIGNED NULL AFTER kontrak_id,
    ADD KEY IF NOT EXISTS idx_pembayaran_kontrak_id (kontrak_id),
    ADD KEY IF NOT EXISTS idx_pembayaran_invoice_id (invoice_id);

UPDATE database_master_po p
JOIN master_kontrak k ON CONVERT(k.nomor_kontrak USING utf8mb4) COLLATE utf8mb4_unicode_ci =
                        CONVERT(TRIM(p.nomor_kontrak) USING utf8mb4) COLLATE utf8mb4_unicode_ci
SET p.kontrak_id = k.id
WHERE p.kontrak_id IS NULL;

UPDATE database_master_referensi r
JOIN master_kontrak k ON CONVERT(k.nomor_kontrak USING utf8mb4) COLLATE utf8mb4_unicode_ci =
                        CONVERT(TRIM(r.nomor_kontrak) USING utf8mb4) COLLATE utf8mb4_unicode_ci
SET r.kontrak_id = k.id
WHERE r.kontrak_id IS NULL;

UPDATE database_transaksi_rincian t
JOIN master_kontrak k ON CONVERT(k.nomor_kontrak USING utf8mb4) COLLATE utf8mb4_unicode_ci =
                        CONVERT(TRIM(t.nomor_kontrak) USING utf8mb4) COLLATE utf8mb4_unicode_ci
SET t.kontrak_id = k.id
WHERE t.kontrak_id IS NULL;

UPDATE database_opname o
JOIN master_kontrak k ON CONVERT(k.nomor_kontrak USING utf8mb4) COLLATE utf8mb4_unicode_ci =
                        CONVERT(TRIM(o.nomor_kontrak) USING utf8mb4) COLLATE utf8mb4_unicode_ci
SET o.kontrak_id = k.id
WHERE o.kontrak_id IS NULL;

UPDATE database_po_realisasi r
JOIN master_kontrak k ON CONVERT(k.nomor_kontrak USING utf8mb4) COLLATE utf8mb4_unicode_ci =
                        CONVERT(TRIM(r.nomor_kontrak) USING utf8mb4) COLLATE utf8mb4_unicode_ci
SET r.kontrak_id = k.id
WHERE r.kontrak_id IS NULL;

UPDATE database_po_mapping_rule r
JOIN master_kontrak k ON CONVERT(k.nomor_kontrak USING utf8mb4) COLLATE utf8mb4_unicode_ci =
                        CONVERT(TRIM(r.nomor_kontrak) USING utf8mb4) COLLATE utf8mb4_unicode_ci
SET r.kontrak_id = k.id
WHERE r.kontrak_id IS NULL;

UPDATE database_billing_tax b
JOIN master_kontrak k ON CONVERT(k.nomor_kontrak USING utf8mb4) COLLATE utf8mb4_unicode_ci =
                        CONVERT(TRIM(b.kontrak_no) USING utf8mb4) COLLATE utf8mb4_unicode_ci
SET b.kontrak_id = k.id
WHERE b.kontrak_id IS NULL;

UPDATE database_status_pembayaran p
JOIN master_kontrak k ON CONVERT(k.nomor_kontrak USING utf8mb4) COLLATE utf8mb4_unicode_ci =
                        CONVERT(TRIM(p.nomor_kontrak) USING utf8mb4) COLLATE utf8mb4_unicode_ci
SET p.kontrak_id = k.id
WHERE p.kontrak_id IS NULL;

-- Foreign key hanya ditambahkan pada tabel inti yang sudah dimigrasikan.
ALTER TABLE database_master_po
    ADD CONSTRAINT fk_master_po_kontrak
    FOREIGN KEY (kontrak_id) REFERENCES master_kontrak(id)
    ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE database_transaksi_rincian
    ADD CONSTRAINT fk_transaksi_kontrak
    FOREIGN KEY (kontrak_id) REFERENCES master_kontrak(id)
    ON UPDATE CASCADE ON DELETE SET NULL;

ALTER TABLE database_po_realisasi
    ADD CONSTRAINT fk_realisasi_kontrak
    FOREIGN KEY (kontrak_id) REFERENCES master_kontrak(id)
    ON UPDATE CASCADE ON DELETE SET NULL;

-- ================================================================
-- D. MASTER PROFORMA INVOICE NORMALIZED
--    Tabel lama tetap dipertahankan sebagai legacy/source.
-- ================================================================

CREATE TABLE IF NOT EXISTS database_master_pi (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    kontrak_id BIGINT UNSIGNED NOT NULL,
    nomor_pi VARCHAR(100) NOT NULL,
    nomor_po_lama VARCHAR(100) NULL,
    tanggal_pi_text VARCHAR(50) NULL,
    judul_kontrak TEXT NULL,
    status_pi VARCHAR(30) NOT NULL DEFAULT 'DRAFT',
    total_nilai DECIMAL(20,2) NOT NULL DEFAULT 0.00,
    keterangan TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_master_pi_kontrak_nomor (kontrak_id, nomor_pi),
    KEY idx_master_pi_nomor (nomor_pi),
    CONSTRAINT fk_master_pi_kontrak
        FOREIGN KEY (kontrak_id) REFERENCES master_kontrak(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO database_master_pi
    (kontrak_id, nomor_pi, nomor_po_lama, tanggal_pi_text, judul_kontrak)
SELECT
    k.id,
    TRIM(p.`Proforma Invoice No.`),
    NULLIF(TRIM(p.`Nomor Purchase Order`), ''),
    NULLIF(TRIM(p.`Tanggal Performa Invoice`), ''),
    NULLIF(TRIM(p.`Judul Kontrak`), '')
FROM database_proforma_invoice p
JOIN master_kontrak k
  ON CONVERT(k.nomor_kontrak USING utf8mb4) COLLATE utf8mb4_unicode_ci =
     CONVERT(TRIM(p.`Nomor Kontrak`) USING utf8mb4) COLLATE utf8mb4_unicode_ci
WHERE p.`Proforma Invoice No.` IS NOT NULL
  AND TRIM(p.`Proforma Invoice No.`) NOT IN ('', '-', '0');

ALTER TABLE database_transaksi_rincian
    ADD COLUMN IF NOT EXISTS pi_id BIGINT UNSIGNED NULL AFTER pi_no,
    ADD KEY IF NOT EXISTS idx_transaksi_pi_id (pi_id);

UPDATE database_transaksi_rincian t
JOIN database_master_pi p
  ON p.kontrak_id = t.kontrak_id
 AND CONVERT(p.nomor_pi USING utf8mb4) COLLATE utf8mb4_unicode_ci =
     CONVERT(TRIM(t.pi_no) USING utf8mb4) COLLATE utf8mb4_unicode_ci
SET t.pi_id = p.id
WHERE t.pi_id IS NULL;

ALTER TABLE database_po_realisasi
    ADD COLUMN IF NOT EXISTS pi_id BIGINT UNSIGNED NULL AFTER nomor_pi,
    ADD KEY IF NOT EXISTS idx_realisasi_pi_id (pi_id);

UPDATE database_po_realisasi r
JOIN database_master_pi p
  ON p.kontrak_id = r.kontrak_id
 AND CONVERT(p.nomor_pi USING utf8mb4) COLLATE utf8mb4_unicode_ci =
     CONVERT(TRIM(r.nomor_pi) USING utf8mb4) COLLATE utf8mb4_unicode_ci
SET r.pi_id = p.id
WHERE r.pi_id IS NULL;

ALTER TABLE database_opname
    ADD COLUMN IF NOT EXISTS pi_id BIGINT UNSIGNED NULL AFTER nomor_pi,
    ADD KEY IF NOT EXISTS idx_opname_pi_id (pi_id);

UPDATE database_opname o
JOIN database_master_pi p
  ON p.kontrak_id = o.kontrak_id
 AND CONVERT(p.nomor_pi USING utf8mb4) COLLATE utf8mb4_unicode_ci =
     CONVERT(TRIM(o.nomor_pi) USING utf8mb4) COLLATE utf8mb4_unicode_ci
SET o.pi_id = p.id
WHERE o.pi_id IS NULL;

ALTER TABLE database_transaksi_rincian
    ADD CONSTRAINT fk_transaksi_pi
    FOREIGN KEY (pi_id) REFERENCES database_master_pi(id)
    ON UPDATE CASCADE ON DELETE SET NULL;

ALTER TABLE database_po_realisasi
    ADD CONSTRAINT fk_realisasi_pi
    FOREIGN KEY (pi_id) REFERENCES database_master_pi(id)
    ON UPDATE CASCADE ON DELETE SET NULL;

-- ================================================================
-- E. INVOICE RESMI NORMALIZED
--    database_billing_tax tetap berjalan sebagai legacy compatibility.
-- ================================================================

CREATE TABLE IF NOT EXISTS database_master_invoice (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    kontrak_id BIGINT UNSIGNED NOT NULL,
    nomor_invoice VARCHAR(100) NOT NULL,
    nomor_sa_wan VARCHAR(100) NULL,
    tanggal_invoice DATE NULL,
    jatuh_tempo DATE NULL,
    nilai_dpp DECIMAL(20,2) NOT NULL DEFAULT 0.00,
    add_cost DECIMAL(20,2) NOT NULL DEFAULT 0.00,
    management_fee DECIMAL(20,2) NOT NULL DEFAULT 0.00,
    ppn_nominal DECIMAL(20,2) NOT NULL DEFAULT 0.00,
    pph_nominal DECIMAL(20,2) NOT NULL DEFAULT 0.00,
    total_netto DECIMAL(20,2) NOT NULL DEFAULT 0.00,
    status_invoice VARCHAR(30) NOT NULL DEFAULT 'TERBIT',
    keterangan TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_master_invoice_kontrak_nomor (kontrak_id, nomor_invoice),
    KEY idx_master_invoice_tanggal (tanggal_invoice),
    CONSTRAINT fk_master_invoice_kontrak
        FOREIGN KEY (kontrak_id) REFERENCES master_kontrak(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO database_master_invoice
    (kontrak_id, nomor_invoice, nomor_sa_wan, tanggal_invoice,
     jatuh_tempo, nilai_dpp, add_cost, management_fee, ppn_nominal,
     pph_nominal, total_netto, keterangan)
SELECT
    k.id,
    TRIM(b.nomor_invoice),
    NULLIF(TRIM(b.nomor_sa_wan), ''),
    CASE WHEN b.tanggal_invoice IS NULL OR b.tanggal_invoice IN ('0000-00-00', '')
         THEN NULL ELSE b.tanggal_invoice END,
    CASE WHEN b.jatuh_tempo IS NULL OR b.jatuh_tempo IN ('0000-00-00', '')
         THEN NULL ELSE b.jatuh_tempo END,
    COALESCE(b.nilai_invoice, 0),
    COALESCE(b.add_cost, 0),
    COALESCE(b.management_fee, 0),
    COALESCE(b.ppn_nominal, 0),
    COALESCE(b.pph_nominal, 0),
    COALESCE(b.total_netto, 0),
    NULLIF(TRIM(b.keterangan_invoice), '')
FROM database_billing_tax b
JOIN master_kontrak k
  ON CONVERT(k.nomor_kontrak USING utf8mb4) COLLATE utf8mb4_unicode_ci =
     CONVERT(TRIM(b.kontrak_no) USING utf8mb4) COLLATE utf8mb4_unicode_ci
WHERE b.nomor_invoice IS NOT NULL
  AND TRIM(b.nomor_invoice) NOT IN ('', '-', '0', 'Nomor Invoice Resmi');

UPDATE database_billing_tax b
JOIN database_master_invoice i
  ON i.kontrak_id = b.kontrak_id
 AND CONVERT(i.nomor_invoice USING utf8mb4) COLLATE utf8mb4_unicode_ci =
     CONVERT(TRIM(b.nomor_invoice) USING utf8mb4) COLLATE utf8mb4_unicode_ci
SET b.invoice_id = i.id
WHERE b.invoice_id IS NULL;

UPDATE database_status_pembayaran p
JOIN database_master_invoice i
  ON i.kontrak_id = p.kontrak_id
 AND CONVERT(i.nomor_invoice USING utf8mb4) COLLATE utf8mb4_unicode_ci =
     CONVERT(TRIM(p.nomor_invoice) USING utf8mb4) COLLATE utf8mb4_unicode_ci
SET p.invoice_id = i.id
WHERE p.invoice_id IS NULL;

ALTER TABLE database_billing_tax
    ADD CONSTRAINT fk_billing_invoice
    FOREIGN KEY (invoice_id) REFERENCES database_master_invoice(id)
    ON UPDATE CASCADE ON DELETE SET NULL;

ALTER TABLE database_status_pembayaran
    ADD CONSTRAINT fk_status_invoice
    FOREIGN KEY (invoice_id) REFERENCES database_master_invoice(id)
    ON UPDATE CASCADE ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS database_invoice_allocation (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    invoice_id BIGINT UNSIGNED NOT NULL,
    pi_id BIGINT UNSIGNED NULL,
    po_id BIGINT UNSIGNED NULL,
    nilai_alokasi DECIMAL(20,2) NOT NULL DEFAULT 0.00,
    keterangan TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_allocation_invoice (invoice_id),
    KEY idx_allocation_pi (pi_id),
    KEY idx_allocation_po (po_id),
    CONSTRAINT fk_allocation_invoice
        FOREIGN KEY (invoice_id) REFERENCES database_master_invoice(id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_allocation_pi
        FOREIGN KEY (pi_id) REFERENCES database_master_pi(id)
        ON UPDATE CASCADE ON DELETE SET NULL,
    CONSTRAINT fk_allocation_po
        FOREIGN KEY (po_id) REFERENCES database_master_po(id)
        ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS database_invoice_payment (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    invoice_id BIGINT UNSIGNED NOT NULL,
    nomor_faktur_pajak VARCHAR(100) NULL,
    tanggal_penyerahan DATE NULL,
    tanggal_jatuh_tempo DATE NULL,
    tanggal_pelunasan DATE NULL,
    nominal_tagihan DECIMAL(20,2) NOT NULL DEFAULT 0.00,
    nominal_dibayar DECIMAL(20,2) NOT NULL DEFAULT 0.00,
    potongan_pph DECIMAL(20,2) NOT NULL DEFAULT 0.00,
    potongan_ppn_wapu DECIMAL(20,2) NOT NULL DEFAULT 0.00,
    selisih_lainnya DECIMAL(20,2) NOT NULL DEFAULT 0.00,
    status_pembayaran VARCHAR(30) NOT NULL DEFAULT 'BELUM DIBAYAR',
    catatan TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_payment_invoice (invoice_id),
    KEY idx_payment_status (status_pembayaran),
    CONSTRAINT fk_payment_invoice
        FOREIGN KEY (invoice_id) REFERENCES database_master_invoice(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ================================================================
-- F. VIEW RINGKASAN JANGKA PANJANG
-- ================================================================

CREATE OR REPLACE VIEW vw_kontrak_summary AS
SELECT
    k.id AS kontrak_id,
    k.nomor_kontrak,
    k.judul_kontrak,
    k.plafon_kontrak,
    COALESCE(po.total_plafon_po, 0) AS total_plafon_po,
    COALESCE(r.total_realisasi, 0) AS total_realisasi,
    COALESCE(i.total_invoice, 0) AS total_invoice,
    COALESCE(pay.total_dibayar, 0) AS total_dibayar,
    k.plafon_kontrak - COALESCE(r.total_realisasi, 0) AS sisa_plafon_kontrak,
    k.plafon_kontrak - COALESCE(po.total_plafon_po, 0) AS sisa_plafon_yang_dialokasikan,
    COALESCE(i.total_invoice, 0) - COALESCE(pay.total_dibayar, 0) AS saldo_piutang
FROM master_kontrak k
LEFT JOIN (
    SELECT kontrak_id, SUM(total_plafon) AS total_plafon_po
    FROM database_master_po
    WHERE status_po NOT IN ('DELETED', 'CANCELLED')
    GROUP BY kontrak_id
) po ON po.kontrak_id = k.id
LEFT JOIN (
    SELECT kontrak_id, SUM(nilai_realisasi) AS total_realisasi
    FROM database_po_realisasi
    WHERE mapping_status = 'MAPPED'
    GROUP BY kontrak_id
) r ON r.kontrak_id = k.id
LEFT JOIN (
    SELECT kontrak_id, SUM(total_netto) AS total_invoice
    FROM database_master_invoice
    WHERE status_invoice <> 'DIBATALKAN'
    GROUP BY kontrak_id
) i ON i.kontrak_id = k.id
LEFT JOIN (
    SELECT mi.kontrak_id, SUM(p.nominal_dibayar) AS total_dibayar
    FROM database_invoice_payment p
    JOIN database_master_invoice mi ON mi.id = p.invoice_id
    GROUP BY mi.kontrak_id
) pay ON pay.kontrak_id = k.id;

CREATE OR REPLACE VIEW vw_po_summary AS
SELECT
    p.id AS po_id,
    p.kontrak_id,
    k.nomor_kontrak,
    p.nomor_po,
    p.status_po,
    p.total_plafon,
    COALESCE(r.total_realisasi, 0) AS total_realisasi,
    p.total_plafon - COALESCE(r.total_realisasi, 0) AS sisa_plafon_po,
    CASE WHEN p.total_plafon > 0
         THEN ROUND(COALESCE(r.total_realisasi, 0) / p.total_plafon * 100, 2)
         ELSE 0 END AS persentase_penyerapan
FROM database_master_po p
JOIN master_kontrak k ON k.id = p.kontrak_id
LEFT JOIN (
    SELECT po_id, SUM(nilai_realisasi) AS total_realisasi
    FROM database_po_realisasi r
    JOIN database_master_po_item pi ON pi.id = r.po_item_id
    WHERE r.mapping_status = 'MAPPED'
    GROUP BY po_id
) r ON r.po_id = p.id;

-- ================================================================
-- G. AUDIT MIGRASI
-- ================================================================

CREATE TABLE IF NOT EXISTS database_migration_log (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    migration_key VARCHAR(100) NOT NULL,
    executed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    note TEXT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_migration_key (migration_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO database_migration_log
    (migration_key, note)
VALUES
    ('001_normalisasi_kontrak_po_keuangan',
     'Menambahkan Master Kontrak, relasi kontrak/PI/invoice, tabel pembayaran, dan view ringkasan tanpa menghapus tabel legacy.');

-- ================================================================
-- H. VALIDASI PASCA MIGRASI
-- Jalankan SELECT ini setelah migrasi untuk memeriksa data yang belum
-- terhubung. Nilai yang muncul tidak dihapus; perlu ditinjau manual.
-- ================================================================

SELECT 'PO tanpa kontrak_id' AS pemeriksaan, COUNT(*) AS jumlah
FROM database_master_po WHERE kontrak_id IS NULL
UNION ALL
SELECT 'Transaksi tanpa kontrak_id', COUNT(*)
FROM database_transaksi_rincian WHERE kontrak_id IS NULL
UNION ALL
SELECT 'Realisasi tanpa kontrak_id', COUNT(*)
FROM database_po_realisasi WHERE kontrak_id IS NULL
UNION ALL
SELECT 'Billing tanpa kontrak_id', COUNT(*)
FROM database_billing_tax
WHERE kontrak_id IS NULL
  AND TRIM(COALESCE(kontrak_no, '')) NOT IN ('', '-', '0', 'Kontrak No.')
UNION ALL
SELECT 'PI transaksi tanpa pi_id', COUNT(*)
FROM database_transaksi_rincian
WHERE pi_no IS NOT NULL
  AND TRIM(COALESCE(nomor_kontrak, '')) NOT IN ('', '-', '0', 'Nomor Kontrak')
  AND TRIM(pi_no) NOT IN ('', '-', '0', 'PI No.')
  AND TRIM(COALESCE(nomor_po, '')) NOT IN ('Nomor PO')
  AND pi_id IS NULL;

