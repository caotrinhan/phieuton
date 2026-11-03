USE phieuton;

ALTER TABLE tickets
	ADD COLUMN progress VARCHAR(150) NOT NULL DEFAULT '' AFTER equipment_type;
