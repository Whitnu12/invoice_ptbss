-- Jalankan sekali setelah 004_invoice_payment_history.sql.
-- Pembayaran yang dihapus tetap tersimpan untuk audit, tetapi tidak masuk saldo.
ALTER TABLE database_invoice_payment_event
    ADD COLUMN deleted_at DATETIME NULL,
    ADD COLUMN deleted_by VARCHAR(150) NULL,
    ADD COLUMN deleted_role VARCHAR(80) NULL,
    ADD KEY idx_payment_event_active (invoice_id, deleted_at, tanggal_pembayaran);
