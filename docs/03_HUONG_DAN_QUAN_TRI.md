# Hướng dẫn quản trị và phân quyền

## 1. Khởi tạo lần đầu (Quản trị hệ thống)
1. Đăng nhập `/tai-khoan/dang-nhap/` bằng tài khoản tạo từ `create_admin`.
2. **Cấu hình** (`/quan-tri/cau-hinh/`): tên trường, cơ quan chủ quản, logo, banner, màu, địa chỉ, điện thoại, email, tên miền, bản đồ (URL nhúng Google Maps), nội dung trang chủ, bật/tắt "bắt buộc duyệt trước khi xuất bản".
3. **Cơ cấu tổ chức** (`/quan-tri/to-chuc/nam-hoc/`): năm học (đánh dấu hiện hành), điểm trường, tổ chuyên môn, lớp, danh mục chuyên môn (loại văn bản, lĩnh vực, cơ quan ban hành).
4. **Tài khoản** (`/quan-tri/tai-khoan/`): tạo tài khoản, chọn vai trò, điểm trường, tổ, lớp phụ trách, đặt mật khẩu tạm thời. Người dùng buộc phải đổi mật khẩu khi đăng nhập lần đầu. Gửi mật khẩu tạm qua kênh riêng (gặp trực tiếp/điện thoại), không gửi kèm tên đăng nhập trong cùng tin nhắn công khai.
5. **Phân quyền** (`/quan-tri/tai-khoan/phan-quyen/`): xem/chỉnh ma trận quyền. Chỉ Quản trị hệ thống được lưu thay đổi; thay đổi được ghi nhật ký.
6. Rà soát **Mục công khai giáo dục** (`/quan-tri/noi-dung/muc-cong-khai/`) theo quy định hiện hành; ghi căn cứ đã kiểm tra.
7. Xóa dữ liệu mẫu nếu đã tạo: `python manage.py seed_demo --remove`.

## 2. Vai trò và nguyên tắc
- Mỗi tài khoản có **một vai trò**; người dùng không thể tự đổi vai trò/trạng thái của mình. Chỉ Quản trị hệ thống gán được vai trò Quản trị hệ thống và sửa tài khoản Quản trị.
- Khi cán bộ nghỉ/chuyển công tác: **Khóa** tài khoản (không xóa) để giữ lịch sử; mọi phiên đăng nhập của họ bị thu hồi ngay.
- Phân quyền tối thiểu: chỉ bật quyền cần cho công việc. Quyền "Xuất dữ liệu" và "Tải xuống" cần cân nhắc vì dữ liệu rời khỏi hệ thống.

## 3. Quy trình nội dung website
Nháp → **Gửi duyệt** (người soạn) → **Phê duyệt**/Trả lại (người có quyền duyệt) → **Xuất bản** → Ẩn / Lưu trữ / Khôi phục.
- Nút "Xem trước" hiển thị nội dung chưa công khai bằng giao diện website (chỉ người có quyền).
- Tin có ảnh đại diện phải xác nhận quyền sử dụng ảnh trước khi xuất bản.
- **Album ảnh**: ảnh tải lên ở trạng thái "Chưa kiểm tra quyền". Người có quyền duyệt album phải xác nhận "Được phép công khai" kèm căn cứ (ví dụ phiếu đồng ý của cha mẹ trẻ). Ảnh chỉ hiển thị công khai khi album đã xuất bản, phạm vi Công khai và ảnh đã được xác nhận. Không ghi họ tên trẻ trong chú thích. Ảnh được thu nhỏ và xóa EXIF (có thể chứa vị trí GPS).
- **Công khai giáo dục**: mỗi lần sửa nội dung/tệp tạo một phiên bản lịch sử. Phải có người có thẩm quyền bấm "xác nhận đã kiểm tra" thì mới xuất bản được; sửa nội dung sau đó sẽ tự hủy xác nhận. Dashboard và lệnh `send_reminders` nhắc hạn rà soát.

## 4. Văn bản
- Phạm vi truy cập: Toàn bộ / Lãnh đạo và văn phòng / Chỉ người được chỉ định. Người tạo, người phụ trách luôn xem được.
- Tìm kiếm theo số, ký hiệu, trích yếu, nội dung; lọc loại sổ, loại văn bản, lĩnh vực, trạng thái, khoảng ngày (dd/mm/yyyy).
- Tải tệp và xuất Excel đều được ghi nhật ký.

## 5. Kế hoạch giáo dục
Dự thảo → Gửi lấy góp ý → Trình duyệt → Phê duyệt → **Ban hành chính thức** → Lưu trữ.
- Mỗi lần lưu/chuyển trạng thái tạo một **phiên bản**; tệp của phiên bản cũ vẫn tải được.
- Chỉ sửa được ở trạng thái Dự thảo/Đang góp ý. Người duyệt có thể "Trả lại chỉnh sửa".
- Tổ trưởng duyệt kế hoạch tổ/lớp/chủ đề/tuần/hoạt động của tổ mình; kế hoạch cấp trường do Hiệu trưởng/Phó Hiệu trưởng duyệt.
- Xuất Word/PDF theo **Mẫu xuất kế hoạch** (phần đầu, chức danh ký, nơi nhận); bản chưa ban hành được in nhãn DỰ THẢO/ĐÃ DUYỆT.

## 6. Nhiệm vụ
- Giao cho cá nhân, tổ hoặc điểm trường; người nhận được nhắc việc (và email nếu bật).
- Người thực hiện: Chưa thực hiện → Đang thực hiện → Chờ xác nhận (đính kèm minh chứng). Người giao/lãnh đạo/tổ trưởng xác nhận **Hoàn thành**. "Quá hạn" được tính tự động khi quá thời hạn mà chưa hoàn thành.

## 7. Minh chứng
- Danh mục minh chứng (mã/tiêu chí) do lãnh đạo/văn phòng quản lý.
- Mỗi lần tải tệp tạo phiên bản mới, **không ghi đè**. Gắn với kế hoạch, nhiệm vụ, tiêu chí, báo cáo. Xuất danh mục ra Excel.

## 8. Báo cáo, nhật ký, sao lưu
- Báo cáo (`/quan-tri/bao-cao/`): số liệu thật, lọc theo thời gian/tổ/điểm trường, chỉ trong phạm vi quyền; xuất Excel/PDF (ghi nhật ký).
- Nhật ký hệ thống: ai, lúc nào, thao tác gì, trên đối tượng nào, IP.
- Sao lưu/khôi phục: xem `02_CAI_DAT_VA_TRIEN_KHAI.md` mục 7, 9.

## 9. AI hỗ trợ
Chỉ dùng khi máy chủ đã bật. Kết quả luôn là **bản nháp**; người dùng phải tự kiểm tra, sửa, lưu và đưa qua quy trình duyệt. Không nhập thông tin cá nhân của trẻ. Tìm kiếm tài liệu nội bộ chạy trên máy chủ của trường và chỉ trả về tài liệu bạn được phép xem.
