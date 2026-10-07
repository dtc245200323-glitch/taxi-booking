# Đối chiếu đề và hướng dẫn demo

| Tiêu chí | Kết quả trong dự án | Minh chứng |
|---|---|---|
| GitHub, README, 3 commit | Có Git cục bộ, commit theo 3 bước; chưa push vì thiếu repo/xác thực/MSSV | `git log --oneline`, README |
| Website + database + DB tool | Taxi Booking + PostgreSQL + pgAdmin | Website :8080, pgAdmin :5050, ảnh trong báo cáo |
| Reverse proxy | Nginx + security headers, rate limit | infra/nginx.conf; evidence/monitoring.json |
| Prometheus + Grafana | Metrics API/Nginx/PostgreSQL/container, 11 panel | Prometheus :9090/targets; Grafana :3000 |
| Loki + Promtail, LogQL | Promtail mặc định; ba query đã có dữ liệu | infra/promtail.yml; evidence/monitoring.json |
| Hardening | Non-root app, read-only, capabilities, isolation, DB DML role, private ports, CSRF | tests/hardening.py; evidence/hardening.json |
| Báo cáo ≥10 trang | Có Word/PDF, hình thực tế; chờ thông tin bìa | BAO_CAO_TAXI_BOOKING.docx/pdf |

## Thông tin cần bổ sung trước nộp

Điền trường, khoa, họ tên, MSSV, lớp, giảng viên và repo vào `docs/student.json`. Chạy lại `python docs/build_report.py`. Tác giả commit hiện là tên dự án tạm thời; cấu hình họ tên/email sinh viên cho các commit tiếp theo. Không tự nhận đã đăng ký tài khoản GitHub hay đã push.

1. Tạo tài khoản GitHub theo MSSV; xác thực email trên GitHub.
2. Tạo repo trống, ví dụ `MSSV-taxi-booking`, không thêm README tự động để tránh lịch sử khác nhánh.
3. Trong dự án, chạy `git remote add origin https://github.com/TAI_KHOAN/MSSV-taxi-booking.git` rồi `git push -u origin main`. Nếu origin đã tồn tại, kiểm tra `git remote -v` trước khi sửa.
4. Đăng nhập bằng Git Credential Manager khi Git yêu cầu; không gửi PAT vào chat hoặc lưu trong file.
5. Mở repo trên GitHub và kiểm tra README, source, infra, ba commit, báo cáo, ảnh; `.env` phải không có.

## Demo khoảng 10–15 phút

1. `docker compose ps -a`: app/db healthy, migrate Exited (0); không diễn giải migrate đã hoàn thành là lỗi.
2. Khách đặt xe máy/4/7 chỗ, áp dụng WELCOME20; tài xế nhận và thực hiện; admin xem dữ liệu và đối soát chuyển khoản thủ công.
3. pgAdmin đăng nhập, đăng ký server Host `db`, Port `5432`, Database `taxi`, User `taxi`, mật khẩu từ môi trường. Query Tool: `SELECT id,pickup,destination,fare,status FROM trips ORDER BY id DESC LIMIT 20;`.
4. Prometheus `/targets`: năm job UP. Chạy `pg_up`, `nginx_up`, `container_memory_working_set_bytes{service="app"}`.
5. Grafana dashboard **Taxi Booking — Operations**: web request/latency, database connections, CPU/memory container. Chờ ít nhất hai mẫu scrape để `rate` có dữ liệu.
6. Grafana Explore chọn Loki: chạy ba query bên dưới, tạo request website nếu cần log mới.
7. `python tests/hardening.py`: giải thích các biện pháp, mở file config mà không trình chiếu .env.
8. Mở GitHub, lịch sử commit và báo cáo PDF/Word đã điền thông tin sinh viên.

```logql
{job="taxi-nginx",collector="promtail"}
{job="taxi-nginx",collector="promtail"} |= "GET"
sum(count_over_time({job="taxi-nginx",collector="promtail"}[5m]))
```

## Giới hạn cần trình bày đúng

Promtail đã EOL ngày 02/03/2026; chạy vì đề yêu cầu, Alloy được giữ làm lựa chọn thay thế. Cấu hình mặc định thu log Nginx, không tuyên bố đã thu log tất cả container. Positions của Promtail trên tmpfs có thể đọc lại log sau recreate.

Không dùng HTTPS trong bản localhost; đề cho phép security headers. Hai mật khẩu tài khoản demo còn đơn giản theo yêu cầu trước, cần đổi khi trình bày tiêu chí mật khẩu mạnh. DB và monitoring dùng secret riêng, không commit.

Docker Desktop không tương thích cAdvisor đã thử với image store hiện tại; dùng exporter Docker Engine stats thực, không fake metrics. Exporter đọc socket là ngoại lệ cần quản lý, dù không privileged và không publish port. `:ro` trên socket không chặn API ghi nếu tiến trình bị khai thác.

QR chuyển khoản chưa có webhook ngân hàng; admin đối soát. Xe máy dùng quãng đường tuyến ô tô làm tham chiếu. Ảnh map-test là test tile giả và không dùng để minh chứng tile thật trong báo cáo.
