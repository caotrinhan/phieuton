# Hệ thống giám sát phiếu tồn lắp đặt >48 giờ

Ứng dụng Flask đọc hai file Excel Cà Mau/Bạc Liêu, lọc phiếu `THOIGIAN_TON > 48`, lưu vào MySQL database `phieuton`, theo dõi trạng thái xuyên các lần upload, nhập lý do và xuất Excel.

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

## 9. Trạng thái phiếu

- `ĐANG CHỜ XÁC MINH`: mã còn trong danh sách mới nhất và hiển thị để nhập lý do.
- `KHÔNG CÓ TRONG DANH SÁCH MỚI NHẤT`: mã từng tồn nhưng biến mất khỏi lần upload mới.

## 10. Quy trình hằng ngày

1. Đăng nhập.
2. Upload file Cà Mau và Bạc Liêu.
3. Hệ thống lọc phiếu tồn trên 48 giờ.
4. Dashboard hiển thị bảng Tổng hợp và Chi tiết.
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
