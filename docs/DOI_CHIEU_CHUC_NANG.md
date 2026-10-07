# Đối chiếu kế hoạch Taxi Booking và giao diện minh họa

Tài liệu đầu vào: `Ke_hoach_va_chuc_nang_Taxi_Booking.docx` và ba ảnh khách/tài xế/admin. Công nghệ Node.js/Express/Bootstrap trong tài liệu là phương án dự kiến; bản đang chạy tiếp tục dùng Flask + HTML/CSS/JS để giữ dữ liệu và hệ thống triển khai hiện có. Lịch 4 tuần, nhóm 4 người là kế hoạch tham khảo, không phải thao tác tự động trên repository.

## Ba giao diện

| Vai trò | Màn hình chính | Các trang phụ |
|---|---|---|
| Khách | Thanh menu ngang, form đặt chuyến, chọn xe 4/7 chỗ, giá/tiền mặt/chuyển khoản, bản đồ mô phỏng | Lịch sử, chi tiết/timeline, hồ sơ, đổi mật khẩu, phản ánh |
| Tài xế | Sidebar, bật/tắt nhận chuyến, KPI hôm nay, thẻ chuyến chờ, hồ sơ/xe | Tổng quan/chuyến đang chạy, lịch sử, thu nhập theo tháng, hồ sơ/yêu cầu đổi xe |
| Admin | Sidebar, KPI, biểu đồ chuyến 7 ngày, trạng thái tài xế, bảng chuyến gần đây | Chuyến, khách, tài xế, phương tiện, báo cáo, cài đặt, tài khoản, duyệt hồ sơ, phản ánh/đánh giá, audit |

Ảnh thực tế được lưu tại `docs/screenshots/customer.png`, `driver.png`, `admin.png`, `driver-mobile.png`. Số liệu lấy từ database hiện có, không gán cố định các con số trong ảnh mẫu.

## Chức năng trong tài liệu

| Nhóm | Chức năng | Cách thực hiện |
|---|---|---|
| Chung | Đăng ký/đăng nhập/đăng xuất | Khách tự đăng ký; admin/tài xế được tạo bởi admin; cookie HttpOnly, CSRF, phân quyền server |
| Chung | Hồ sơ và đổi mật khẩu | Menu Tài khoản/Hồ sơ; đổi mật khẩu kiểm tra mật khẩu cũ và thu hồi mọi phiên |
| Chung mở rộng | Quên mật khẩu qua email | Form email + username; token hash, hết hạn 30 phút, dùng một lần. Cần cấu hình SMTP; khi chưa cấu hình, hướng dẫn liên hệ admin, không giả vờ đã gửi thư |
| Khách | Đặt, loại xe, giá dự kiến, tiền mặt/chuyển khoản | Form đặt xe; giá lưu cùng bản sao biểu giá lúc đặt |
| Khách | Theo dõi trạng thái | Thẻ chuyến hiện tại, chi tiết/timeline; làm mới tự động 15 giây khi không đang nhập form hoặc mở dialog |
| Khách | Thông tin tài xế | Tên, SĐT, mẫu xe, biển số, số chỗ trong chi tiết chuyến |
| Khách | Hủy | Chỉ chuyến của mình còn `pending`; nhận rồi không được tự hủy |
| Khách | Lịch sử | Tìm/lọc/phân trang, thời gian, hành trình, giá và trạng thái |
| Khách mở rộng | Đánh giá | 1–5 sao và nhận xét, chỉ chuyến của mình đã hoàn thành, một đánh giá/chuyến |
| Khách mở rộng | Phản ánh | Gửi từ chi tiết, xem kết quả trong tài khoản; admin xử lý |
| Tài xế | Hồ sơ/giấy phép/phương tiện | Hồ sơ cá nhân; xe/giấy phép do admin quản lý hoặc duyệt yêu cầu |
| Tài xế | Bật/tắt nhận chuyến | `available`/`offline`; không được tắt khi đang bận |
| Tài xế | Chờ/nhận chuyến | Chỉ xe đúng số chỗ, đang hoạt động, tài xế sẵn sàng. Hai tài xế tranh một chuyến chỉ một thành công |
| Tài xế | Liên hệ khách/chi tiết | Chỉ chuyến đã được giao cho mình; hàng chờ chưa tiết lộ SĐT khách |
| Tài xế | Bắt đầu/hoàn thành | Chỉ đúng chủ sở hữu, đúng thứ tự; giải phóng tài xế khi kết thúc |
| Tài xế | Lịch sử/thu nhập | Lịch sử riêng, KPI hôm nay và thu nhập theo ngày/tháng hoàn thành |
| Tài xế mở rộng | Đã đến | Nút trong chuyến đã nhận; khách thấy thông báo khi làm mới |
| Admin | Khách/tài xế/tài khoản | Tìm, thêm/sửa, khóa/mở, reset mật khẩu; lưu trữ/khôi phục giữ lịch sử |
| Admin | Phương tiện | Biển số/mẫu xe/số chỗ/tài xế phụ trách, kích hoạt/ngừng. Không đổi khi tài xế bận |
| Admin | Chuyến và thống kê | Bộ lọc khách/tài xế/ngày/trạng thái, chi tiết/sửa khi chờ, điều phối lại, báo cáo và CSV |
| Admin mở rộng | Giá cước | Cài đặt cho xe 4/7 chỗ; chuyến đã đặt giữ nguyên biểu giá và giá |
| Admin mở rộng | Duyệt hồ sơ | Xem giấy phép/xe đề xuất, duyệt hoặc từ chối với ghi chú |
| Admin mở rộng | Đánh giá/phản ánh | Xem nhận xét, xử lý phản ánh với trạng thái và kết quả |

## Trạng thái và dữ liệu

Tên trong kế hoạch tương ứng với API hiện có: `PENDING → pending`, `ACCEPTED → assigned`, `IN_PROGRESS → ongoing`, `COMPLETED → completed`, `CANCELLED → cancelled`.

Các bảng bổ sung: `vehicles`, `fares`, `trip_status_history`, `reviews`, `complaints`, `driver_requests`, `password_resets`. Chuyến có các mốc accepted/arrived/started/completed/cancelled và bản sao giá/xe. Migration giữ dữ liệu cũ; với chuyến có từ trước khi bổ sung timeline, chỉ ghi nhận trạng thái đã lưu, không tự dựng lịch sử thay đổi chưa được ghi lại.

## Phạm vi mô phỏng và vận hành

- Bản đồ SVG và ảnh xe/avatar là minh họa cục bộ, không gọi dịch vụ bản đồ hay theo dõi GPS. Điểm đón/đến là văn bản; khoảng cách do người dùng nhập mẫu.
- Tiền mặt và chuyển khoản QR: lưu lựa chọn, tạo QR cục bộ, admin đối soát; không tự chuyển tiền hoặc tự xác nhận ngân hàng.
- Không có SMS/thông báo đẩy hoặc tự động ghép tài xế; tài xế nhận hoặc admin phân công.
- PostgreSQL, pgAdmin, Nginx, Prometheus/Grafana, Loki/Alloy và CI hiện có tiếp tục hoạt động. Các đề xuất exporter container/Nginx/PostgreSQL và diễn tập backup/restore trong phần vận hành của tài liệu không được xem là chức năng giao diện đã hoàn thành.

## Kiểm thử

`tests/smoke.py`: phân quyền cơ bản, sở hữu, CSRF, vòng đời, tài xế nhận nhiều chuyến.

`tests/admin.py`: hồ sơ/tài khoản, thu hồi phiên, điều phối, bộ lọc, CSV, báo cáo, audit.

`tests/features.py`: hai tài xế tranh chuyến, sẵn sàng, đúng loại xe, timeline/mốc thời gian, hồ sơ/password, giá snapshot, đánh giá/phản ánh và duyệt xe.

`tests/password_reset.py`: tích hợp database và Flask, SMTP giả lập không gửi thư, token hết hạn/dùng một lần, đổi mật khẩu và thu hồi phiên.

`tests/browser.cjs`: Chrome thực, các menu/dialog, chuỗi đặt→nhận→đến→bắt đầu→hoàn thành, giao diện mobile và ảnh minh chứng.

## Bổ sung theo yêu cầu mới

Ảnh đại diện tài xế từ thư viện và chuyển khoản QR tạo cục bộ đã được triển khai. Trạng thái thành công/thất bại do admin đối soát, chưa kết nối webhook ngân hàng. Xem [hướng dẫn](ANH_VA_THANH_TOAN.md).

## Bổ sung bản đồ thực tế

Giao diện khách và tài xế đã thay bản đồ minh họa bằng Leaflet/OpenStreetMap, tìm địa điểm và tuyến ô tô thật. GPS tài xế chia sẻ tự nguyện, khách chỉ xem chuyến của mình đang phục vụ. Các ghi chú mô phỏng ở phần cũ áp dụng cho dữ liệu lịch sử/admin đặt thủ công. Chi tiết: [hướng dẫn bản đồ](BAN_DO_THUC_TE.md).
