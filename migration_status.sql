USE phieuton;

ALTER TABLE tickets ADD COLUMN latest_batch_id INT NULL;
ALTER TABLE tickets ADD COLUMN last_seen_at DATETIME NULL;
ALTER TABLE tickets ADD COLUMN status_changed_at DATETIME NULL;
UPDATE tickets SET status = 'ĐANG CHỜ XÁC MINH' WHERE status IS NULL OR status = '';
UPDATE tickets SET last_seen_at = CURRENT_TIMESTAMP WHERE last_seen_at IS NULL;
UPDATE tickets SET status_changed_at = CURRENT_TIMESTAMP WHERE status_changed_at IS NULL;
ALTER TABLE tickets MODIFY status VARCHAR(100) NOT NULL;
ALTER TABLE tickets MODIFY last_seen_at DATETIME NOT NULL;
ALTER TABLE tickets MODIFY status_changed_at DATETIME NOT NULL;
ALTER TABLE tickets ADD INDEX ix_ticket_status (status);
ALTER TABLE tickets ADD INDEX ix_ticket_latest_batch (latest_batch_id);
ALTER TABLE tickets ADD CONSTRAINT fk_ticket_latest_batch FOREIGN KEY (latest_batch_id) REFERENCES upload_batches(id);