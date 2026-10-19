# Trạng thái chức năng, hạn chế và công việc còn lại

Cập nhật: 19/10/2026. "Đã hoàn thành" nghĩa là đã có mã chạy được và (nếu ghi) có kiểm thử tự động đã chạy đạt trong môi trường phát triển
(SQLite, Python 3.13, Django 5.2). **Chưa** kiểm thử trên PostgreSQL thật, chưa triển khai lên máy chủ/tên miền nào.

## Theo giai đoạn

| Giai đoạn | Nội dung | Trạng thái |
|---|---|---|
| 1 | Phân tích, kiến trúc, sitemap, mô hình dữ liệu, ma trận quyền | Hoàn thành — `docs/01_PHAN_TICH_THIET_KE.md` |
| 2 | Nền tảng, đăng nhập, người dùng, vai trò, dashboard | Hoàn thành, có kiểm thử |
| 3 | Website công khai, quản trị nội dung, quy trình duyệt | Hoàn thành, có kiểm thử |
| 4 | Văn bản, kế hoạch (phiên bản, góp ý, duyệt, xuất Word/PDF), nhiệm vụ, minh chứng | Hoàn thành, có kiểm thử |
| 5 | Báo cáo + xuất Excel/PDF, sao lưu/kiểm tra/khôi phục, AI tùy chọn | Hoàn thành; AI chỉ kiểm thử với dịch vụ giả lập (mock) |
| 6 | Kiểm thử bảo mật/phân quyền, giao diện desktop/điện thoại, cấu hình triển khai | Hoàn thành trong môi trường phát triển; chưa triển khai thật |

## Chi tiết đã hoàn thành
- Đăng nhập/đăng xuất (POST), đổi mật khẩu, khôi phục mật khẩu qua email, buộc đổi mật khẩu tạm, khóa/mở khóa, khóa tạm khi sai nhiều lần, quản lý và thu hồi phiên, hồ sơ cá nhân.
- 7 vai trò, ma trận quyền 18 chức năng với 9 loại thao tác (xem, tạo, sửa, xóa, duyệt, xuất bản, tải xuống, xuất dữ liệu, sử dụng) cấu hình được qua giao diện; giới hạn theo điểm trường/tổ/lớp/người tạo; kiểm thử truy cập trực tiếp URL cho mọi vai trò.
- Dashboard theo quyền: thẻ thống kê, cảnh báo cần xử lý, việc sắp đến hạn, văn bản mới, nhắc việc, hoạt động gần đây; banner cảnh báo khi có dữ liệu mẫu.
- Nội dung: tin tức + danh mục, thông báo (loại, thời hạn, đính kèm, ghim), trang giới thiệu, đội ngũ (cờ đồng ý công khai), album ảnh/video (tải nhiều ảnh, tối ưu, xóa EXIF, xác nhận quyền hình ảnh), tài liệu tải xuống, công khai giáo dục (phiên bản, hạn rà soát, xác nhận người có thẩm quyền). Quy trình nháp/duyệt/xuất bản/ẩn/lưu trữ, xem trước, nhật ký chỉnh sửa, tìm kiếm, lọc, phân trang.
- Website công khai đầy đủ các trang theo yêu cầu, tìm kiếm, biểu mẫu liên hệ chống spam, bản đồ nhúng, giao diện đáp ứng.
- Văn bản: số/ký hiệu/ngày/cơ quan/loại/lĩnh vực/trích yếu/tệp/người phụ trách/trạng thái/hạn/phạm vi truy cập; tìm kiếm, lọc theo khoảng ngày, xuất Excel.
- Kế hoạch: 6 cấp, năm học, cây kế hoạch, dự thảo/góp ý/trình duyệt/duyệt/ban hành/lưu trữ, phiên bản, góp ý, xuất Word/PDF theo mẫu cấu hình.
- Nhiệm vụ: giao cá nhân/tổ/điểm trường, trạng thái + quá hạn, minh chứng, nhận xét, lịch sử, theo dõi tiến độ, nhắc việc giao diện + email (tùy cấu hình), xuất Excel.
- Minh chứng: danh mục, gắn kế hoạch/nhiệm vụ/tiêu chí/báo cáo, phiên bản tệp không ghi đè, phạm vi truy cập, xuất danh mục.
- Báo cáo: theo thời gian/tổ/điểm trường, chỉ dữ liệu được phép, xuất Excel/PDF, ghi nhật ký xuất.
- Cấu hình: thông tin trường, logo, banner, màu, liên hệ, bản đồ, quy trình duyệt; xem cấu hình máy chủ (chỉ đọc), danh sách bản sao lưu; nhật ký hệ thống + xuất Excel.
- Lệnh: `create_admin`, `seed_demo [--remove]`, `backup_data`, `verify_backup [--restore-test]`, `restore_data --yes`, `send_reminders`, `cleanup_data`.
- AI: gợi ý tin bài, soạn kế hoạch, tóm tắt, gợi ý minh chứng, dàn ý báo cáo, tìm kiếm nội bộ theo quyền (không cần AI).
- Triển khai: `.env.example`, Gunicorn, systemd service + timer, Nginx (HTTPS, X-Accel cho tệp nội bộ), script sao lưu.

## Chưa hoàn thành / ngoài phạm vi phiên bản này
- Chưa triển khai thật lên VPS/tên miền; chưa kiểm thử trên PostgreSQL (mã dùng ORM chuẩn, kỳ vọng tương thích nhưng **chưa xác minh**).
- Trình soạn thảo văn bản giàu định dạng (WYSIWYG) chưa tích hợp; hiện nhập HTML cơ bản trong ô văn bản (được làm sạch).
- Chưa có tải video lên máy chủ (chỉ liên kết YouTube) và chưa có lưu trữ đối tượng (S3…) — có thể thay `STORAGES` khi cần.
- Chưa có xác thực hai yếu tố (2FA), chưa có CAPTCHA bên thứ ba cho biểu mẫu liên hệ.
- Thanh toán/khoản thu, hồ sơ trẻ, điểm danh, thực đơn: không thuộc phạm vi (không thu thập dữ liệu trẻ).
- Danh sách mục công khai giáo dục chỉ là khung gợi ý; **chưa đối chiếu** với văn bản quy phạm hiện hành.
- Chức năng AI chưa được gọi thử với dịch vụ thật (chỉ kiểm thử bằng mock); chất lượng nội dung AI chưa được đánh giá.
- Kiểm tra khả năng tiếp cận mới ở mức cơ bản (nhãn form, phím tắt bỏ qua điều hướng, aria, focus) — chưa kiểm định bằng công cụ chuyên dụng/trình đọc màn hình.
- Kiểm tra giao diện đã làm bằng trình duyệt Chromium headless ở 1366px và 390px cho một số trang; chưa thử Safari/iOS, Firefox.

## Hạn chế kỹ thuật đã biết
- Giới hạn tần suất liên hệ dùng cache trong tiến trình (xem `04_BAO_MAT_VA_SU_CO.md`).
- Phục vụ tệp nội bộ qua Django khi không có Nginx X-Accel sẽ chậm với tệp lớn.
- Bản sao lưu JSON (`backup_data`) phù hợp quy mô một trường; dữ liệu lớn nên dựa vào `pg_dump`.
- Tìm kiếm dùng `icontains` (không phải tìm kiếm toàn văn); với PostgreSQL có thể nâng cấp lên full-text search.
