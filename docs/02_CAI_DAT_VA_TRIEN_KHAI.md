# Cài đặt và triển khai

> Các bước dưới đây là **hướng dẫn**; chưa có máy chủ hay tên miền nào được triển khai từ kho mã này.
> Lệnh được viết cho Ubuntu 22.04/24.04 LTS — tôi chưa chạy thử trên máy chủ thật, phiên bản gói hệ điều hành có thể khác,
> bạn nên đối chiếu với tài liệu chính thức của Ubuntu, PostgreSQL, Nginx, Certbot tại thời điểm triển khai.

## 0. Ba môi trường

| Môi trường | `DJANGO_ENV` | CSDL | Mục đích |
|---|---|---|---|
| Phát triển (máy cá nhân) | `development` | SQLite | Lập trình, dùng thử với dữ liệu mẫu |
| Kiểm thử (staging) | `testing` hoặc `production` trên tên miền phụ | PostgreSQL riêng | Kiểm tra bản mới, thử khôi phục sao lưu |
| Chính thức | `production` | PostgreSQL | Phục vụ thật, HTTPS, không dữ liệu mẫu |

Không dùng chung CSDL, `SECRET_KEY` hay thư mục tệp giữa các môi trường.

## 1. Cài đặt trên máy tính (phát triển)

Yêu cầu: Python 3.11+ (đã kiểm thử với 3.13), Git.

```bash
git clone <địa-chỉ-kho> mamnon && cd mamnon
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py create_admin --username quantri --email ban@truong.edu.vn   # nhập mật khẩu ẩn
python manage.py seed_demo           # (tùy chọn) dữ liệu MẪU, in mật khẩu tài khoản mẫu một lần
python manage.py runserver
```
Mở http://127.0.0.1:8000/ (website) và http://127.0.0.1:8000/quan-tri/ (quản trị).
Xóa dữ liệu mẫu: `python manage.py seed_demo --remove`.

Chạy kiểm thử: `python manage.py test` · Kiểm tra cấu hình: `python manage.py check`.

## 2. Chuẩn bị máy chủ (VPS)

Gợi ý tối thiểu cho một trường: 2 vCPU, 2–4 GB RAM, 40 GB SSD (tăng theo dung lượng ảnh/tài liệu). Đây là ước tính, chưa đo tải thực tế.

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-dev build-essential postgresql nginx certbot python3-certbot-nginx git ufw
sudo ufw allow OpenSSH && sudo ufw allow 'Nginx Full' && sudo ufw enable
sudo adduser --system --group --home /srv/mamnon mamnon
sudo mkdir -p /srv/mamnon/{app,media,protected_media,staticfiles,backups,logs}
sudo chown -R mamnon:www-data /srv/mamnon && sudo chmod 750 /srv/mamnon/protected_media /srv/mamnon/backups
```
Hosting Python dùng chung (cPanel "Setup Python App"…) cũng có thể chạy được nếu hỗ trợ WSGI, PostgreSQL và biến môi trường; khi đó
không có Nginx `X-Accel-Redirect` → để trống `PROTECTED_MEDIA_ACCEL_PREFIX` (Django tự phục vụ tệp nội bộ, chậm hơn).

## 3. Tên miền và DNS

Tại nhà cung cấp tên miền, tạo bản ghi:
- `A  @    <IP máy chủ>` · `A  www  <IP máy chủ>` (và `AAAA` nếu có IPv6).
Kiểm tra: `dig +short mamnon-ten-truong.edu.vn` trả về đúng IP (thời gian lan truyền DNS có thể từ vài phút đến vài giờ).
Tên miền `.edu.vn` có quy trình đăng ký riêng — cần kiểm tra với nhà đăng ký/cơ quan quản lý hiện hành.

## 4. PostgreSQL

```bash
sudo -u postgres psql <<'SQL'
CREATE USER mamnon WITH PASSWORD 'thay-mat-khau-manh';
CREATE DATABASE mamnon OWNER mamnon ENCODING 'UTF8';
SQL
```
Chỉ cho phép kết nối cục bộ (mặc định của Ubuntu).

## 5. Mã nguồn, biến môi trường, migration, static

```bash
sudo -u mamnon -H bash
cd /srv/mamnon && git clone <địa-chỉ-kho> app && cd app
python3 -m venv /srv/mamnon/venv && /srv/mamnon/venv/bin/pip install -r requirements.txt
cp .env.example .env && chmod 600 .env && nano .env    # điền SECRET_KEY, mật khẩu CSDL, tên miền, email...
set -a; source .env; set +a
/srv/mamnon/venv/bin/python manage.py migrate
/srv/mamnon/venv/bin/python manage.py collectstatic --noinput
/srv/mamnon/venv/bin/python manage.py check --deploy
/srv/mamnon/venv/bin/python manage.py create_admin --username quantri --email quantri@...
```
`check --deploy` sẽ còn 2 cảnh báo HSTS (W005, W021): chỉ bật `SECURE_HSTS_INCLUDE_SUBDOMAINS`/preload khi chắc chắn mọi tên miền con đều chạy HTTPS.

## 6. Gunicorn + systemd, Nginx, HTTPS

```bash
sudo cp deploy/mamnon.service deploy/mamnon-daily.service deploy/mamnon-daily.timer /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now mamnon mamnon-daily.timer
sudo cp deploy/nginx.conf /etc/nginx/sites-available/mamnon   # sửa tên miền
sudo ln -s /etc/nginx/sites-available/mamnon /etc/nginx/sites-enabled/
# Lần đầu, khi chưa có chứng chỉ: tạm comment khối server 443, rồi:
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d mamnon-ten-truong.edu.vn -d www.mamnon-ten-truong.edu.vn
sudo systemctl reload nginx
```
Xác minh: `curl -I https://<tên-miền>/` trả về 200 và header `Strict-Transport-Security`; đăng nhập thử `/quan-tri/`.
Chỉ khi các bước xác minh này thành công mới coi là website đã hoạt động.

## 7. Sao lưu tự động và kiểm tra khả năng phục hồi

- `mamnon-daily.timer` chạy `deploy/backup.sh` lúc 01:30: `pg_dump` + `backup_data` (JSON + tệp, có SHA-256) + `verify_backup`.
- Giữ `BACKUP_KEEP` bản; **sao chép ra nơi khác** (máy chủ khác/lưu trữ đám mây, mã hóa) — sao lưu chỉ trên cùng máy chủ là chưa đủ.
- Mỗi tháng thử khôi phục: `python manage.py verify_backup <tệp.zip> --restore-test` (khôi phục vào CSDL SQLite tạm, không ảnh hưởng dữ liệu thật).
  Định kỳ quý: khôi phục đầy đủ lên máy staging (mục 9).

## 8. Theo dõi lỗi và nhật ký

- Ứng dụng: `/srv/mamnon/logs/app.log` (xoay vòng 10 MB × 5) · `journalctl -u mamnon` · Nginx: `/var/log/nginx/`.
- Đặt `DJANGO_ADMIN_EMAILS` + cấu hình SMTP để nhận email khi lỗi 500 (Django gửi qua `mail_admins` khi `DEBUG=False`).
- Nhật ký nghiệp vụ (ai làm gì): `/quan-tri/nhat-ky/`.
- Tùy chọn: dịch vụ giám sát uptime bên ngoài để báo khi website không phản hồi.

## 9. Nâng cấp và khôi phục khi sự cố

Nâng cấp:
```bash
cd /srv/mamnon/app && sudo -u mamnon deploy/backup.sh       # sao lưu trước
sudo -u mamnon git pull
sudo -u mamnon /srv/mamnon/venv/bin/pip install -r requirements.txt
set -a; source .env; set +a
sudo -u mamnon -E /srv/mamnon/venv/bin/python manage.py migrate
sudo -u mamnon -E /srv/mamnon/venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart mamnon
```
Luôn thử bản mới trên staging trước.

Quay lui: `git checkout <phiên-bản-cũ>` → nếu migration đã chạy, khôi phục CSDL từ `pg-*.dump`:
```bash
sudo systemctl stop mamnon
sudo -u postgres dropdb mamnon && sudo -u postgres createdb -O mamnon mamnon
PGPASSWORD=... pg_restore -h 127.0.0.1 -U mamnon -d mamnon /srv/mamnon/backups/pg-YYYYMMDD-HHMMSS.dump
sudo systemctl start mamnon
```
Khôi phục từ bản ZIP ứng dụng (khi không có pg_dump, hoặc chuyển CSDL): tạo CSDL mới → `migrate` →
`python manage.py restore_data <tệp.zip> --yes` (lệnh từ chối chạy nếu CSDL đã có tài khoản).

## 10. Bật AI hỗ trợ (tùy chọn)

`pip install -r requirements-ai.txt`, đặt `AI_ENABLED=True`, `ANTHROPIC_API_KEY=...` trong `.env`, khởi động lại.
`AI_ALLOW_INTERNAL_DOCUMENTS` để `False` trừ khi lãnh đạo nhà trường đã cho phép gửi văn bản nội bộ ra dịch vụ bên ngoài.
Chi phí, điều khoản dữ liệu và tên model của nhà cung cấp có thể thay đổi — cần kiểm tra tại thời điểm bật.
