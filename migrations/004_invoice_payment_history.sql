-- Jalankan sekali sebelum mengaktifkan API riwayat pembayaran.
-- Setiap baris mencatat satu penerimaan/potongan aktual; tabel ringkasan
-- database_invoice_payment tetap dipakai untuk saldo dan aging.
CREATE TABLE IF NOT EXISTS database_invoice_payment_event (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    invoice_id BIGINT UNSIGNED NOT NULL,
    tanggal_pembayaran DATE NOT NULL,
    nominal_diterima DECIMAL(20,2) NOT NULL DEFAULT 0.00,
    potongan_pph DECIMAL(20,2) NOT NULL DEFAULT 0.00,
    potongan_ppn_wapu DECIMAL(20,2) NOT NULL DEFAULT 0.00,
    catatan VARCHAR(500) NULL,
    created_by VARCHAR(150) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_payment_event_invoice_date (invoice_id, tanggal_pembayaran, id),
    CONSTRAINT fk_payment_event_invoice
        FOREIGN KEY (invoice_id) REFERENCES database_master_invoice(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
