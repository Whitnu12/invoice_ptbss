-- BSS INVOICE - STEP 1
-- Normalisasi dan audit data Invoice & Tax Management.
-- Target: MariaDB 10.11 / database terbaru 13 Oktober 2026.
--
-- Migration ini tidak menghapus tabel legacy. Semua backfill dibuat idempotent
-- berdasarkan invoice_id atau pasangan kontrak + nomor invoice.

SET NAMES utf8mb4;
SET time_zone = '+00:00';
START TRANSACTION;

-- ================================================================
-- A. Tambahkan atribut invoice yang masih berada di tabel legacy.
-- ================================================================

ALTER TABLE database_master_invoice
    ADD COLUMN IF NOT EXISTS pi_no VARCHAR(100) NULL AFTER nomor_sa_wan,
    ADD COLUMN IF NOT EXISTS nomor_po VARCHAR(100) NULL AFTER pi_no,
    ADD COLUMN IF NOT EXISTS customer VARCHAR(255) NULL AFTER nomor_po,
    ADD COLUMN IF NOT EXISTS alamat_customer TEXT NULL AFTER customer,
    ADD COLUMN IF NOT EXISTS npwp_customer VARCHAR(50) NULL AFTER alamat_customer,
    ADD COLUMN IF NOT EXISTS informasi_bank TEXT NULL AFTER npwp_customer,
    ADD COLUMN IF NOT EXISTS nilai_gross DECIMAL(20,2) NOT NULL DEFAULT 0.00 AFTER nilai_dpp,
    ADD COLUMN IF NOT EXISTS diskon_nominal DECIMAL(20,2) NOT NULL DEFAULT 0.00 AFTER nilai_gross,
    ADD COLUMN IF NOT EXISTS gunakan_professional_sum TINYINT(1) NOT NULL DEFAULT 0 AFTER diskon_nominal,
    ADD COLUMN IF NOT EXISTS gunakan_estimasi_sum TINYINT(1) NOT NULL DEFAULT 0 AFTER gunakan_professional_sum,
    ADD COLUMN IF NOT EXISTS kena_ppn TINYINT(1) NOT NULL DEFAULT 1 AFTER total_netto,
    ADD COLUMN IF NOT EXISTS kena_pph TINYINT(1) NOT NULL DEFAULT 0 AFTER kena_ppn,
    ADD COLUMN IF NOT EXISTS tarif_pph DECIMAL(5,2) NOT NULL DEFAULT 0.00 AFTER kena_pph;

UPDATE database_master_invoice i
JOIN database_billing_tax b ON b.invoice_id = i.id
SET
    i.pi_no = NULLIF(TRIM(b.pi_no), ''),
    i.nomor_po = NULLIF(TRIM(b.nomor_po), ''),
    i.customer = NULLIF(TRIM(b.customer), ''),
    i.alamat_customer = NULLIF(TRIM(b.alamat_customer), ''),
    i.npwp_customer = NULLIF(TRIM(b.npwp_customer), ''),
    i.informasi_bank = NULLIF(TRIM(b.informasi_bank), ''),
    i.nilai_gross = COALESCE(b.nilai_invoice, 0),
    i.diskon_nominal = COALESCE(b.nilai_invoice, 0) - COALESCE(b.nilai_invoice, 0),
    i.gunakan_professional_sum = CASE
        WHEN LOWER(TRIM(COALESCE(b.gunakan_professional_sum, '0'))) IN ('1', 'true', 'yes') THEN 1
        ELSE 0
    END,
    -- Versi dump 13 Oktober belum menyimpan flag Estimated Sum di
    -- database_billing_tax; nilai default 0 dipakai sampai sumber legacy
    -- tersebut memiliki kolom eksplisit.
    i.gunakan_estimasi_sum = 0,
    i.kena_ppn = CASE
        WHEN LOWER(TRIM(COALESCE(b.kena_ppn, '1'))) IN ('0', 'false', 'no') THEN 0
        ELSE 1
    END,
    i.kena_pph = CASE
        WHEN LOWER(TRIM(COALESCE(b.kena_pph, '0'))) IN ('1', 'true', 'yes') THEN 1
        ELSE 0
    END,
    i.tarif_pph = COALESCE(b.tarif_pph, 0);

-- ================================================================
-- B. Referensi faktur pajak normalized.
-- ================================================================

CREATE TABLE IF NOT EXISTS database_tax_invoice_reference (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    invoice_id BIGINT UNSIGNED NULL,
    kontrak_id BIGINT UNSIGNED NULL,
    nomor_kontrak VARCHAR(100) NULL,
    nomor_invoice VARCHAR(100) NOT NULL,
    nsfp VARCHAR(100) NULL,
    tanggal_fp DATE NULL,
    nilai_dpp DECIMAL(20,2) NOT NULL DEFAULT 0.00,
    customer_name VARCHAR(255) NULL,
    customer_address TEXT NULL,
    customer_npwp VARCHAR(50) NULL,
    keterangan TEXT NULL,
    sumber_data VARCHAR(50) NOT NULL DEFAULT 'LEGACY',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_tax_reference_invoice (invoice_id),
    KEY idx_tax_reference_nomor (nomor_invoice),
    KEY idx_tax_reference_nsfp (nsfp),
    CONSTRAINT fk_tax_reference_invoice
        FOREIGN KEY (invoice_id) REFERENCES database_master_invoice(id)
        ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO database_tax_invoice_reference
    (invoice_id, kontrak_id, nomor_kontrak, nomor_invoice, nsfp,
     tanggal_fp, nilai_dpp, customer_name, customer_address,
     customer_npwp, keterangan, sumber_data)
SELECT
    i.id,
    i.kontrak_id,
    NULLIF(TRIM(f.nomor_kontrak), ''),
    TRIM(f.nomor_invoice),
    NULLIF(TRIM(f.nsfp), ''),
    CASE
        WHEN TRIM(COALESCE(f.tanggal_fp, '')) REGEXP '^[0-9]{2}/[0-9]{2}/[0-9]{4}$'
        THEN STR_TO_DATE(TRIM(f.tanggal_fp), '%d/%m/%Y')
        ELSE NULL
    END,
    CASE
        WHEN TRIM(COALESCE(f.nilai_dpp, '')) REGEXP '^[0-9]+([.][0-9]+)?$'
        THEN CAST(TRIM(f.nilai_dpp) AS DECIMAL(20,2))
        ELSE 0.00
    END,
    NULLIF(TRIM(f.customer_name), ''),
    NULLIF(TRIM(f.customer_address), ''),
    NULLIF(TRIM(f.customer_npwp), ''),
    NULLIF(TRIM(f.keterangan), ''),
    'LEGACY'
FROM database_faktur_pajak_online f
LEFT JOIN database_master_invoice i
    ON CONVERT(i.nomor_invoice USING utf8mb4) COLLATE utf8mb4_unicode_ci =
       CONVERT(TRIM(f.nomor_invoice) USING utf8mb4) COLLATE utf8mb4_unicode_ci
   AND (f.nomor_kontrak IS NULL OR i.kontrak_id = (
       SELECT k.id FROM master_kontrak k
       WHERE CONVERT(k.nomor_kontrak USING utf8mb4) COLLATE utf8mb4_unicode_ci =
             CONVERT(TRIM(f.nomor_kontrak) USING utf8mb4) COLLATE utf8mb4_unicode_ci
       LIMIT 1
   ))
WHERE TRIM(COALESCE(f.nomor_invoice, '')) NOT IN ('', 'Nomor Invoice')
  AND NOT EXISTS (
      SELECT 1
      FROM database_tax_invoice_reference x
      WHERE x.invoice_id <=> i.id
        AND CONVERT(x.nomor_invoice USING utf8mb4) COLLATE utf8mb4_unicode_ci =
            CONVERT(TRIM(f.nomor_invoice) USING utf8mb4) COLLATE utf8mb4_unicode_ci
  );

-- ================================================================
-- C. Backfill allocation invoice -> PI/PO.
-- ================================================================

INSERT INTO database_invoice_allocation
    (invoice_id, pi_id, po_id, nilai_alokasi, keterangan)
SELECT
    i.id,
    pi.id,
    po.id,
    i.total_netto,
    'Backfill Step 1 dari database_billing_tax berdasarkan PI/PO.'
FROM database_master_invoice i
LEFT JOIN database_master_pi pi
    ON pi.kontrak_id = i.kontrak_id
   AND CONVERT(pi.nomor_pi USING utf8mb4) COLLATE utf8mb4_unicode_ci =
       CONVERT(i.pi_no USING utf8mb4) COLLATE utf8mb4_unicode_ci
LEFT JOIN database_master_po po
    ON po.kontrak_id = i.kontrak_id
   AND CONVERT(po.nomor_po USING utf8mb4) COLLATE utf8mb4_unicode_ci =
       CONVERT(i.nomor_po USING utf8mb4) COLLATE utf8mb4_unicode_ci
WHERE (pi.id IS NOT NULL OR po.id IS NOT NULL)
  AND NOT EXISTS (
      SELECT 1 FROM database_invoice_allocation a
      WHERE a.invoice_id = i.id
  );

-- ================================================================
-- D. Backfill status pembayaran normalized.
-- ================================================================

ALTER TABLE database_invoice_payment
    ADD COLUMN IF NOT EXISTS durasi_riil_hari INT NULL AFTER status_pembayaran;

INSERT INTO database_invoice_payment
    (invoice_id, nomor_faktur_pajak, tanggal_penyerahan,
     tanggal_jatuh_tempo, tanggal_pelunasan, nominal_tagihan,
     nominal_dibayar, potongan_pph, potongan_ppn_wapu,
     selisih_lainnya, status_pembayaran, durasi_riil_hari, catatan)
SELECT
    i.id,
    CASE
        WHEN LOWER(TRIM(COALESCE(s.nomor_faktur_pajak, ''))) IN ('', '-', 'null') THEN NULL
        ELSE TRIM(s.nomor_faktur_pajak)
    END,
    CASE
        WHEN TRIM(COALESCE(s.tanggal_penyerahan, '')) REGEXP '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
        THEN STR_TO_DATE(TRIM(s.tanggal_penyerahan), '%Y-%m-%d')
        ELSE NULL
    END,
    CASE
        WHEN TRIM(COALESCE(s.tanggal_jatuh_tempo, '')) REGEXP '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
        THEN STR_TO_DATE(TRIM(s.tanggal_jatuh_tempo), '%Y-%m-%d')
        ELSE i.jatuh_tempo
    END,
    CASE
        WHEN TRIM(COALESCE(s.tanggal_pelunasan, '')) REGEXP '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
        THEN STR_TO_DATE(TRIM(s.tanggal_pelunasan), '%Y-%m-%d')
        ELSE NULL
    END,
    i.total_netto,
    CASE
        WHEN LOWER(TRIM(COALESCE(s.status_pembayaran, ''))) IN ('lunas', 'dibayar', 'paid')
        THEN i.total_netto
        ELSE 0.00
    END,
    0.00,
    0.00,
    0.00,
    CASE
        WHEN LOWER(TRIM(COALESCE(s.status_pembayaran, ''))) IN ('lunas', 'dibayar', 'paid') THEN 'DIBAYAR'
        WHEN LOWER(TRIM(COALESCE(s.status_pembayaran, ''))) IN ('proses', 'diproses', 'process') THEN 'PROSES'
        ELSE 'BELUM DIBAYAR'
    END,
    CASE
        WHEN TRIM(COALESCE(s.durasi_riil_hari, '')) REGEXP '^[0-9]+$'
        THEN CAST(TRIM(s.durasi_riil_hari) AS UNSIGNED)
        ELSE NULL
    END,
    NULLIF(TRIM(s.catatan), '')
FROM database_status_pembayaran s
JOIN database_master_invoice i
    ON (
        s.invoice_id IS NOT NULL AND s.invoice_id = i.id
    ) OR (
        s.invoice_id IS NULL
        AND CONVERT(TRIM(s.nomor_invoice) USING utf8mb4) COLLATE utf8mb4_unicode_ci =
            CONVERT(i.nomor_invoice USING utf8mb4) COLLATE utf8mb4_unicode_ci
        AND s.kontrak_id = i.kontrak_id
    )
WHERE TRIM(COALESCE(s.nomor_kontrak, '')) NOT IN ('', 'Nomor Kontrak')
  AND TRIM(COALESCE(s.nomor_invoice, '')) NOT IN ('', 'Nomor Invoice')
  AND NOT EXISTS (
      SELECT 1 FROM database_invoice_payment p
      WHERE p.invoice_id = i.id
  );

-- ================================================================
-- E. Audit temuan yang tidak boleh hilang saat cutover.
-- ================================================================

CREATE TABLE IF NOT EXISTS database_invoice_tax_audit (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    migration_key VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    source_key VARCHAR(255) NOT NULL,
    issue_code VARCHAR(100) NOT NULL,
    detail TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_invoice_tax_audit (migration_key, entity_type, source_key, issue_code),
    KEY idx_invoice_tax_audit_issue (issue_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO database_invoice_tax_audit
    (migration_key, entity_type, source_key, issue_code, detail)
SELECT
    '002_invoice_tax_step1_data_quality',
    'CONTRACT',
    CAST(k.id AS CHAR),
    'DUMMY_CONTRACT',
    CONCAT('Nomor kontrak dummy: ', k.nomor_kontrak)
FROM master_kontrak k
WHERE k.nomor_kontrak IN ('', 'Nomor Kontrak');

INSERT IGNORE INTO database_invoice_tax_audit
    (migration_key, entity_type, source_key, issue_code, detail)
SELECT
    '002_invoice_tax_step1_data_quality',
    'PAYMENT',
    CONCAT(COALESCE(s.nomor_kontrak, ''), '|', COALESCE(s.nomor_invoice, '')),
    'HEADER_OR_PLACEHOLDER_ROW',
    'Baris header/placeholder tidak dimigrasikan ke payment normalized.'
FROM database_status_pembayaran s
WHERE TRIM(COALESCE(s.nomor_kontrak, '')) IN ('', 'Nomor Kontrak')
   OR TRIM(COALESCE(s.nomor_invoice, '')) IN ('', 'Nomor Invoice');

INSERT IGNORE INTO database_invoice_tax_audit
    (migration_key, entity_type, source_key, issue_code, detail)
SELECT
    '002_invoice_tax_step1_data_quality',
    'INVOICE',
    i.nomor_invoice,
    'MISSING_PI_OR_PO_ALLOCATION',
    CONCAT('PI=', COALESCE(i.pi_no, '-'), '; PO=', COALESCE(i.nomor_po, '-'))
FROM database_master_invoice i
LEFT JOIN database_invoice_allocation a ON a.invoice_id = i.id
WHERE a.id IS NULL;

INSERT IGNORE INTO database_invoice_tax_audit
    (migration_key, entity_type, source_key, issue_code, detail)
SELECT
    '002_invoice_tax_step1_data_quality',
    'PAYMENT',
    COALESCE(s.nomor_invoice, CONCAT('row-', s.nomor_kontrak)),
    'PAYMENT_WITHOUT_INVOICE',
    'Baris pembayaran legacy tidak menemukan invoice normalized.'
FROM database_status_pembayaran s
LEFT JOIN database_master_invoice i
    ON (s.invoice_id IS NOT NULL AND i.id = s.invoice_id)
    OR (s.invoice_id IS NULL
        AND i.kontrak_id = s.kontrak_id
        AND CONVERT(i.nomor_invoice USING utf8mb4) COLLATE utf8mb4_unicode_ci =
            CONVERT(TRIM(s.nomor_invoice) USING utf8mb4) COLLATE utf8mb4_unicode_ci)
WHERE TRIM(COALESCE(s.nomor_kontrak, '')) NOT IN ('', 'Nomor Kontrak')
  AND TRIM(COALESCE(s.nomor_invoice, '')) NOT IN ('', 'Nomor Invoice')
  AND i.id IS NULL;

INSERT IGNORE INTO database_invoice_tax_audit
    (migration_key, entity_type, source_key, issue_code, detail)
SELECT
    '002_invoice_tax_step1_data_quality',
    'TAX_REFERENCE',
    COALESCE(f.nomor_invoice, CONCAT('row-', f.nomor_kontrak)),
    'TAX_REFERENCE_WITHOUT_INVOICE',
    'Referensi faktur pajak tidak menemukan invoice normalized.'
FROM database_faktur_pajak_online f
LEFT JOIN database_master_invoice i
    ON CONVERT(i.nomor_invoice USING utf8mb4) COLLATE utf8mb4_unicode_ci =
       CONVERT(TRIM(f.nomor_invoice) USING utf8mb4) COLLATE utf8mb4_unicode_ci
WHERE TRIM(COALESCE(f.nomor_invoice, '')) NOT IN ('', 'Nomor Invoice')
  AND i.id IS NULL;

INSERT IGNORE INTO database_invoice_tax_audit
    (migration_key, entity_type, source_key, issue_code, detail)
SELECT
    '002_invoice_tax_step1_data_quality',
    'TAX_REFERENCE',
    COALESCE(f.nomor_invoice, CONCAT('row-', f.nomor_kontrak)),
    'SCIENTIFIC_NOTATION_NSFP',
    CONCAT('Nomor faktur pajak perlu verifikasi sumber: ', f.nsfp)
FROM database_faktur_pajak_online f
WHERE LOWER(COALESCE(f.nsfp, '')) LIKE '%e+%';

INSERT IGNORE INTO database_migration_log
    (migration_key, note)
VALUES
    ('002_invoice_tax_step1_data_quality',
     'Melengkapi atribut invoice, membuat referensi faktur pajak normalized, backfill allocation/payment, dan mencatat audit data yang tidak dapat dipetakan.');

COMMIT;

-- Query verifikasi pasca-eksekusi:
-- SELECT issue_code, COUNT(*) FROM database_invoice_tax_audit
-- WHERE migration_key = '002_invoice_tax_step1_data_quality'
-- GROUP BY issue_code ORDER BY issue_code;
-- SELECT COUNT(*) AS invoice_count FROM database_master_invoice;
-- SELECT COUNT(*) AS allocation_count FROM database_invoice_allocation;
-- SELECT COUNT(*) AS payment_count FROM database_invoice_payment;
-- SELECT COUNT(*) AS tax_reference_count FROM database_tax_invoice_reference;
