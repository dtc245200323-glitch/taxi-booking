# Báo cáo đề 22: Hệ thống đặt xe

## 1. Mục tiêu

Xây dựng ứng dụng web phục vụ nhân viên điều phối: quản lý khách hàng, tài xế, tạo và theo dõi chuyến đi. Triển khai database và công cụ quản trị, reverse proxy, giám sát metrics và log bằng Docker Compose.

## 2. Công nghệ

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| Frontend | HTML, CSS, JavaScript | Giao diện tiếng Việt responsive |
| Backend | Python Flask, Gunicorn | REST API và nghiệp vụ |
| Database | PostgreSQL 16 | Lưu khách, tài xế, chuyến đi |
| Database UI | pgAdmin | Xem bảng và truy vấn SQL |
| Reverse proxy | Nginx | Chuyển tiếp request, giới hạn tốc độ |
| Metrics | Prometheus | Thu thập số request, status, độ trễ |
| Dashboard | Grafana | Hiển thị metrics và log |
| Log | Alloy + Loki | Thu thập và truy vấn log Nginx |
| CI | GitHub Actions | Build và test API trên push/PR |

## 3. Thiết kế cơ sở dữ liệu

- `customers(id, name, phone)`: số điện thoại duy nhất.
- `drivers(id, name, phone, plate, status)`: số điện thoại và biển số duy nhất; trạng thái available/busy.
- `trips(id, customer_id, driver_id, pickup, destination, distance, fare, status, created_at)`: khóa ngoại liên kết khách và tài xế.

Khách hàng 1–N chuyến; tài xế 1–N chuyến. Unique partial index đảm bảo tài xế chỉ có một chuyến ở trạng thái assigned/ongoing. Check constraints giới hạn trạng thái, khoảng cách và cước. Dùng transaction và row lock khi phân công/cập nhật.

## 4. Chức năng

1. Thêm và xem khách hàng, tài xế.
2. Tạo chuyến từ điểm đón, điểm đến, khoảng cách và khách hàng.
3. Tính cước theo công thức 15.000 + 12.000 × km.
4. Phân công tài xế sẵn sàng và theo dõi vòng đời chuyến.
5. Hủy trước khi di chuyển; giải phóng tài xế khi hủy/hoàn thành.
6. Thống kê tổng chuyến, chuyến hoạt động, hoàn thành và doanh thu.
7. Admin sửa, lưu trữ/khôi phục hồ sơ; thay đổi trạng thái tài xế sẵn sàng/đang nghỉ; quản lý khóa tài khoản và reset mật khẩu có thu hồi phiên.
8. Admin tạo thêm tài khoản quản trị hoặc gắn tài khoản vào hồ sơ cũ; hệ thống chặn tự khóa và khóa tài xế đang chạy chuyến.
9. Tra cứu chuyến theo tên, địa chỉ, mã, SĐT, biển số; lọc thời gian/trạng thái, phân trang, xem chi tiết, sửa chuyến pending và đổi tài xế assigned.
10. Báo cáo doanh thu theo ngày/tài xế, biểu đồ, CSV cho Excel và nhật ký thao tác quản trị.

## 5. Triển khai và hardening

Các container giao tiếp qua network riêng của Compose. PostgreSQL không công bố cổng ra host. Các giao diện chỉ bind localhost. API dùng phiên đăng nhập cookie HttpOnly/SameSite, mật khẩu hash scrypt, kiểm tra CSRF/Origin và phân quyền admin/tài xế/khách. Truy vấn SQL có tham số, giới hạn request body và rate limit ở Nginx. App chạy bằng user không phải root với filesystem read-only và capabilities bị loại bỏ. Các response thêm CSP và các header chống iframe/MIME sniffing.

Thông tin bí mật nằm trong `.env` được gitignore. Volume giữ dữ liệu database và giám sát sau khi dừng container. Prometheus truy cập `/metrics` trực tiếp qua mạng container; Nginx chặn endpoint này từ browser. Alloy chuyển log file Nginx đến Loki; Grafana được provision sẵn hai datasource và dashboard.

## 6. Kịch bản kiểm thử

`tests/smoke.py` kiểm tra cả ba vai trò, từ chối truy cập chuyến người khác, thống kê riêng, đăng ký không thể tự nâng quyền, CSRF, thu hồi phiên sau logout, khoảng cách âm/NaN, cước, trạng thái, tài xế bận và hai yêu cầu phân công đồng thời. Test tạo dữ liệu riêng bằng định danh ngẫu nhiên.

`tests/admin.py` kiểm tra sửa/lưu trữ/khôi phục hồ sơ, khóa và reset mật khẩu, chặn thao tác lên tài xế bận, điều phối lại, giữ lịch sử, tìm kiếm/phân trang, báo cáo/CSV và nhật ký. `tests/browser.cjs` kiểm tra giao diện bằng Chrome headless với ba vai trò.

## 7. Giới hạn và hướng phát triển

Ứng dụng có ba vai trò: admin quản lý toàn bộ và phân công; tài xế chỉ xem/bắt đầu/hoàn thành chuyến được giao; khách tự đăng ký và đặt/theo dõi/hủy chuyến của mình. Bảng `users` liên kết duy nhất với hồ sơ khách hoặc tài xế, bảng `sessions` lưu hash token và thời hạn phiên 24 giờ. Migration bổ sung bảng mà không xóa chuyến cũ.

Khoảng cách nhập thủ công, chưa có GPS/bản đồ hay thanh toán. Hướng phát triển: HTTPS, khách/tài xế tự đổi hoặc quên mật khẩu, tích hợp bản đồ và định vị tài xế, thanh toán, backup tự động, cảnh báo vận hành và log rotation.

## 8. Minh chứng khi nộp

Chụp giao diện đặt chuyến, các trạng thái chuyến, bảng dữ liệu trong pgAdmin, `docker compose ps`, dashboard Grafana, log Loki và kết quả workflow GitHub Actions. Điền URL repository thật sau khi push theo hướng dẫn README.
