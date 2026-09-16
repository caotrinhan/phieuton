# Hướng dẫn vận hành và phát triển hệ thống

## 1. Mục đích

Tài liệu này dành cho người tiếp nhận, vận hành, bảo trì và phát triển hệ thống:

`VNPT CÀ MAU - HỆ THỐNG GIÁM SÁT PHIẾU TỒN BĂNG RỘNG CỐ ĐỊNH`

Ứng dụng nhận hai file Excel Cà Mau và Bạc Liêu, lọc các phiếu tồn trên 48 giờ, lưu dữ liệu vào MySQL, hiển thị bảng Tổng hợp/Chi tiết, cho phép cập nhật lý do tồn và hình ảnh minh họa.

Thông tin triển khai hiện tại:

- Máy chủ: Windows Server 2016.
- Web server: Waitress.
- Port: `8888`.
- URL nội bộ: `http://10.96.31.30:8888/`.
- Framework: Flask.
- Database: MySQL, database `phieuton`.
- Múi giờ nghiệp vụ: `Asia/Ho_Chi_Minh`.
- Repository: `https://github.com/caotrinhan/phieuton.git`.

## 2. Cấu trúc dự án

```text
ton_lap_dat_web/
|-- app/
|   |-- __init__.py
|   |-- extensions.py
|   |-- models.py
|   |-- time_utils.py
|   |-- routes/
|   |   |-- __init__.py
|   |   |-- auth.py
|   |   |-- main.py
|   |-- services/
|   |   |-- __init__.py
|   |   |-- import_service.py
|   |-- static/
|   |   |-- style.css
|   |-- templates/
|       |-- base.html
|       |-- login.html
|       |-- dashboard.html
|       |-- upload.html
|       |-- users.html
|-- config.py
|-- run.py
|-- seed_admin.py
|-- requirements.txt
|-- schema.sql
|-- migration_status.sql
|-- migration_dashboard.sql
|-- start_web.ps1
|-- stop_web.ps1
|-- status_web.ps1
|-- .env.example
|-- .gitignore
|-- README.md
|-- HUONG_DAN_VAN_HANH.md
|-- .env                 (không đưa lên Git)
|-- .venv/               (không đưa lên Git)
|-- uploads/             (dữ liệu ảnh, không đưa lên Git)
|-- instance/            (dữ liệu runtime, không đưa lên Git)
```

## 3. Chức năng từng file

### 3.1. Thư mục `app/`

#### `app/__init__.py`

Tạo Flask application:

- Nạp cấu hình từ `config.py` và `.env`.
- Tạo thư mục upload nếu chưa có.
- Khởi tạo SQLAlchemy và Flask-Login.
- Đăng ký route xác thực và route nghiệp vụ.
- Gọi `db.create_all()` để tạo các bảng còn thiếu khi ứng dụng khởi động.

Không đặt xử lý nghiệp vụ upload trực tiếp ở đây.

#### `app/extensions.py`

Khai báo các đối tượng dùng chung:

- `db`: SQLAlchemy.
- `login_manager`: Flask-Login.

Các module khác import đối tượng từ file này để tránh tạo nhiều kết nối hoặc nhiều instance khác nhau.

#### `app/models.py`

Định nghĩa bảng database bằng SQLAlchemy:

- `User`: tài khoản, đơn vị, số điện thoại, quyền admin.
- `UploadBatch`: thông tin mỗi lần upload và số lượng phiếu mới/đã tồn tại/đổi trạng thái.
- `Ticket`: phiếu tồn, trạng thái, lý do, thời gian và thông tin thuê bao.
- `ReasonAudit`: lịch sử thay đổi lý do.
- `TicketImage`: liên kết ảnh với phiếu.

Khi thêm hoặc đổi cột trong file này, phải tạo migration SQL tương ứng. Không chỉ sửa `models.py` rồi giả định database cũ tự cập nhật.

#### `app/time_utils.py`

Cung cấp `local_now()` theo múi giờ Việt Nam `Asia/Ho_Chi_Minh`. Dùng hàm này cho:

- Thời gian upload.
- Thời gian cập nhật lý do.
- Thời gian đổi trạng thái.
- Thời gian audit.

Không dùng lại `datetime.utcnow()` cho dữ liệu nghiệp vụ mới.

### 3.2. Routes

#### `app/routes/auth.py`

Xử lý:

- `/login`: đăng nhập.
- `/logout`: đăng xuất.
- Kiểm tra email, mật khẩu và tài khoản đang hoạt động.

Nếu thay đổi quy trình đăng nhập, phân quyền hoặc session, sửa file này và kiểm tra lại toàn bộ route có `@login_required`.

#### `app/routes/main.py`

Đây là route nghiệp vụ chính:

- `/`: dashboard trang chủ.
- `/upload`: nhận hai file Excel, lọc và lưu batch.
- `/tickets/<id>/reason`: cập nhật lý do và nhận ảnh.
- `/ticket-images/<id>`: trả ảnh cho người đã đăng nhập.
- `/export.xlsx`: xuất báo cáo Excel.
- `/users`: danh sách tài khoản admin.
- `/users` POST: tạo tài khoản.

Khi sửa luồng upload, cần kiểm tra đồng thời `import_service.py`, `models.py`, `schema.sql` và migration nếu có cột mới.

### 3.3. Services

#### `app/services/import_service.py`

Đọc và chuẩn hóa hai file Excel:

- Cà Mau: dùng các cột `LOAI TB`, `TRANGTHAI_HD`, `TEN_LOAIHD`, `DONVI_XULY_PHIEU`, `MA_TB`, `TEN_TB`, `NGAY LAPPHIEU`.
- Bạc Liêu: dùng các cột `Loaihinh Tb`, `Trangthai Hd`, `Ten Loaihd`, `Tendv Ld`, `Ma Tb`, `Ten Tb`, `Ngay Yc`, `Diachi Ld`, `So Dt`.
- Lọc loại thiết bị Fiber, MyTV, Mesh, Camera.
- Lọc trạng thái `Đã giao thi công`.
- Lọc loại hợp đồng được hỗ trợ.
- Tính `age_hours` và giữ phiếu trên 48 giờ.
- Trả về danh sách record chuẩn hóa cho route upload.

Nếu mẫu Excel thay đổi tên cột, phải sửa mapping và kiểm tra lại bằng file mẫu trước khi triển khai.

### 3.4. Giao diện

#### `app/templates/base.html`

Layout dùng chung:

- Khai báo UTF-8.
- Nạp font Roboto và `style.css`.
- Header, menu, flash message, footer.
- Script chung xử lý màu trạng thái và metadata lý do.

Mọi template có `{% extends 'base.html' %}` sẽ dùng layout này.

#### `app/templates/dashboard.html`

Dashboard trang chủ:

- Thông tin batch mới nhất.
- Kết quả upload gần nhất.
- Một bảng Tổng hợp.
- Một bảng Chi tiết.
- Modal cập nhật lý do và upload ảnh.
- Modal xem ảnh, zoom và xoay.

Khi sửa bảng, phải giữ đúng tên trường được truyền từ `main.py`.

#### `app/templates/upload.html`

Form chọn hai file Excel:

- File Cà Mau: `name="ca_mau"`.
- File Bạc Liêu: `name="bac_lieu"`.
- Bắt buộc `multipart/form-data`.

#### `app/templates/login.html`

Màn hình đăng nhập.

#### `app/templates/users.html`

Màn hình admin tạo tài khoản và xem danh sách người dùng.

#### `app/static/style.css`

Toàn bộ CSS giao diện:

- Màu nền, panel, bảng, nút, form.
- Font Roboto.
- Màu success/danger cho dòng đã/chưa xác minh.
- Border bảng.
- Modal và thumbnail ảnh.

Sau khi sửa CSS, phải hard refresh trình duyệt bằng `Ctrl + F5`.

### 3.5. File cấu hình và khởi động

#### `config.py`

Đọc các cấu hình:

- `SECRET_KEY`.
- `DATABASE_URL`.
- `MAX_CONTENT_LENGTH`.
- `UPLOAD_DIR`.
- Định dạng Excel được phép.

Không ghi mật khẩu thật trực tiếp vào `config.py`.

#### `.env`

Cấu hình riêng của máy server. Ví dụ:

```env
SECRET_KEY=chuoi-bi-mat-dai
DATABASE_URL=mysql+pymysql://root:mat-khau@127.0.0.1:3306/phieuton
MAX_CONTENT_LENGTH=52428800
UPLOAD_DIR=C:\Apps\ton_lap_dat_web\uploads
```

File `.env` không được commit lên Git.

#### `run.py`

Điểm vào WSGI cho Waitress, thường chứa `app = create_app()`.

#### `requirements.txt`

Danh sách thư viện Python. Khi thêm thư viện:

1. Sửa file.
2. Commit/push lên Git.
3. Trên server chạy `pip install -r requirements.txt`.

#### `start_web.ps1`

Khởi động Waitress trên `0.0.0.0:8888`, ghi log và chạy từ thư mục dự án.

#### `stop_web.ps1`

Dừng tiến trình Waitress.

#### `status_web.ps1`

Kiểm tra tiến trình Waitress và port `8888`.

#### `seed_admin.py`

Tạo tài khoản admin ban đầu. Chỉ chạy khi database mới hoặc cần tạo tài khoản admin mới. Nếu email đã tồn tại, không chạy lại tùy tiện.

### 3.6. Database

#### `schema.sql`

Schema đầy đủ cho database mới. Dùng khi tạo database sạch lần đầu.

#### `migration_status.sql`

Migration cho các cột quản lý trạng thái phiếu.

#### `migration_dashboard.sql`

Migration cho dashboard mới:

- Bộ đếm upload.
- Địa chỉ/số điện thoại.
- Bảng `ticket_images`.
- Chuyển dữ liệu thời gian cũ từ UTC sang giờ Việt Nam.

Migration có câu lệnh chuyển giờ, vì vậy chỉ chạy một lần trên database tương ứng.

## 4. Khởi tạo hệ thống mới

### 4.1. Chuẩn bị máy chủ

Cài:

- Python 3.12.x 64-bit.
- Git for Windows.
- MySQL.
- Visual C++ Redistributable nếu pandas yêu cầu.

Mở firewall port 8888:

```powershell
New-NetFirewallRule -DisplayName "Phieu ton web 8888 LAN" -Direction Inbound -Protocol TCP -LocalPort 8888 -Action Allow
```

### 4.2. Clone code

```powershell
cd C:\Apps
# Đi tới thư mục chứa ứng dụng

git clone https://github.com/caotrinhan/phieuton.git ton_lap_dat_web
# Tải toàn bộ mã nguồn từ GitHub
```

### 4.3. Tạo môi trường Python

```powershell
cd C:\Apps\ton_lap_dat_web
# Vào project

py -m venv .venv
# Tạo môi trường Python riêng cho web

.\.venv\Scripts\python.exe -m pip install --upgrade pip
# Cập nhật pip trong môi trường riêng

.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Cài các thư viện của dự án
```

### 4.4. Tạo cấu hình

```powershell
Copy-Item .env.example .env
# Tạo cấu hình runtime từ file mẫu
```

Mở `.env`, sửa `DATABASE_URL`, `SECRET_KEY` và `UPLOAD_DIR` theo server.

### 4.5. Tạo database

```powershell
mysql -u root -p
```

Trong MySQL:

```sql
CREATE DATABASE phieuton CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EXIT;
```

Nạp schema:

```powershell
mysql -u root -p phieuton < schema.sql
# Tạo toàn bộ bảng cho database mới
```

Tạo admin:

```powershell
.\.venv\Scripts\python.exe seed_admin.py
# Tạo tài khoản quản trị đầu tiên
```

Khởi động:

```powershell
.\start_web.ps1
# Chạy website

.\status_web.ps1
# Kiểm tra website
```

## 5. Quy trình cập nhật bằng Git

### 5.1. Trên laptop

```powershell
cd "C:\Users\caotr\OneDrive - VNPT\NHUT\2026\ton lap dat hang ngay\code\ton_lap_dat_web"
# Vào project trên laptop

git status
# Xem file đã thay đổi

git add .
# Đưa thay đổi vào vùng chuẩn bị commit

git commit -m "Mo ta thay doi"
# Tạo phiên bản có mã commit

git push origin main
# Đẩy commit lên GitHub
```

### 5.2. Trên server

```powershell
cd C:\Apps\ton_lap_dat_web
# Vào project trên server

.\stop_web.ps1
# Dừng website trước khi cập nhật

git fetch origin
# Tải thông tin commit mới, chưa ghi đè file

git reset --hard origin/main
# Đồng bộ code server đúng bằng GitHub

.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Cài thêm thư viện nếu requirements thay đổi

.\start_web.ps1
# Khởi động website
```

`git reset --hard origin/main` có thể xóa thay đổi code chưa commit trên server. Không chạy nếu server có code riêng chưa đưa lên Git.

Git không chứa và không được ghi đè:

- `.env`.
- `.venv/`.
- `uploads/`.
- `instance/`.
- Database MySQL.

### 5.3. Khi có migration

Nếu commit có migration mới:

```powershell
cd C:\Apps\ton_lap_dat_web
.\stop_web.ps1
mysql -u root -p phieuton < migration_ten_moi.sql
.\start_web.ps1
```

Đọc migration trước khi chạy. Không chạy lại migration đã có câu lệnh chuyển đổi dữ liệu.

## 6. Thay đổi giao diện

Ví dụ đổi tiêu đề dashboard:

1. Sửa `app/templates/dashboard.html`.
2. Nếu cần đổi layout chung, sửa `app/templates/base.html`.
3. Nếu đổi màu, kích thước, border, font, sửa `app/static/style.css`.
4. Kiểm tra lỗi template.
5. Commit và push.
6. Server pull và restart.
7. Trình duyệt nhấn `Ctrl + F5`.

Các file tác động:

| Mục tiêu | File chính | Có cần database? |
|---|---|---|
| Đổi tiêu đề/trường hiển thị | `dashboard.html` | Không |
| Đổi menu/footer | `base.html` | Không |
| Đổi màu/font/border | `style.css`, `base.html` | Không |
| Thêm cột hiển thị đã có trong DB | `dashboard.html`, có thể `main.py` | Không |
| Thêm dữ liệu chưa có trong DB | `models.py`, `main.py`, `schema.sql`, migration | Có |
| Đổi form upload | `upload.html`, `main.py` | Tùy |

## 7. Thay đổi port chạy web

Port hiện tại là `8888`. Khi đổi port, sửa đồng bộ:

1. `start_web.ps1`: đổi `--listen=0.0.0.0:8888`.
2. `status_web.ps1`: đổi port kiểm tra.
3. `README.md` và tài liệu triển khai.
4. Windows Firewall.
5. URL người dùng truy cập.

Ví dụ đổi sang `8899`:

```powershell
New-NetFirewallRule -DisplayName "Phieu ton web 8899 LAN" -Direction Inbound -Protocol TCP -LocalPort 8899 -Action Allow
```

Sau khi sửa script:

```powershell
.\stop_web.ps1
.\start_web.ps1
.\status_web.ps1
```

Không cần sửa Flask route chỉ vì đổi port Waitress.

## 8. Quản lý người dùng và phân quyền

### Quyền hiện tại

- Người dùng đăng nhập được xem dashboard, upload, cập nhật lý do/ảnh và xuất Excel.
- Người có `is_admin = TRUE` được vào `/users` và tạo tài khoản.
- Route yêu cầu đăng nhập dùng `@login_required`.
- Route quản trị phải kiểm tra `current_user.is_admin`.

### Tạo admin lần đầu

```powershell
.\.venv\Scripts\python.exe seed_admin.py
```

### Tạo người dùng sau khi web chạy

Đăng nhập bằng admin, mở menu `Người dùng`, nhập:

- Email.
- Họ tên.
- Đơn vị.
- Số điện thoại.
- Mật khẩu.
- Có chọn quyền quản trị hay không.

### Khi phát triển phân quyền mới

1. Thêm hoặc đổi trường quyền trong `models.py`.
2. Tạo migration nếu database cần cột mới.
3. Sửa route trong `auth.py` hoặc `main.py`.
4. Thêm kiểm tra trước thao tác nhạy cảm.
5. Ẩn/hiện menu trong template chỉ là giao diện; bảo mật thật phải nằm ở route.
6. Kiểm tra cả tài khoản thường và admin.

Không dùng cách chỉ ẩn nút bằng CSS để bảo vệ chức năng.

## 9. Backup và dữ liệu runtime

Database:

```powershell
mysqldump -u root -p phieuton > C:\Backup\phieuton_YYYYMMDD.sql
```

Ảnh minh họa:

```powershell
Copy-Item C:\Apps\ton_lap_dat_web\uploads C:\Backup\uploads -Recurse
```

Phải backup cả database và `uploads`, vì database chỉ lưu thông tin liên kết ảnh còn file ảnh nằm trên đĩa.

Không commit các dữ liệu sau:

- Mật khẩu trong `.env`.
- File Excel nghiệp vụ.
- Ảnh người dùng upload.
- Log runtime.
- `.venv`.

## 10. Kiểm tra sau triển khai

```powershell
cd C:\Apps\ton_lap_dat_web
# Vào project

git log -1 --oneline
# Kiểm tra commit đang chạy

Test-Path .\app\templates\base.html
# Kiểm tra template chung

Test-Path .\app\static\style.css
# Kiểm tra CSS

(Invoke-WebRequest http://127.0.0.1:8888/static/style.css -UseBasicParsing).StatusCode
# Kiểm tra CSS trả mã 200

.\status_web.ps1
# Kiểm tra tiến trình và port
```

Kiểm tra nghiệp vụ:

1. Đăng nhập.
2. Upload đủ hai file Excel.
3. Xác nhận dashboard có đúng một bảng Tổng hợp và một bảng Chi tiết.
4. Bấm mã thuê bao hoặc tên thuê bao.
5. Nhập lý do và chọn ảnh.
6. Bấm lưu.
7. Kiểm tra lý do, người cập nhật, thời gian và thumbnail.
8. Bấm thumbnail, thử zoom/xoay.
9. Xuất Excel.

## 11. Xử lý lỗi thường gặp

### Trang trắng hoặc không có CSS

```powershell
Test-Path .\app\static\style.css
(Invoke-WebRequest http://127.0.0.1:8888/static/style.css -UseBasicParsing).StatusCode
```

Sau đó `Ctrl + F5`.

### Code server chưa đúng bản GitHub

```powershell
git fetch origin
git reset --hard origin/main
```

### PyMySQL báo thiếu `cryptography`

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Website không chạy

```powershell
Get-Content .\waitress.stderr.log -Tail 50
```

### Không thấy ảnh

Kiểm tra:

- `uploads/` có tồn tại.
- Tài khoản chạy Waitress có quyền ghi.
- Database có bảng `ticket_images`.
- URL ảnh trả về khi người dùng đã đăng nhập.

## 12. Nguyên tắc phát triển

- Sửa đúng lớp sở hữu chức năng.
- Thay đổi database phải có migration.
- Không sửa trực tiếp database production nếu chưa hiểu tác động.
- Không commit `.env`, mật khẩu hoặc dữ liệu nghiệp vụ.
- Test trên dữ liệu mẫu trước khi cập nhật server.
- Commit nhỏ, nội dung commit rõ ràng.
- Sau mỗi thay đổi phải kiểm tra, push Git và ghi lại migration nếu có.
- Giữ nguyên tên field giữa `models.py`, route và template hoặc cập nhật đồng bộ cả ba.
