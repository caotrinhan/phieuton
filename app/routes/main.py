from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pandas as pd
from flask import Blueprint, current_app, flash, redirect, render_template, request, send_file, send_from_directory, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import SQLAlchemyError
from ..extensions import db
from ..models import ReasonAudit, Ticket, TicketImage, UploadBatch, User, LoginLog, TrungTamMapping
from ..time_utils import local_now


main_bp = Blueprint("main", __name__)

ACTIVE_USERS = {}
UPLOAD_PROGRESS_STATUS = "đã giao thi công"
OPEN_TICKET_EQUIPMENT_TYPES = (
    "Internet tr",
    "Leasedline",
    "Megawan",
    "MetroNet",
    "MyTV",
    "Fiber",
    "Camera",
    "Mesh",
)


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]


def _now() -> datetime:
    return local_now()


def _image_allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in {"jpg", "jpeg", "png", "webp"}


def _get_allowed_units() -> list:
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


def _get_open_ticket_groups(now: datetime | None = None) -> tuple[list[Ticket], list[Ticket]]:
    now = now or _now()
    tickets = (
        Ticket.query.filter(
            Ticket.status.in_(
                [
                    Ticket.STATUS_PENDING,
                    Ticket.STATUS_WAITING,
                    Ticket.STATUS_UNDER_48H,
                ]
            ),
            db.or_(
                *(
                    Ticket.equipment_type.ilike(f"%{equipment_type}%")
                    for equipment_type in OPEN_TICKET_EQUIPMENT_TYPES
                )
            ),
        )
        .order_by(Ticket.unit, Ticket.request_at.asc())
        .all()
    )
    over_48h = []
    under_48h = []
    threshold = timedelta(hours=48)
    for ticket in tickets:
        progress = (ticket.progress or "").strip().casefold()
        if progress != UPLOAD_PROGRESS_STATUS:
            continue
        if now - ticket.request_at >= threshold:
            over_48h.append(ticket)
        else:
            under_48h.append(ticket)
    return over_48h, under_48h


def load_new_tickets(ca_mau_path, bac_lieu_path):
    """
    Đọc các dòng có mã thuê bao trong hai file template mới.
    """
    df_cm = pd.read_excel(ca_mau_path)
    df_bl = pd.read_excel(bac_lieu_path)

    df_cm.columns = df_cm.columns.astype(str).str.strip().str.lower()
    df_bl.columns = df_bl.columns.astype(str).str.strip().str.lower()

    required_columns = {"ma_tb", "ngay_yeucau", "tien_trinh"}
    for frame, source in ((df_cm, "Cà Mau"), (df_bl, "Bạc Liêu")):
        missing_columns = required_columns.difference(frame.columns)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"File {source} thiếu cột: {missing}")

    df = pd.concat([df_cm, df_bl], ignore_index=True)
    records = []

    for row_number, (_, row) in enumerate(df.iterrows(), start=2):
        subscriber_code = "" if pd.isna(row["ma_tb"]) else str(row["ma_tb"]).strip()
        if not subscriber_code:
            continue

        request_at = pd.to_datetime(row["ngay_yeucau"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
        if pd.isna(request_at):
            request_at = pd.to_datetime(row["ngay_yeucau"], errors="coerce")
        if pd.isna(request_at):
            raise ValueError(f"Dòng {row_number}: ngày yêu cầu không hợp lệ.")
        if request_at.tzinfo is not None:
            request_at = request_at.tz_localize(None)

        record = {
            "province": "" if pd.isna(row.get("tentinh")) else str(row.get("tentinh")).strip(),
            "contract_type": "" if pd.isna(row.get("loai_hopdong")) else str(row.get("loai_hopdong")).strip(),
            "equipment_type": "" if pd.isna(row.get("tenloai_tb")) else str(row.get("tenloai_tb")).strip(),
            "progress": "" if pd.isna(row["tien_trinh"]) else str(row["tien_trinh"]).strip(),
            "subscriber_code": subscriber_code,
            "subscriber_name": "" if pd.isna(row.get("ten_kh")) else str(row.get("ten_kh")).strip(),
            "request_at": request_at.to_pydatetime(),
            "address": "" if pd.isna(row.get("diachi_lapdat")) else str(row.get("diachi_lapdat")).strip(),
            "phone": "" if pd.isna(row.get("sodt_lh")) else str(row.get("sodt_lh")).strip(),
            "unit": "" if pd.isna(row.get("donvi_lapdat")) else str(row.get("donvi_lapdat")).strip(),
        }
        records.append(record)

    return records, len(df)


@main_bp.before_request
def track_active_users():
    if request.path.startswith('/static') or request.path.startswith('/ticket-images') or request.path.startswith('/api/ping'):
        return
        
    if current_user.is_authenticated:
        identifier = f"user_{current_user.id}"
        display_name = f"{current_user.email};"
    else:
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip and ',' in ip:
            ip = ip.split(',')[0].strip()
        identifier = f"guest_{ip}"
        display_name = f"Khách (IP: {ip})"
        
    ACTIVE_USERS[identifier] = {
        "name": display_name,
        "last_active": datetime.now()
    }


@main_bp.get("/api/ping")
def ping_online():
    if request.args.get('action') == 'leave':
        if current_user.is_authenticated:
            identifier = f"user_{current_user.id}"
        else:
            ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            if ip and ',' in ip:
                ip = ip.split(',')[0].strip()
            identifier = f"guest_{ip}"
        ACTIVE_USERS.pop(identifier, None)
        return {"online_count": len(ACTIVE_USERS), "online_users": [v["name"] for v in ACTIVE_USERS.values()]}
        
    if current_user.is_authenticated:
        identifier = f"user_{current_user.id}"
        display_name = current_user.email
    else:   
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip and ',' in ip:
            ip = ip.split(',')[0].strip()
        identifier = f"guest_{ip}"
        display_name = f"Khách (IP: {ip})"
        
    ACTIVE_USERS[identifier] = {
        "name": display_name,
        "last_active": datetime.now()
    }
    
    threshold = datetime.now() - timedelta(seconds=15)
    expired_keys = [k for k, v in ACTIVE_USERS.items() if v["last_active"] < threshold]
    for k in expired_keys:
        ACTIVE_USERS.pop(k, None)
        
    user_list = [v["name"] for v in ACTIVE_USERS.values()]
    return {
        "online_count": len(ACTIVE_USERS),
        "online_users": user_list
    }


@main_bp.get("/")
def dashboard():
    batch = UploadBatch.query.order_by(UploadBatch.uploaded_at.desc()).first()
    tickets, under_48h_tickets = _get_open_ticket_groups()
    
    units = {}
    for ticket in tickets:
        item = units.setdefault(ticket.unit, {"total": 0, "MegaWAN/MetroNET": 0, "fiber": 0, "mytv": 0, "mesh": 0, "camera": 0, "reported": 0, "requires_reason_recheck": 0})
        item["total"] += 1
        item["requires_reason_recheck"] += ticket.requires_reason_recheck
        equipment = (ticket.equipment_type or "").lower()
        if "megawan" in equipment or "metronet" in equipment or "internet tr" in equipment:
            item["MegaWAN/MetroNET"] += 1
        elif equipment == "fiber":
            item["fiber"] += 1
        elif equipment == "mytv":
            item["mytv"] += 1
        elif "mesh" in equipment:
            item["mesh"] += 1
        elif "camera" in equipment:
            item["camera"] += 1
        item["reported"] += bool(ticket.reason and ticket.reason.strip())
        
    sorted_units = sorted(units.items(), key=lambda x: x[1]["total"], reverse=True)

    summary_rows = [{"stt": index, "unit": unit, **item} for index, (unit, item) in enumerate(sorted_units, 1)]
    summary_total = {
        "total": sum(row["total"] for row in summary_rows),
        "MegaWAN/MetroNET": sum(row["MegaWAN/MetroNET"] for row in summary_rows),
        "fiber": sum(row["fiber"] for row in summary_rows),
        "mytv": sum(row["mytv"] for row in summary_rows),
        "mesh": sum(row["mesh"] for row in summary_rows),
        "camera": sum(row["camera"] for row in summary_rows),
        "reported": sum(row["reported"] for row in summary_rows),
        "requires_reason_recheck": sum(row["requires_reason_recheck"] for row in summary_rows),
    }
    
    allowed_units = _get_allowed_units() if current_user.is_authenticated else []
    all_users = User.query.order_by(User.full_name).all() if (current_user.is_authenticated and current_user.is_admin) else []

    return render_template(
        "dashboard.html", 
        batch=batch, 
        tickets=tickets, 
        under_48h_tickets=under_48h_tickets,
        units=units, 
        summary_rows=summary_rows, 
        summary_total=summary_total,
        allowed_units=allowed_units,
        all_users=all_users
    )


@main_bp.post("/change-password")
@login_required
def change_password():
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if new_password != confirm_password:
        flash("Mật khẩu mới và xác nhận mật khẩu không khớp.", "error")
        return redirect(url_for("main.dashboard"))

    current_user.set_password(new_password)
    db.session.commit()
    
    flash("Đổi mật khẩu thành công!", "success")
    return redirect(url_for("main.dashboard"))


@main_bp.post("/admin/reset-password-user")
@login_required
def admin_reset_password_user():
    if not current_user.is_admin:
        flash("Bạn không có quyền thực hiện thao tác này.", "error")
        return redirect(url_for("main.dashboard"))
        
    target_email = request.form.get("target_email", "").strip().lower()
    if not target_email:
        flash("Vui lòng cung cấp email/username người dùng cần reset.", "error")
        return redirect(url_for("main.dashboard"))
        
    user_to_reset = User.query.filter_by(email=target_email).first()
    if not user_to_reset:
        flash(f"Không tìm thấy người dùng với email/username: {target_email}", "error")
        return redirect(url_for("main.dashboard"))
        
    user_to_reset.set_password("1")
    db.session.commit()
    
    flash(f"Đã reset thành công mật khẩu của tài khoản {target_email} về '1'.", "success")
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


@main_bp.route("/upload-new", methods=["GET", "POST"])
@login_required
def upload_new_template():
    if not current_user.is_admin:
        flash("Bạn không có quyền thực hiện chức năng upload file.", "error")
        return redirect(url_for("main.dashboard"))

    if request.method == "GET":
        return render_template("upload.html")

    ca_mau_file = request.files.get("ca_mau_moi")
    bac_lieu_file = request.files.get("bac_lieu_moi")
    
    if not ca_mau_file or not bac_lieu_file or not ca_mau_file.filename or not bac_lieu_file.filename:
        flash("Vui lòng chọn đủ hai file Excel template mới.", "error")
        return redirect(url_for("main.dashboard"))
        
    if not _allowed(ca_mau_file.filename) or not _allowed(bac_lieu_file.filename):
        flash("Chỉ chấp nhận file .xlsx hoặc .xls.", "error")
        return redirect(url_for("main.dashboard"))

    upload_dir: Path = Path(current_app.config["UPLOAD_DIR"])
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    ca_path = upload_dir / f"{uuid4().hex}_{ca_mau_file.filename}"
    bl_path = upload_dir / f"{uuid4().hex}_{bac_lieu_file.filename}"
    ca_mau_file.save(ca_path)
    bac_lieu_file.save(bl_path)
    
    try:
        records, total = load_new_tickets(ca_path, bl_path)
        now = _now()
        current_codes = {record["subscriber_code"].strip().lower() for record in records}
        existing_tickets = {}
        for ticket in Ticket.query.order_by(Ticket.id.desc()).all():
            code_key = (ticket.subscriber_code or "").strip().lower()
            if code_key and code_key not in existing_tickets:
                existing_tickets[code_key] = ticket

        batch = UploadBatch(
            uploaded_at=now,
            uploaded_by_id=current_user.id,
            ca_mau_filename=ca_mau_file.filename,
            bac_lieu_filename=bac_lieu_file.filename,
            total_tickets=total,
            over_48h_tickets=sum(
                now - record["request_at"] >= timedelta(hours=48)
                for record in records
            ),
            new_tickets=0,
            status_changed_tickets=0,
            existing_tickets=0,
        )
        db.session.add(batch)
        db.session.flush()

        existing_db_codes = set(existing_tickets)
        new_codes = set()
        existing_codes = set()
        for record in records:
            code_key = record["subscriber_code"].strip().lower()
            ticket = existing_tickets.get(code_key)
            if code_key in existing_db_codes:
                existing_codes.add(code_key)
            else:
                new_codes.add(code_key)
            if ticket is None:
                ticket = Ticket(
                    batch_id=batch.id,
                    latest_batch_id=batch.id,
                    status=Ticket.STATUS_PENDING,
                    last_seen_at=now,
                    status_changed_at=now,
                    **record,
                )
                db.session.add(ticket)
                existing_tickets[code_key] = ticket
            else:
                ticket.latest_batch_id = batch.id
                ticket.last_seen_at = now
                if ticket.status != Ticket.STATUS_PENDING:
                    ticket.status_changed_at = now
                ticket.status = Ticket.STATUS_PENDING
                for field, value in record.items():
                    setattr(ticket, field, value)

        status_changed_count = 0
        for ticket in Ticket.query.all():
            code_key = (ticket.subscriber_code or "").strip().lower()
            if code_key not in current_codes and ticket.status != Ticket.STATUS_COMPLETED:
                ticket.status = Ticket.STATUS_COMPLETED
                ticket.status_changed_at = now
                status_changed_count += 1

        batch.new_tickets = len(new_codes)
        batch.existing_tickets = len(existing_codes)
        batch.status_changed_tickets = status_changed_count

        db.session.commit()
        flash(
            f"Upload thành công: thêm mới {len(new_codes)} phiếu; cập nhật {len(existing_codes)} phiếu; "
            f"đã chuyển {status_changed_count} phiếu không còn trong file thành đã hoàn công.",
            "success",
        )
        return redirect(url_for("main.dashboard"))

    except Exception as error:
        db.session.rollback()
        current_app.logger.exception("Không thể xử lý file template mới.")
        flash(f"Không thể xử lý file template mới: {error}", "error")
        return redirect(url_for("main.upload_new_template"))
    finally:
        ca_path.unlink(missing_ok=True)
        bl_path.unlink(missing_ok=True)

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
    
    upload_dir = Path(current_app.config["UPLOAD_DIR"])
    upload_dir.mkdir(parents=True, exist_ok=True)

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
        image.save(upload_dir / stored_filename)
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


@main_bp.post("/tickets/<int:ticket_id>/check-again")
@login_required
def update_reason_recheck(ticket_id: int):
    if not current_user.is_admin:
        flash("Bạn không có quyền cập nhật yêu cầu check lại lý do tồn.", "error")
        return redirect(url_for("main.dashboard"))

    value = request.form.get("requires_reason_recheck")
    if value not in {"true", "false"}:
        flash("Giá trị yêu cầu check lại không hợp lệ.", "error")
        return redirect(url_for("main.dashboard"))

    ticket = db.get_or_404(Ticket, ticket_id)
    ticket.requires_reason_recheck = value == "true"
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Không thể cập nhật yêu cầu check lại cho ticket %s.", ticket_id)
        flash("Không thể lưu trạng thái yêu cầu check lại. Vui lòng thử lại.", "error")
    else:
        status = "có" if ticket.requires_reason_recheck else "không"
        flash(f"Đã cập nhật thuê bao {ticket.subscriber_code}: {status} yêu cầu check lại lý do tồn.", "success")
    return redirect(url_for("main.dashboard"))


@main_bp.get("/ticket-images/<int:image_id>")
def ticket_image(image_id: int):
    image = db.get_or_404(TicketImage, image_id)
    upload_dir = Path(current_app.config["UPLOAD_DIR"])
    return send_from_directory(upload_dir, image.stored_filename)


@main_bp.get("/export.xlsx")
@login_required
def export_xlsx():
    batch = UploadBatch.query.order_by(UploadBatch.uploaded_at.desc()).first()
    if not batch:
        flash("Chưa có dữ liệu để xuất.", "error")
        return redirect(url_for("main.dashboard"))

    over_48h_tickets, under_48h_tickets = _get_open_ticket_groups()

    def ticket_rows(tickets: list[Ticket]) -> list[dict]:
        return [
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
                "Yêu cầu check lại lý do tồn": ticket.requires_reason_recheck,
                "Trạng thái": ticket.status,
                "TTVT báo lý do tồn": ticket.reason or "",
                "Người cập nhật": ticket.reason_updated_by.full_name if ticket.reason_updated_by else "",
                "Thời gian cập nhật": ticket.reason_updated_at.strftime("%d/%m/%Y %H:%M:%S") if ticket.reason_updated_at else "",
            }
            for index, ticket in enumerate(tickets, 1)
        ]

    detail_columns = [
        "STT", "Đơn vị", "Tỉnh", "Loại HĐ", "Loại TB", "Mã thuê bao", "Tên thuê bao",
        "NGAY LAPPHIEU", "THOIGIAN_TON (h)", "Diachi Ld", "So Dt",
        "Yêu cầu check lại lý do tồn", "Trạng thái", "TTVT báo lý do tồn",
        "Người cập nhật", "Thời gian cập nhật",
    ]
    detail = pd.DataFrame(ticket_rows(over_48h_tickets), columns=detail_columns)
    under_48h_detail = pd.DataFrame(ticket_rows(under_48h_tickets), columns=detail_columns)
    summary = detail.groupby("Đơn vị", dropna=False).agg(
        total=("Mã thuê bao", "count"),
        requires_reason_recheck=("Yêu cầu check lại lý do tồn", "sum"),
        megawan_metronet=(
            "Loại TB",
            lambda values: values.astype(str).str.lower().str.contains("megawan|metronet", regex=True).sum(),
        ),
        reported=("TTVT báo lý do tồn", lambda values: (values.astype(str).str.strip() != "").sum()),
    ).reset_index()
    summary = summary.rename(columns={
        "total": "Tổng",
        "requires_reason_recheck": "Yêu cầu check lại lý do tồn",
        "megawan_metronet": "MegaWAN/MetroNET",
        "reported": "Đã xác minh",
    })
    summary["Tỷ lệ xác minh (%)"] = (summary["Đã xác minh"] * 100 / summary["Tổng"]).round(2)
    summary = summary[[
        "Đơn vị",
        "Tổng",
        "MegaWAN/MetroNET",
        "Đã xác minh",
        "Tỷ lệ xác minh (%)",
        "Yêu cầu check lại lý do tồn",
    ]]
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Tổng hợp", index=False)
        detail.to_excel(writer, sheet_name="Tồn trên 48h", index=False)
        under_48h_detail.to_excel(writer, sheet_name="Tồn dưới 48h", index=False)
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


@main_bp.get("/api/table-data")
def get_table_data():
    over_48h_tickets, under_48h_tickets = _get_open_ticket_groups()

    def serialize_tickets(tickets: list[Ticket]) -> list[dict]:
        return [
            {
                "id": ticket.id,
                "stt": index,
                "unit": ticket.unit,
                "equipment_type": ticket.equipment_type,
                "subscriber_code": ticket.subscriber_code,
                "subscriber_name": ticket.subscriber_name,
                "request_at": ticket.request_at.strftime("%d/%m/%Y %H:%M:%S"),
                "age_hours": ticket.age_hours,
                "requires_reason_recheck": ticket.requires_reason_recheck,
                "reason": ticket.reason or "",
                "address": ticket.address or "",
                "phone": ticket.phone or "",
                "contract_type": ticket.contract_type or "",
                "status": ticket.status,
                "reason_updated_by": ticket.reason_updated_by.email if ticket.reason_updated_by else None,
                "reason_updated_at": (
                    ticket.reason_updated_at.strftime("%d/%m/%Y %H:%M:%S")
                    if ticket.reason_updated_at
                    else None
                ),
                "images": [
                    {
                        "id": image.id,
                        "url": url_for("main.ticket_image", image_id=image.id),
                        "name": image.original_filename,
                    }
                    for image in ticket.images
                ],
            }
            for index, ticket in enumerate(tickets, 1)
        ]

    return {
        "over_48h_tickets": serialize_tickets(over_48h_tickets),
        "under_48h_tickets": serialize_tickets(under_48h_tickets),
    }