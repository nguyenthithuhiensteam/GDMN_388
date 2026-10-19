# Báo cáo Giai đoạn 1–2: rà soát, bổ sung, kết quả kiểm tra thực tế

Ngày thực hiện: 19/10/2026. Phát triển tiếp trên mã nguồn hiện có trong kho (không tạo dự án mới).
Môi trường kiểm tra: Linux, Python 3.13, Django 5.2.18, SQLite. **Chưa** chạy trên Windows thật, PostgreSQL thật hay máy chủ Internet.

## 1. Rà soát mã nguồn hiện có

| Hạng mục | Đã có trước đợt này | Thiếu / lỗi phát hiện |
|---|---|---|
| Đăng nhập, đăng xuất (POST), đổi/khôi phục mật khẩu, khóa tạm khi sai nhiều lần | Có | Khôi phục mật khẩu chưa giới hạn tần suất (có thể bị dùng để spam email) |
| Quản lý người dùng: tạo, sửa, khóa/mở khóa, xóa, mật khẩu tạm | Có | Có thể khóa/xóa/hạ quyền tài khoản Quản trị **cuối cùng**; quản lý chưa xem được phiên, lịch sử đăng nhập, quyền thực tế của từng người; chưa thu hồi phiên của người khác được |
| Phân quyền phía máy chủ (ma trận + phạm vi dữ liệu) | Có, có kiểm thử theo URL | Trang 403 trong khu quản trị dùng giao diện công khai; truy cập bị từ chối chưa được ghi nhật ký |
| Dashboard | Có, lọc theo quyền | Chưa có nội dung **riêng cho từng vai trò** (hàng chờ duyệt, tiến độ tổ, việc của tôi, tình trạng hệ thống) |
| Giao diện nền | 2 khung riêng (công khai, quản trị) | Lặp phần `<head>`/script; chưa có đường dẫn (breadcrumb) trong quản trị; logo không dùng chung |
| Kiểm tra mã | Chỉ có kiểm thử | Chưa có công cụ lint; ruff báo **120 lỗi** ở lần chạy đầu |
| Tài liệu | README cho Linux/macOS | Chưa hướng dẫn Windows; gói máy chủ (gunicorn, psycopg) lẫn trong requirements dùng cho Windows |

## 2. Đã bổ sung / sửa

**Tài khoản & phân quyền** (`apps/accounts/`)
- Chặn khóa, xóa, hạ vai trò tài khoản Quản trị hệ thống cuối cùng đang hoạt động (`is_last_active_admin`, kiểm tra ở form, view khóa, view xóa).
- `PasswordResetView` riêng: tối đa 5 yêu cầu/giờ/IP, vượt ngưỡng thì không gửi email nhưng vẫn trả cùng thông báo (không tiết lộ), ghi nhật ký.
- Trang chi tiết tài khoản `/quan-tri/tai-khoan/<id>/`: phạm vi, **quyền thực tế** tính từ ma trận, phiên đang hoạt động, 20 lần đăng nhập gần nhất, thao tác gần đây; nút **thu hồi mọi phiên** của người đó (cần quyền sửa tài khoản; Hiệu trưởng không thao tác được trên tài khoản Quản trị).
- Trang 403 trong khu quản trị dùng giao diện quản trị, ghi nhật ký `access_denied` (đường dẫn, phương thức).

**Dashboard theo vai trò** (`apps/core/dashboard.py`)

| Vai trò | Khối hiển thị |
|---|---|
| Quản trị hệ thống | Tình trạng hệ thống (đăng nhập thất bại 24h, tài khoản bị khóa, chưa đổi mật khẩu tạm, số quản trị viên, tuổi bản sao lưu gần nhất, cảnh báo DEBUG), đăng nhập thất bại gần đây, + các khối lãnh đạo |
| Hiệu trưởng, Phó HT | Hàng chờ phê duyệt (tin, thông báo, album, công khai, kế hoạch mình được duyệt), tiến độ nhiệm vụ theo tổ, văn bản cần xử lý, liên hệ mới |
| Văn phòng | Văn bản cần xử lý (theo hạn), liên hệ mới |
| Tổ trưởng | Tổ của tôi (thành viên, kế hoạch chờ duyệt, việc quá hạn trong tổ), hàng chờ duyệt **chỉ của tổ mình**, tiến độ tổ |
| Giáo viên, Nhân viên | Việc của tôi; (GV) kế hoạch tôi lập, nội dung tôi soạn chưa xuất bản kèm ghi chú duyệt |

Mỗi khối được kiểm tra quyền riêng và dữ liệu dùng truy vấn `for_user()` (chỉ trong phạm vi được phép).

**Giao diện nền thống nhất** (`templates/`)
- `base.html` chung: meta, CSS, màu theo cấu hình, favicon, liên kết "bỏ qua điều hướng", JS. `base_public.html` và `base_admin.html` kế thừa.
- `includes/brand.html` dùng chung logo (hoặc biểu tượng mặc định); breadcrumb trong khu quản trị; `body` có class `public`/`admin`.

**Kiểm tra mã & đóng gói**
- `ruff.toml` (quy tắc E, F, W, B, I, DJ, S): sửa 8 model thiếu `__str__`, biến vòng lặp thừa, import, thứ tự phương thức model, dòng quá dài; định dạng mã bằng `ruff format`.
- Tách `requirements-prod.txt` (gunicorn, psycopg) khỏi `requirements.txt`.

## 3. Kết quả kiểm tra (đã thực sự chạy)

| Kiểm tra | Lệnh | Kết quả |
|---|---|---|
| Lint | `ruff check .` | Lần đầu: 120 lỗi → sau sửa: **All checks passed!** |
| Định dạng | `ruff format --check .` | Không còn tệp cần định dạng |
| Django | `python manage.py check` | No issues |
| Migration | `makemigrations --check --dry-run` | No changes detected |
| Triển khai | `check --deploy` (DJANGO_ENV=production) | Còn 2 cảnh báo HSTS W005/W021 — cố ý để tùy chọn, xem tài liệu triển khai |
| Kiểm thử tự động | `python manage.py test` | **98/98 đạt** (trước đợt này: 76) |
| Cài đặt sạch | venv mới + `pip install -r requirements.txt` + `manage.py test` | 98/98 đạt |
| Trình duyệt | Chromium headless, 1366px và 390px, đăng nhập 3 vai trò | Đúng khối dashboard theo vai trò, không tràn ngang; lỗi console duy nhất là phản hồi 403 có chủ đích khi giáo viên mở trang Tài khoản |

22 kiểm thử mới:
- `apps/accounts/tests/test_security_roles.py`: quản trị viên cuối cùng, giới hạn khôi phục mật khẩu, CSRF ở đăng nhập/đăng xuất,
  đổi khóa phiên khi đăng nhập (chống session fixation), chống chuyển hướng ra ngoài sau đăng nhập, tài khoản bị khóa mất phiên ngay,
  không thu hồi được phiên của người khác (IDOR), lãnh đạo thu hồi phiên, **POST trực tiếp** của 5 vai trò không đủ quyền vào tạo/khóa/xóa
  tài khoản, ma trận quyền, cấu hình (dữ liệu không đổi), người chưa đăng nhập POST, trang 403 quản trị + nhật ký, trang chi tiết tài khoản.
- `apps/core/tests/test_dashboard_roles.py`: khối dashboard bắt buộc có/không được có cho 7 vai trò, phạm vi "việc của tôi",
  hàng chờ duyệt của tổ trưởng chỉ gồm tổ mình, tình trạng hệ thống, giao diện nền dùng chung.

## 4. Chưa thực hiện được và lý do
- **Triển khai lên Internet:** không có máy chủ (IP, SSH), tên miền, chứng chỉ, SMTP của nhà trường trong môi trường làm việc này.
  Mã nguồn và cấu hình triển khai đã sẵn sàng (`deploy/`, `docs/02_CAI_DAT_VA_TRIEN_KHAI.md`).
- **Chạy thử trên Windows:** môi trường làm việc là Linux; hướng dẫn Windows dựa trên quy trình chuẩn của Python/venv, cần người dùng chạy thử xác nhận.
- **PostgreSQL:** chưa chạy kiểm thử trên PostgreSQL thật.
- Khóa tạm theo tên đăng nhập có thể bị kẻ xấu lợi dụng để khóa tạm tài khoản người khác (đánh đổi đã biết của cơ chế chống dò mật khẩu);
  nếu cần có thể chuyển sang chỉ khóa theo IP hoặc thêm CAPTCHA.
