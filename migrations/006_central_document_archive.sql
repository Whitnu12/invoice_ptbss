-- Arsip terpusat dokumen customer dan dokumen pendukung.
-- Tabel bersifat additive; arsip invoice-tax yang sudah ada tidak diubah.

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS database_document_archive (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    contract_number VARCHAR(150) NOT NULL,
    pi_number VARCHAR(150) NULL,
    reference_number VARCHAR(150) NULL,
    category VARCHAR(50) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(100) NOT NULL,
    storage_path VARCHAR(600) NOT NULL,
    mime_type VARCHAR(150) NULL,
    file_size BIGINT UNSIGNED NOT NULL DEFAULT 0,
    note TEXT NULL,
    uploaded_by VARCHAR(150) NULL,
    uploaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    deleted_by VARCHAR(150) NULL,
    deleted_at DATETIME NULL,
    legacy_key CHAR(64) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_document_archive_stored_filename (stored_filename),
    UNIQUE KEY uq_document_archive_legacy_key (legacy_key),
    KEY idx_document_archive_contract (contract_number),
    KEY idx_document_archive_category (category),
    KEY idx_document_archive_status_uploaded (status, uploaded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS database_document_archive_audit (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    archive_id BIGINT UNSIGNED NOT NULL,
    actor_username VARCHAR(150) NULL,
    actor_role VARCHAR(80) NULL,
    action VARCHAR(30) NOT NULL,
    detail JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_document_archive_audit_archive (archive_id, created_at),
    KEY idx_document_archive_audit_actor (actor_username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS database_document_archive_migration (
    migration_key VARCHAR(100) NOT NULL,
    completed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (migration_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
