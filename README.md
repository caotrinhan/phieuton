# Hệ thống theo dõi phiếu chưa hoàn công

Tài liệu vận hành và phát triển chi tiết: [HUONG_DAN_VAN_HANH.md](HUONG_DAN_VAN_HANH.md)

Ứng dụng Flask đọc hai file Excel template mới Cà Mau/Bạc Liêu, lưu danh sách phiếu chưa hoàn công vào MySQL database `phieuton`, tính giờ tồn trực tiếp từ ngày yêu cầu, hiển thị hai nhóm phiếu từ 48 giờ trở lên/dưới 48 giờ, nhập lý do và xuất Excel.

## 1. Lưu ý port

Spring Boot hiện đang chạy `server.port=80`, vì vậy Flask chạy ở port `8888`.

- Spring Boot: `http://10.96.31.30/`
- Website phiếu tồn: `http://10.96.31.30:8888/`

Không chạy Flask trên port 80 khi Spring Boot vẫn đang dùng port đó.

## 2. Database MySQL

MySQL hiện có:

```text
Host: localhost
Port: 3306
Database: phieuton
Username: root
Password: nhutcm
```

Trên server, chạy toàn bộ `schema.sql`:

```powershell
mysql -u root -p phieuton < schema.sql
```

Nhập mật khẩu `nhutcm`. Schema tạo các bảng `users`, `upload_batches`, `tickets`, `reason_audits` và `ticket_images`.

Khuyến nghị sau khi hệ thống chạy ổn: tạo user MySQL riêng cho Flask, không dùng root cho ứng dụng web.

## 3. Chuẩn bị Windows Server 2016

1. Cài Python 3.12.x 64-bit.
2. Kiểm tra MySQL service đang chạy.
3. Cài Microsoft Visual C++ Redistributable 2015-2022 x64 nếu Python/pandas yêu cầu.
4. Tạo thư mục `C:\Apps\ton_lap_dat_web`.
5. Chép mã nguồn dự án vào thư mục đó.
6. Cấp quyền đọc/ghi thư mục `uploads` cho tài khoản chạy web.
7. Mở firewall port 8888 cho mạng LAN.

Kiểm tra:

```powershell
python --version
Get-Service MySQL*
Test-NetConnection 127.0.0.1 -Port 3306
```

## 4. Cài và cấu hình trên server

Mở PowerShell bằng Administrator:

```powershell
cd C:\Apps\ton_lap_dat_web
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Mở `.env` và đặt:

```env
SECRET_KEY=tao-mot-chuoi-bi-mat-dai
DATABASE_URL=mysql+pymysql://root:nhutcm@127.0.0.1:3306/phieuton
MAX_CONTENT_LENGTH=52428800
UPLOAD_DIR=C:\Apps\ton_lap_dat_web\uploads
```

Không đưa `.env` lên Git hoặc gửi cho người khác vì có mật khẩu MySQL.

Tạo tài khoản admin lần đầu:

```powershell
.\.venv\Scripts\python.exe seed_admin.py
```

## 5. Chạy website

```powershell
cd C:\Apps\ton_lap_dat_web
.\.venv\Scripts\waitress-serve.exe --listen=0.0.0.0:8888 run:app
```

Truy cập từ máy trong LAN:

```text
http://10.96.31.30:8888/
```

## 6. Mở, tắt, kiểm tra website

```powershell
.\start_web.ps1
.\status_web.ps1
.\stop_web.ps1
```

## 7. Firewall

```powershell
New-NetFirewallRule -DisplayName "Phieu ton web 8888 LAN" -Direction Inbound -Protocol TCP -LocalPort 8888 -Action Allow -RemoteAddress <DIA_CHI_MANG_LAN>
```

Kiểm tra từ laptop:

```powershell
Test-NetConnection 10.96.31.30 -Port 8888
```

## 8. Migration dashboard và hình ảnh

Sau khi cập nhật phiên bản có dashboard mới, chạy migration một lần trên server trước khi mở web:

```powershell
mysql -u root -p phieuton < migration_dashboard.sql
```

Migration thêm bộ đếm upload, địa chỉ/số điện thoại, bảng hình ảnh và chuyển các mốc thời gian cũ từ UTC sang giờ Việt Nam. Không chạy lại file này lần thứ hai.

Hình ảnh minh họa được lưu trong thư mục `uploads`; khi sao lưu phải sao lưu cả thư mục này cùng database.

Khi cập nhật lên phiên bản tính giờ tồn động, chạy migration một lần:

```powershell
mysql -u root -p phieuton < migration_dynamic_age.sql
```

Migration cho phép cột `age_hours` cũ nhận `NULL`; hệ thống không còn ghi giá trị giờ tồn vào cột này mà tính trực tiếp từ `request_at`.

Khi cập nhật chức năng lưu tiến trình, chạy migration một lần trên database hiện có:

```powershell
mysql -u root -p phieuton < migration_ticket_progress.sql
```

Migration thêm cột `progress` vào bảng `tickets`. Upload sẽ lưu tất cả dòng có mã thuê bao và ngày yêu cầu hợp lệ, kèm giá trị `TIEN_TRINH`; dashboard chỉ hiển thị dòng có tiến trình `Đã giao thi công`.
Các danh sách trên dashboard, API và file Excel được phân nhóm >48h/<48h ở backend và chỉ lấy phiếu thuộc lần upload mới nhất. Dashboard tự vẽ biểu đồ thanh chồng từ hai danh sách này: phiếu ≥48h theo nhóm 48–72h/72–96h/trên 96h, phiếu <48h theo loại thiết bị; không cần nhúng Power BI hay cài thêm thư viện biểu đồ.

## 9. Trạng thái phiếu

- `CHƯA HOÀN CÔNG`: mã thuê bao có trong file upload gần nhất.
- `ĐÃ HOÀN CÔNG`: mã thuê bao đã có trong database nhưng không còn trong file upload gần nhất.
- Dashboard tính thời gian tồn động từ ngày yêu cầu; phiếu đúng 48 giờ được xếp vào bảng từ 48 giờ trở lên.

## 10. Quy trình hằng ngày

1. Đăng nhập.
2. Upload file Cà Mau và Bạc Liêu.
3. Hệ thống lưu tất cả dòng có mã thuê bao và ngày yêu cầu hợp lệ, kèm giá trị `TIEN_TRINH`; mã đã có được cập nhật, không tạo bản ghi trùng.
4. Dashboard chỉ hiển thị dòng có tiến trình `Đã giao thi công`, phân thành hai bảng: từ 48 giờ trở lên và dưới 48 giờ.
5. Người dùng nhập lý do và có thể đính kèm hình ảnh.
6. Hệ thống lưu người cập nhật, thời gian cập nhật và lịch sử cũ/mới.
7. Xuất Excel khi cần báo cáo.

## 11. Sao lưu

```powershell
mysqldump -u root -p phieuton > C:\Backup\phieuton_%DATE:~6,4%%DATE:~3,2%%DATE:~0,2%.sql
```

## 12. Đồng bộ code bằng Git

Chỉ đưa mã nguồn và file migration lên Git. Không đưa `.env`, `.venv`, `uploads`, `instance` hoặc log lên Git.

Trên laptop sau mỗi lần sửa code:

```powershell
git add .
git commit -m "Mo ta thay doi"
git push origin main
```

Trên Windows Server:

```powershell
cd C:\Apps\ton_lap_dat_web
.\stop_web.ps1
git pull origin main
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start_web.ps1
```

Giữ nguyên `.env`, `.venv`, `uploads` và `instance` trên server. Nếu có migration mới, chạy migration bằng MySQL trước khi khởi động website.
