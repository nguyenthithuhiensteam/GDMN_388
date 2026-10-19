# Bảo mật, lưu giữ dữ liệu và xử lý sự cố

## 1. Biện pháp đã hiện thực trong mã nguồn
| Hạng mục | Cách làm | Vị trí |
|---|---|---|
| CSRF | Middleware CSRF của Django; mọi thao tác thay đổi dữ liệu dùng POST có token | `config/settings.py`, templates |
| Kiểm tra quyền phía máy chủ | `require_perm`, `ModulePermissionMixin`, kiểm tra theo đối tượng, queryset `for_user()` | `apps/core/permissions_mixins.py`, `apps/*/views*.py` |
| Chống tự nâng quyền | Form không cho sửa vai trò/trạng thái của chính mình; chỉ Quản trị gán vai trò Quản trị | `apps/accounts/forms.py`, `views.py` |
| Đăng nhập | Khóa tạm sau `LOGIN_MAX_FAILURES` lần sai (theo tên đăng nhập và theo IP); mật khẩu ≥ 10 ký tự + kiểm tra mật khẩu phổ biến; buộc đổi mật khẩu tạm | `apps/accounts/forms.py` |
| Phiên | Cookie HttpOnly, SameSite=Lax, Secure (production); hết hạn 8 giờ; xem và thu hồi phiên; thu hồi toàn bộ khi đổi mật khẩu/khóa tài khoản | `apps/accounts/middleware.py` |
| XSS | Tự động escape của template; HTML bài viết làm sạch bằng `bleach` (whitelist) | `apps/core/sanitize.py` |
| Tệp tải lên | Giới hạn phần mở rộng + dung lượng + kiểm tra chữ ký nội dung (magic bytes) + Pillow verify ảnh; tên tệp ngẫu nhiên; tệp nội bộ ngoài thư mục web, tải qua view có kiểm tra quyền, `Content-Disposition: attachment`, `nosniff` | `apps/core/validators.py`, `storage.py`, `downloads.py` |
| Không thực thi tệp | Nginx chặn đuôi thực thi trong `/media/`, CSP chặt cho tệp tĩnh tải lên; `/_protected/` là `internal` | `deploy/nginx.conf` |
| Riêng tư ảnh trẻ | Ảnh album lưu kho nội bộ; chỉ phục vụ công khai khi đã xác nhận quyền + album xuất bản; xóa EXIF | `apps/content` |
| Lộ thông tin lỗi | `DEBUG=False` ở production; trang lỗi 403/404/500 chung | `templates/errors/` |
| Bí mật | Biến môi trường/`.env` (không commit); production từ chối chạy khi thiếu `DJANGO_SECRET_KEY` | `config/settings.py`, `.gitignore` |
| HTTPS | `SECURE_SSL_REDIRECT`, HSTS, cookie Secure, `SECURE_PROXY_SSL_HEADER` | `config/settings.py` |
| Open redirect | Liên kết nhắc việc kiểm tra cùng host | `apps/core/views_admin.py` |
| Excel injection | Ô bắt đầu bằng `= + - @` được thêm dấu `'` | `apps/reports/exporters.py` |
| Spam liên hệ | Honeypot, thời gian điền tối thiểu (token ký), giới hạn 5 lần/giờ/IP, cần đồng ý sử dụng thông tin | `apps/core/forms.py`, `views_public.py` |
| Nhật ký | Đăng nhập/đăng xuất, tạo/sửa/xóa, chuyển trạng thái, tải xuống, xuất dữ liệu, thay đổi quyền/cấu hình | `apps/core/audit.py` |
| AI | Mặc định tắt; che email/SĐT/số định danh trước khi gửi; không gửi văn bản nội bộ trừ khi bật `AI_ALLOW_INTERNAL_DOCUMENTS` và văn bản ở phạm vi "Toàn bộ"; chỉ lấy văn bản người dùng được xem | `apps/ai_assistant/` |

Hạn chế cần biết: bộ đếm giới hạn liên hệ dùng bộ nhớ đệm trong tiến trình (LocMem) — với nhiều worker Gunicorn, giới hạn là theo từng worker. Nếu cần chặt hơn, cấu hình Redis/Memcached làm `CACHES`. Bộ lọc che thông tin định danh cho AI dựa trên mẫu (regex), không nhận diện được mọi dữ liệu nhạy cảm.

## 2. Chính sách lưu giữ và xóa dữ liệu (mặc định, cấu hình bằng biến môi trường)
| Dữ liệu | Thời hạn mặc định | Lệnh |
|---|---|---|
| Lịch sử đăng nhập | 180 ngày | `cleanup_data` |
| Nhắc việc đã đọc | 180 ngày | `cleanup_data` |
| Liên hệ đã xử lý | 730 ngày | `cleanup_data` |
| Nhật ký hệ thống | 1825 ngày (5 năm) | `cleanup_data` |
| Phiên hết hạn | ngay khi hết hạn | `cleanup_data` |
| Bản sao lưu | `BACKUP_KEEP` bản gần nhất | `backup_data` |
| Văn bản, kế hoạch, minh chứng | không tự xóa (hồ sơ nghiệp vụ) | xóa thủ công theo quy định lưu trữ |

Các thời hạn trên là **mặc định kỹ thuật**, không phải tư vấn pháp lý. Nhà trường cần đối chiếu quy định hiện hành về lưu trữ hồ sơ và bảo vệ dữ liệu cá nhân, rồi điều chỉnh. Dữ liệu cá nhân của trẻ em không được thu thập trong phiên bản này.

## 3. Quy trình xử lý khi tài khoản hoặc dữ liệu bị xâm phạm
1. **Khoanh vùng (trong vài giờ đầu)**
   - Khóa tài khoản nghi bị chiếm (`/quan-tri/tai-khoan/` → Khóa) — phiên của tài khoản bị thu hồi ngay.
   - Nếu nghi tài khoản Quản trị bị lộ: đổi `DJANGO_SECRET_KEY` trong `.env` và khởi động lại (mọi phiên và liên kết đặt lại mật khẩu đều mất hiệu lực), đổi mật khẩu CSDL, SMTP, khóa API AI.
   - Nếu nghi máy chủ bị xâm nhập: ngắt Nginx (`systemctl stop nginx`), chụp/giữ nguyên ổ đĩa để điều tra, không xóa log.
2. **Điều tra**: xem `/quan-tri/nhat-ky/` (lọc theo thời gian, người dùng, IP), `logs/app.log`, log Nginx, `journalctl`; xác định dữ liệu đã bị xem/tải/xuất (các thao tác `download`, `export` đều có nhật ký).
3. **Khắc phục**: vá lỗ hổng/cập nhật gói; đặt lại mật khẩu (tài khoản liên quan được buộc đổi mật khẩu); nếu dữ liệu bị sửa/xóa, khôi phục từ bản sao lưu đã kiểm tra (`verify_backup --restore-test`).
4. **Thông báo**: báo lãnh đạo nhà trường; nếu có dữ liệu cá nhân bị lộ, thực hiện nghĩa vụ thông báo theo quy định pháp luật hiện hành về bảo vệ dữ liệu cá nhân (cần xác minh văn bản và thời hạn áp dụng tại thời điểm xảy ra) và thông báo cho người bị ảnh hưởng khi cần.
5. **Rút kinh nghiệm**: ghi biên bản sự cố, cập nhật quy trình và ma trận quyền.

## 4. Danh sách kiểm tra định kỳ
- Hằng ngày (tự động): sao lưu + kiểm tra toàn vẹn, nhắc việc, dọn dữ liệu.
- Hằng tháng: `verify_backup --restore-test`; rà soát tài khoản không còn dùng; cập nhật hệ điều hành.
- Hằng quý: rà soát ma trận quyền và nhật ký xuất dữ liệu; khôi phục thử đầy đủ trên staging; `pip list --outdated` và cập nhật bản vá bảo mật Django.
