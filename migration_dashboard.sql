USE phieuton;

ALTER TABLE upload_batches ADD COLUMN new_tickets INT NOT NULL DEFAULT 0;
ALTER TABLE upload_batches ADD COLUMN status_changed_tickets INT NOT NULL DEFAULT 0;
ALTER TABLE upload_batches ADD COLUMN existing_tickets INT NOT NULL DEFAULT 0;

ALTER TABLE tickets ADD COLUMN address VARCHAR(500) NULL;
ALTER TABLE tickets ADD COLUMN phone VARCHAR(30) NULL;

CREATE TABLE IF NOT EXISTS ticket_images (
    id INT PRIMARY KEY AUTO_INCREMENT,
    ticket_id INT NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    stored_filename VARCHAR(255) NOT NULL UNIQUE,
    uploaded_at DATETIME NOT NULL,
    uploaded_by_id INT NOT NULL,
    CONSTRAINT fk_image_ticket FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
    CONSTRAINT fk_image_user FOREIGN KEY (uploaded_by_id) REFERENCES users(id),
    INDEX ix_image_ticket (ticket_id)
);

-- One-time conversion for timestamps written by the previous UTC-based code.
UPDATE upload_batches SET uploaded_at = DATE_ADD(uploaded_at, INTERVAL 7 HOUR);
UPDATE tickets SET last_seen_at = DATE_ADD(last_seen_at, INTERVAL 7 HOUR), status_changed_at = DATE_ADD(status_changed_at, INTERVAL 7 HOUR), reason_updated_at = IFNULL(DATE_ADD(reason_updated_at, INTERVAL 7 HOUR), NULL);
UPDATE reason_audits SET changed_at = DATE_ADD(changed_at, INTERVAL 7 HOUR);