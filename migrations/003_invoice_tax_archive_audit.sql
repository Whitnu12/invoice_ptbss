-- BSS INVOICE - STEP 6
-- Arsip dokumen keuangan dan audit trail.

SET NAMES utf8mb4;
START TRANSACTION;

CREATE TABLE IF NOT EXISTS database_invoice_document_archive (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    invoice_id BIGINT UNSIGNED NOT NULL,
    document_type VARCHAR(60) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL,
    storage_path VARCHAR(500) NOT NULL,
    mime_type VARCHAR(150) NULL,
    file_size BIGINT UNSIGNED NOT NULL DEFAULT 0,
    note TEXT NULL,
    uploaded_by VARCHAR(150) NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    uploaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_archive_stored_filename (stored_filename),
    KEY idx_archive_invoice (invoice_id),
    KEY idx_archive_type (document_type),
    KEY idx_archive_status (status),
    CONSTRAINT fk_archive_invoice
        FOREIGN KEY (invoice_id) REFERENCES database_master_invoice(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS database_invoice_tax_audit_log (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    actor_username VARCHAR(150) NULL,
    actor_role VARCHAR(80) NULL,
    action VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id BIGINT UNSIGNED NULL,
    detail JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_audit_entity (entity_type, entity_id),
    KEY idx_audit_actor (actor_username),
    KEY idx_audit_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO database_migration_log (migration_key, note)
VALUES (
    '003_invoice_tax_archive_audit',
    'Menambahkan metadata arsip dokumen keuangan dan audit trail operasi Invoice & Tax.'
);

COMMIT;
