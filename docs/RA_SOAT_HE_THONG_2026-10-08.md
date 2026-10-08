# Rà soát Hệ thống đặt xe — 08/10/2026

## Kết luận

Đã có đủ các nhóm chức năng cốt lõi theo tài liệu đối chiếu của dự án. Không bổ sung chức năng mới sau lần rà soát này. Kết luận áp dụng cho phạm vi phần mềm hiện tại; không đồng nghĩa đã tích hợp mọi dịch vụ của một nền tảng đặt xe thương mại.

## Phạm vi đã kiểm tra

| Vai trò | Chức năng hiện có |
|---|---|
| Khách hàng | Đăng ký, đăng nhập bằng tên/SĐT/email, hồ sơ và ảnh đại diện, đổi/quên mật khẩu; đặt xe máy/4/7 chỗ; điểm đón/đến, bản đồ, tuyến đường và giá dự kiến; mã ưu đãi; theo dõi, hủy khi chờ, lịch sử; tiền mặt/QR; đánh giá, phản ánh và chat hỗ trợ |
| Tài xế | Sẵn sàng/ngừng nhận chuyến; hàng chờ theo loại xe; nhận, báo đã đến, bắt đầu, hoàn thành; liên hệ khách sau nhận; GPS; lịch sử, thu nhập; hồ sơ, yêu cầu đổi giấy phép/xe và hỗ trợ admin |
| Quản trị | Quản lý khách, tài xế, tài khoản và phương tiện; khóa/mở, lưu trữ/khôi phục; điều phối chuyến; cấu hình giá, ngân hàng, ưu đãi và ảnh quảng cáo; đối soát thanh toán; duyệt hồ sơ; xử lý phản ánh/đánh giá; thống kê, báo cáo, CSV, nhật ký |

## Bằng chứng kiểm tra

16 bộ kiểm tra hiện có đã chạy đạt:

- `smoke`, `admin`, `features`: phân quyền, sở hữu, CRUD, vòng đời chuyến, tranh nhận chuyến, điều phối, báo cáo, CSV, giá lưu tại thời điểm đặt, phản ánh và duyệt xe.
- `payment_media`, `qr_payload`, `bank_accounts`: ảnh đại diện, QR, số tiền/tài khoản ngân hàng, thử lại thanh toán, đối soát đồng thời và quyền truy cập.
- `map_features`, `promotions`, `saved_promotions`: tìm địa điểm/tuyến, quyền GPS, xử lý lỗi nhà cung cấp, xe máy, giới hạn mã giảm giá và lưu ưu đãi/ảnh.
- `password_reset`, `landing_auth`, `customer_profile`, `admin_profile`, `driver_rating`: đăng nhập, mật khẩu, hồ sơ, ảnh, kiểm tra dữ liệu và đánh giá.
- `support`, `chat`: chat hai chiều, quyền từng khách/tài xế, trạng thái đã đọc, kết thúc/đánh giá hỗ trợ, chatbot và phương án trả lời khi AI không hoạt động.

Các bộ kiểm tra nghiệp vụ tạo dữ liệu được chạy trên database sao chép riêng `taxi_audit_20261008`; database này đã được dọn sau kiểm tra. Các bài kiểm tra hồ sơ/ngân hàng/hỗ trợ dùng rollback; bài kiểm tra lưu ưu đãi tự dọn dữ liệu thử nghiệm.

Chrome thực đã kiểm tra đăng nhập/đăng xuất, giao diện desktop, điện thoại 390px và màn hình 4K của ba vai trò; không tràn ngang toàn trang hoặc phát sinh lỗi JavaScript. Đã mở toàn bộ menu chính (12 admin, 5 tài xế, 5 khách) cùng các trang tài khoản/cài đặt bổ sung và xác nhận có nội dung. Việc mở menu không thay thế kiểm thử mọi thao tác trên từng màn hình; nghiệp vụ được kiểm tra riêng qua API.

Ảnh giao diện: `screenshots/audit-customer.png`, `screenshots/audit-driver.png`, `screenshots/audit-admin.png`.

## Giới hạn tích hợp

- Chuyển khoản QR đang được admin đối soát; chưa có webhook ngân hàng tự động xác nhận tiền.
- Khôi phục mật khẩu qua email cần SMTP. Kiểm tra lần này dùng SMTP giả lập, không gửi thư thật.
- Bản đồ/GPS đã có chức năng; kiểm thử API dùng dữ liệu nhà cung cấp giả lập. Chưa kiểm chứng theo dõi vị trí trên một chuyến chạy ngoài đường.
- Điều phối bằng tài xế nhận chuyến hoặc admin phân công; chưa có tự ghép tài xế, SMS hay thông báo đẩy.

Các tích hợp trên không thuộc phần chức năng cốt lõi còn thiếu trong tài liệu hiện tại và cần cấu hình/dịch vụ bên ngoài nếu triển khai vận hành thực tế.
