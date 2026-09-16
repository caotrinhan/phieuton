from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db
from .time_utils import local_now


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(190), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(150), nullable=False)
    unit = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(30))
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_active_user = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=local_now, nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class UploadBatch(db.Model):
    __tablename__ = "upload_batches"

    id = db.Column(db.Integer, primary_key=True)
    uploaded_at = db.Column(db.DateTime, default=local_now, nullable=False, index=True)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    ca_mau_filename = db.Column(db.String(255), nullable=False)
    bac_lieu_filename = db.Column(db.String(255), nullable=False)
    total_tickets = db.Column(db.Integer, default=0, nullable=False)
    over_48h_tickets = db.Column(db.Integer, default=0, nullable=False)
    new_tickets = db.Column(db.Integer, default=0, nullable=False)
    status_changed_tickets = db.Column(db.Integer, default=0, nullable=False)
    existing_tickets = db.Column(db.Integer, default=0, nullable=False)

    uploaded_by = db.relationship("User", backref="upload_batches")
    tickets = db.relationship(
        "Ticket",
        back_populates="batch",
        foreign_keys="Ticket.batch_id",
        cascade="all, delete-orphan",
    )


class Ticket(db.Model):
    __tablename__ = "tickets"

    STATUS_WAITING = "ĐANG CHỜ XÁC MINH"
    STATUS_NOT_LATEST = "KHÔNG CÓ TRONG DANH SÁCH MỚI NHẤT"

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("upload_batches.id"), nullable=False, index=True)
    latest_batch_id = db.Column(db.Integer, db.ForeignKey("upload_batches.id"), index=True)
    province = db.Column(db.String(30), nullable=False)
    unit = db.Column(db.String(150), nullable=False, index=True)
    contract_type = db.Column(db.String(100))
    status = db.Column(db.String(100), nullable=False, default=STATUS_WAITING, index=True)
    equipment_type = db.Column(db.String(100))
    subscriber_code = db.Column(db.String(100), nullable=False, index=True)
    subscriber_name = db.Column(db.String(255))
    address = db.Column(db.String(500))
    phone = db.Column(db.String(30))
    request_at = db.Column(db.DateTime, nullable=False)
    age_hours = db.Column(db.Numeric(10, 1), nullable=False, index=True)
    reason = db.Column(db.Text)
    reason_updated_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    reason_updated_at = db.Column(db.DateTime)
    last_seen_at = db.Column(db.DateTime, nullable=False, default=local_now, index=True)
    status_changed_at = db.Column(db.DateTime, default=local_now, nullable=False)

    batch = db.relationship("UploadBatch", back_populates="tickets", foreign_keys=[batch_id])
    latest_batch = db.relationship("UploadBatch", foreign_keys=[latest_batch_id])
    reason_updated_by = db.relationship("User", foreign_keys=[reason_updated_by_id])
    images = db.relationship("TicketImage", back_populates="ticket", cascade="all, delete-orphan")


class TicketImage(db.Model):
    __tablename__ = "ticket_images"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False, index=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False, unique=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    ticket = db.relationship("Ticket", back_populates="images")
    uploaded_by = db.relationship("User")


class ReasonAudit(db.Model):
    __tablename__ = "reason_audits"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False, index=True)
    old_reason = db.Column(db.Text)
    new_reason = db.Column(db.Text)
    changed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    changed_at = db.Column(db.DateTime, default=local_now, nullable=False)

    ticket = db.relationship("Ticket", backref="reason_audits")
    changed_by = db.relationship("User")
