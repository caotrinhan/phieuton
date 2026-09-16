CREATE DATABASE IF NOT EXISTS phieuton CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'app_user'@'localhost' IDENTIFIED BY 'change-this-password';
GRANT ALL PRIVILEGES ON phieuton.* TO 'app_user'@'localhost';
FLUSH PRIVILEGES;

USE phieuton;

CREATE TABLE IF NOT EXISTS users (
	id INT PRIMARY KEY AUTO_INCREMENT,
	email VARCHAR(190) NOT NULL UNIQUE,
	full_name VARCHAR(150) NOT NULL,
	unit VARCHAR(150) NOT NULL,
	phone VARCHAR(30),
	password_hash VARCHAR(255) NOT NULL,
	is_admin BOOLEAN NOT NULL DEFAULT FALSE,
	is_active_user BOOLEAN NOT NULL DEFAULT TRUE,
	created_at DATETIME NOT NULL
);

CREATE TABLE IF NOT EXISTS upload_batches (
	id INT PRIMARY KEY AUTO_INCREMENT,
	uploaded_at DATETIME NOT NULL,
	uploaded_by_id INT NOT NULL,
	ca_mau_filename VARCHAR(255) NOT NULL,
	bac_lieu_filename VARCHAR(255) NOT NULL,
	total_tickets INT NOT NULL DEFAULT 0,
	over_48h_tickets INT NOT NULL DEFAULT 0,
	new_tickets INT NOT NULL DEFAULT 0,
	status_changed_tickets INT NOT NULL DEFAULT 0,
	existing_tickets INT NOT NULL DEFAULT 0,
	CONSTRAINT fk_batch_user FOREIGN KEY (uploaded_by_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS tickets (
	id INT PRIMARY KEY AUTO_INCREMENT,
	batch_id INT NOT NULL,
	latest_batch_id INT,
	province VARCHAR(30) NOT NULL,
	unit VARCHAR(150) NOT NULL,
	contract_type VARCHAR(100),
	status VARCHAR(100) NOT NULL,
	equipment_type VARCHAR(100),
	subscriber_code VARCHAR(100) NOT NULL,
	subscriber_name VARCHAR(255),
	address VARCHAR(500),
	phone VARCHAR(30),
	request_at DATETIME NOT NULL,
	age_hours DECIMAL(10,1) NOT NULL,
	reason TEXT,
	reason_updated_by_id INT,
	reason_updated_at DATETIME,
	last_seen_at DATETIME NOT NULL,
	status_changed_at DATETIME NOT NULL,
	CONSTRAINT fk_ticket_batch FOREIGN KEY (batch_id) REFERENCES upload_batches(id),
	CONSTRAINT fk_ticket_latest_batch FOREIGN KEY (latest_batch_id) REFERENCES upload_batches(id),
	CONSTRAINT fk_ticket_reason_user FOREIGN KEY (reason_updated_by_id) REFERENCES users(id),
	INDEX ix_ticket_code (subscriber_code),
	INDEX ix_ticket_status (status),
	INDEX ix_ticket_latest_batch (latest_batch_id)
);

CREATE TABLE IF NOT EXISTS reason_audits (
	id INT PRIMARY KEY AUTO_INCREMENT,
	ticket_id INT NOT NULL,
	old_reason TEXT,
	new_reason TEXT,
	changed_by_id INT NOT NULL,
	changed_at DATETIME NOT NULL,
	CONSTRAINT fk_audit_ticket FOREIGN KEY (ticket_id) REFERENCES tickets(id),
	CONSTRAINT fk_audit_user FOREIGN KEY (changed_by_id) REFERENCES users(id)
);

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
