USE phieuton;

ALTER TABLE tickets
    ADD COLUMN requires_reason_recheck BOOLEAN NOT NULL DEFAULT FALSE;
