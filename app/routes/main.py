from datetime import datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pandas as pd
from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, send_from_directory, url_for
from flask_login import current_user, login_required
from ..extensions import db
from ..models import ReasonAudit, Ticket, TicketImage, UploadBatch, User, LoginLog, TrungTamMapping
from ..services.import_service import load_filtered_tickets
from ..time_utils import local_now


main_bp = Blueprint("main", __name__)


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]


def _now() -> datetime:
    return local_now()


def _image_allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {"jpg", "jpeg", "png", "webp"}


def _get_allowed_units() -> list:
    """Hỗ trợ lấy danh sách các tổ kỹ thuật thuộc quyền quản lý của user hiện tại"""
    if current_user.is_admin:
        return []
    
    user_unit = (current_user.unit or "").strip()
    
    mappings = TrungTamMapping.query.filter(
        db.func.lower(db.func.trim(TrungTamMapping.trung_tam_quan_ly)) == user_unit.lower()
    ).all()
    
    allowed = [m.to_ky_thuat for m in mappings]
    
    if not allowed:
        allowed = [current_user.unit]
        
    return allowed


@main_bp.get("/")
def dashboard():
    batch = UploadBatch.query.order_by(UploadBatch.uploaded_at.desc()).first()
    
    ticket_query = Ticket.query.filter_by(status=Ticket.STATUS_WAITING)
    tickets = (
        ticket_query.order_by(Ticket.unit, Ticket.age_hours.desc())
        .all()
        if batch
        else []
    )
    
    units = {}
    for ticket in tickets:
        item = units.setdefault(ticket.unit, {"total": 0, "fiber": 0, "mytv": 0, "mesh": 0, "camera": 0, "reported": 0})
        item["total"] += 1
        equipment = (ticket.equipment_type or "").lower()
        if equipment == "fiber":
            item["fiber"] += 1
        elif equipment == "mytv":
            item["mytv"] += 1
        elif "mesh" in equipment:
            item["mesh"] += 1
        elif "camera" in equipment:
            item["camera"] += 1
        item["reported"] += bool(ticket.reason and ticket.reason.strip())
        
    summary_rows = [{"stt": index, "unit": unit, **item} for index, (unit, item) in enumerate(units.items(), 1)]
    summary_total = {
        "total": sum(row["total"] for row in summary_rows),
        "fiber": sum(row["fiber"] for row in summary_rows),
        "mytv": sum(row["mytv"] for row in summary_rows),
        "mesh": sum(row["mesh"] for row in summary_rows),
        "camera": sum(row["camera"] for row in summary_rows),
        "reported": sum(row["reported"] for row in summary_rows),
    }
    
    allowed_units = _get_allowed_units() if current_user.is_authenticated else []

    return render_template(
        "dashboard.html", 
        batch=batch, 
        tickets=tickets, 
        units=units, 
        summary_rows=summary_rows, 
        summary_total=summary_total,
        allowed_units=allowed_units
    )


@main_bp.post("/change-password")
@login_required
def change_password():
    """Xử lý đổi mật khẩu ngay từ giao diện Modal trên Dashboard"""
    old_password = request.form.get("old_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not current_user.check_password(old_password):
        flash("Mật khẩu hiện tại không chính xác.", "error")
        return redirect(url_for("main.dashboard"))

    if new_password != confirm_password:
        flash("Mật khẩu mới và xác nhận mật khẩu không khớp.", "error")
        return redirect(url_for("main.dashboard"))

    if len(new_password) < 6:
        flash("Mật khẩu mới phải có ít nhất 6 ký tự.", "error")
        return redirect(url_for("main.dashboard"))

    current_user.set_password(new_password)
    db.session.commit()
    
    flash("Đổi mật khẩu thành công!", "success")
    return redirect(url_for("main.dashboard"))


@main_bp.get("/tickets/<int:ticket_id>")
@login_required
def ticket_detail(ticket_id: int):
    ticket = db.get_or_404(Ticket, ticket_id)
    
    if not current_user.is_admin:
        allowed_units = _get_allowed_units()
        if ticket.unit not in allowed_units:
            flash(f"Đơn vị của bạn không quản lý tổ kỹ thuật này ({ticket.unit}). Bạn không thể xem chi tiết phiếu này.", "error")
            return redirect(url_for("main.dashboard"))
            
    return render_template("ticket_detail.html", ticket=ticket)


@main_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if not current_user.is_admin:
        flash("Bạn không có quyền thực hiện chức năng upload file.", "error")
        return redirect(url_for("main.dashboard"))
    if request.method == "POST":
        ca_mau_file = request.files.get("ca_mau")
        bac_lieu_file = request.files.get("bac_lieu")
        if not ca_mau_file or not bac_lieu_file or not ca_mau_file.filename or not bac_lieu_file.filename:
            flash("Vui lòng chọn đủ hai file Excel.", "error")
            return redirect(url_for("main.upload"))
        if not _allowed(ca_mau_file.filename) or not _allowed(bac_lieu_file.filename):
            flash("Chỉ chấp nhận file .xlsx hoặc .xls.", "error")
            return redirect(url_for("main.upload"))

        upload_dir: Path = current_app.config["UPLOAD_DIR"]
        ca_path = upload_dir / f"{uuid4().hex}_{ca_mau_file.filename}"
        bl_path = upload_dir / f"{uuid4().hex}_{bac_lieu_file.filename}"
        ca_mau_file.save(ca_path)
        bac_lieu_file.save(bl_path)
        try:
            records, total = load_filtered_tickets(ca_path, bl_path)
            now = _now()
            current_codes = {record["subscriber_code"] for record in records}
            waiting_tickets = Ticket.query.filter_by(status=Ticket.STATUS_WAITING).all()
            status_changed_count = 0
            for ticket in waiting_tickets:
                if ticket.subscriber_code not in current_codes:
                    ticket.status = Ticket.STATUS_NOT_LATEST
                    ticket.status_changed_at = now
                    status_changed_count += 1

            existing_tickets = {
                ticket.subscriber_code: ticket
                for ticket in Ticket.query.filter(Ticket.subscriber_code.in_(current_codes)).all()
            }
            new_count = sum(record["subscriber_code"] not in existing_tickets for record in records)
            existing_count = len(records) - new_count
            batch = UploadBatch(
                uploaded_at=now,
                uploaded_by_id=current_user.id,
                ca_mau_filename=ca_mau_file.filename,
                bac_lieu_filename=bac_lieu_file.filename,
                total_tickets=total,
                over_48h_tickets=len(records),
                new_tickets=new_count,
                status_changed_tickets=status_changed_count,
                existing_tickets=existing_count,
            )
            db.session.add(batch)
            db.session.flush()
            for record in records:
                ticket = existing_tickets.get(record["subscriber_code"])
                if ticket is None:
                    record["status"] = Ticket.STATUS_WAITING
                    ticket = Ticket(
                        batch_id=batch.id,
                        latest_batch_id=batch.id,
                        last_seen_at=now,
                        status_changed_at=now,
                        **record,
                    )
                    db.session.add(ticket)
                    continue

                ticket.latest_batch_id = batch.id
                ticket.last_seen_at = now
                if ticket.status != Ticket.STATUS_WAITING:
                    ticket.status = Ticket.STATUS_WAITING
                    ticket.status_changed_at = now
                for field, value in record.items():
                    if field != "status":
                        setattr(ticket, field, value)
            db.session.commit()
            flash(
                f"Upload thành công: thêm mới {new_count} phiếu; chuyển trạng thái khác {status_changed_count} phiếu; "
                f"đã tồn tại {existing_count} phiếu.",
                "success",
            )
            return redirect(url_for("main.dashboard"))
        except Exception as error:
            db.session.rollback()
            flash(f"Không thể xử lý file: {error}", "error")
        finally:
            ca_path.unlink(missing_ok=True)
            bl_path.unlink(missing_ok=True)
    return render_template("upload.html")


@main_bp.post("/tickets/<int:ticket_id>/reason")
@login_required
def update_reason(ticket_id: int):
    ticket = db.get_or_404(Ticket, ticket_id)
    
    if not current_user.is_admin:
        allowed_units = _get_allowed_units()
        if ticket.unit not in allowed_units:
            flash("Bạn không có quyền cập nhật phiếu của đơn vị khác.", "error")
            return redirect(url_for("main.dashboard"))

    reason = request.form.get("reason", "").strip()
    now = _now()
    image_files = request.files.getlist("images")
    named_images = [image for image in image_files if image and image.filename]
    valid_images = [image for image in named_images if _image_allowed(image.filename)]
    reason_changed = reason != (ticket.reason or "")
    if reason_changed:
        audit = ReasonAudit(
            ticket_id=ticket.id,
            old_reason=ticket.reason,
            new_reason=reason,
            changed_by_id=current_user.id,
            changed_at=now,
        )
        ticket.reason = reason or None
        ticket.reason_updated_by_id = current_user.id
        ticket.reason_updated_at = now
        db.session.add(audit)
    for image in valid_images:
        stored_filename = f"{uuid4().hex}_{Path(image.filename).name}"
        image.save(current_app.config["UPLOAD_DIR"] / stored_filename)
        db.session.add(TicketImage(
            ticket_id=ticket.id,
            original_filename=Path(image.filename).name,
            stored_filename=stored_filename,
            uploaded_at=now,
            uploaded_by_id=current_user.id,
        ))
    if reason_changed or valid_images:
        db.session.commit()
        flash("Đã cập nhật xác minh và hình ảnh minh họa.", "success")
    if len(valid_images) != len(named_images):
        flash("Một số hình ảnh không hợp lệ; chỉ nhận JPG, JPEG, PNG hoặc WEBP.", "error")
    return redirect(request.referrer or url_for("main.dashboard"))


@main_bp.get("/ticket-images/<int:image_id>")
@login_required
def ticket_image(image_id: int):
    image = db.get_or_404(TicketImage, image_id)
    return send_from_directory(current_app.config["UPLOAD_DIR"], image.stored_filename)


@main_bp.get("/export.xlsx")
@login_required
def export_xlsx():
    batch = UploadBatch.query.order_by(UploadBatch.uploaded_at.desc()).first()
    if not batch:
        flash("Chưa có dữ liệu để xuất.", "error")
        return redirect(url_for("main.dashboard"))
        
    ticket_query = Ticket.query.filter_by(status=Ticket.STATUS_WAITING)
    tickets = ticket_query.order_by(Ticket.unit, Ticket.age_hours.desc()).all()
    
    detail = pd.DataFrame([
        {
            "STT": index,
            "Đơn vị": ticket.unit,
            "Tỉnh": ticket.province,
            "Loại HĐ": ticket.contract_type,
            "Loại TB": ticket.equipment_type,
            "Mã thuê bao": ticket.subscriber_code,
            "Tên thuê bao": ticket.subscriber_name,
            "NGAY LAPPHIEU": ticket.request_at.strftime("%d/%m/%Y %H:%M:%S"),
            "THOIGIAN_TON (h)": float(ticket.age_hours),
            "Diachi Ld": ticket.address or "",
            "So Dt": ticket.phone or "",
            "Trạng thái": ticket.status,
            "TTVT báo lý do tồn": ticket.reason or "",
            "Người cập nhật": ticket.reason_updated_by.full_name if ticket.reason_updated_by else "",
            "Thời gian cập nhật": ticket.reason_updated_at.strftime("%d/%m/%Y %H:%M:%S") if ticket.reason_updated_at else "",
        }
        for index, ticket in enumerate(tickets, 1)
    ])
    summary = detail.groupby("Đơn vị", dropna=False).agg(
        total=("Mã thuê bao", "count"),
        reported=("TTVT báo lý do tồn", lambda values: (values.astype(str).str.strip() != "").sum()),
    ).reset_index()
    summary = summary.rename(columns={"total": "Tổng", "reported": "Đã xác minh"})
    summary["Tỷ lệ xác minh (%)"] = (summary["Đã xác minh"] * 100 / summary["Tổng"]).round(2)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Tổng hợp", index=False)
        detail.to_excel(writer, sheet_name="Tồn trên 48h", index=False)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"bao_cao_ton_{_now():%Y%m%d_%H%M%S}.xlsx")


@main_bp.get("/users")
@login_required
def users():
    if not current_user.is_admin:
        flash("Bạn không có quyền quản lý người dùng.", "error")
        return redirect(url_for("main.dashboard"))
    return render_template("users.html", users=User.query.order_by(User.full_name).all())


@main_bp.post("/users")
@login_required
def create_user():
    if not current_user.is_admin:
        return redirect(url_for("main.dashboard"))
    user = User(
        email=request.form["email"].strip().lower(),
        full_name=request.form["full_name"].strip(),
        unit=request.form["unit"].strip(),
        phone=request.form.get("phone", "").strip(),
        is_admin=request.form.get("is_admin") == "on",
    )
    user.set_password(request.form["password"])
    db.session.add(user)
    db.session.commit()
    flash("Đã tạo người dùng.", "success")
    return redirect(url_for("main.users"))


@main_bp.get("/login-logs")
@login_required
def login_logs():
    if not current_user.is_admin:
        flash("Bạn không có quyền xem lịch sử đăng nhập.", "error")
        return redirect(url_for("main.dashboard"))
    logs = LoginLog.query.order_by(LoginLog.logged_at.desc()).limit(150).all()
    return render_template("login_logs.html", logs=logs)