# Đề 22 — Hệ thống Đặt xe / Taxi Booking

Ứng dụng Taxi Booking với ba giao diện khách, tài xế và admin theo ảnh minh họa, Flask + PostgreSQL và Docker Compose. Có Nginx reverse proxy, pgAdmin, Prometheus, Grafana, Loki và Promtail thu thập log (Alloy là profile thay thế). GitHub Actions kiểm tra luồng nghiệp vụ khi push/PR. Xem [bảng đối chiếu chức năng theo tài liệu](docs/DOI_CHIEU_CHUC_NANG.md).

## Chạy trên Windows / Linux

Cài Docker Desktop và bật Linux containers. Chạy trong thư mục dự án:

```powershell
Copy-Item .env.example .env # Chỉ chạy khi chưa có .env; giữ file đã tạo sẵn trên máy này.
# Sửa các mật khẩu trong .env trước khi chạy.
docker compose up -d --build
docker compose ps
```

Mật khẩu database trong cấu hình URL hiện tại dùng chữ, số, dấu gạch ngang/gạch dưới; nếu dùng ký tự đặc biệt phải URL-encode trong DATABASE_URL. Mật khẩu tài khoản tối thiểu 8, tối đa 128 ký tự. Không commit `.env`.

| Dịch vụ | Địa chỉ | Đăng nhập |
|---|---|---|
| Taxi Booking | http://127.0.0.1:8080 | Tài khoản theo bảng bên dưới |
| pgAdmin | http://127.0.0.1:5050 | PGADMIN_EMAIL / PGADMIN_PASSWORD |
| Grafana | http://127.0.0.1:3000 | admin / GRAFANA_PASSWORD |
| Prometheus | http://127.0.0.1:9090 | Không có đăng nhập, chỉ bind localhost |

Trong pgAdmin: Add New Server → tên `Taxi DB` → Connection: Host `db`, Port `5432`, Maintenance database `taxi`, Username `taxi`, Password `POSTGRES_PASSWORD`. Dữ liệu mẫu được tạo khi volume PostgreSQL khởi tạo lần đầu.

## Tài khoản và phân quyền

| Vai trò | Tên đăng nhập demo | Mật khẩu trong `.env` | Quyền |
|---|---|---|---|
| Admin | `admin` (hoặc `ADMIN_USERNAME`) | `ADMIN_PASSWORD` | Xem tất cả chuyến/thống kê, tạo khách và tài xế kèm tài khoản, đặt chuyến, phân công và cập nhật trạng thái |
| Tài xế | `taixe` | `DRIVER_PASSWORD` | Bật/tắt nhận chuyến, xem hàng chờ đúng loại xe, nhận chuyến, báo đã đến/bắt đầu/hoàn thành; hồ sơ và thu nhập riêng |
| Khách hàng | `khach` | `CUSTOMER_PASSWORD` | Đăng ký, đặt xe máy/4/7 chỗ, theo dõi/lịch sử riêng, hủy khi còn chờ nhận, hồ sơ, đánh giá và phản ánh |

Giao diện và menu tự đổi theo tài khoản. Backend kiểm tra vai trò và chủ sở hữu. Tài xế chỉ xem hàng chờ với địa chỉ/tên khách/giá, chưa được lấy liên hệ khách trước khi nhận; lịch sử và chi tiết giới hạn theo chủ sở hữu. Khách/tài xế không được lấy danh sách quản trị hoặc phân công người khác.

Migration tự chạy trước app và không xóa dữ liệu cũ. Ba tài khoản demo liên kết dữ liệu mẫu có sẵn. Mật khẩu trong `.env` chỉ dùng khi tạo tài khoản lần đầu; sửa `.env` không tự đổi mật khẩu tài khoản đã tồn tại. Khách có thể tự đăng ký; admin tạo tài khoản tài xế qua form quản lý.

Để thử nhiều vai trò cùng lúc, dùng cửa sổ ẩn danh hoặc các trình duyệt khác nhau vì cookie đăng nhập được chia sẻ giữa các tab.

## Chức năng quản trị

- **Khách hàng, tài xế:** thêm hồ sơ kèm tài khoản, tìm kiếm, sửa tên/SĐT/biển số, đổi tài xế sang sẵn sàng hoặc đang nghỉ; xem lịch sử chuyến theo từng hồ sơ.
- **Lưu trữ/khôi phục:** giữ lịch sử chuyến và hồ sơ thay vì xóa dữ liệu tham chiếu. Lưu trữ tự khóa tài khoản và thu hồi phiên. Không lưu trữ hồ sơ còn chuyến hoạt động; sau khôi phục, admin mở khóa tài khoản riêng.
- **Tài khoản:** tìm kiếm/lọc vai trò và trạng thái, tạo thêm admin hoặc liên kết hồ sơ cũ chưa có tài khoản, khóa/mở khóa, reset mật khẩu. Khóa/reset thu hồi phiên; chặn tự khóa và giữ ít nhất một admin. Chặn thu hồi phiên tài xế đang bận để không gián đoạn chuyến.
- **Điều phối:** tạo chuyến cho khách, xem chi tiết liên hệ, sửa hành trình/cước khi chuyến còn pending, phân công hoặc đổi tài xế khi assigned, bắt đầu/hoàn thành và hủy theo vòng đời chuyến. Đổi tài xế giải phóng tài xế cũ và khóa tài xế mới trong cùng giao dịch.
- **Tra cứu:** tìm theo mã, tên, SĐT, địa chỉ, biển số; lọc trạng thái và khoảng ngày, phân trang 20 chuyến. Bộ lọc áp dụng cho thống kê, báo cáo và xuất CSV.
- **Báo cáo:** tổng chuyến, đang hoạt động, hoàn thành, hủy, doanh thu, số khách hoạt động, tài xế sẵn sàng, tài khoản khóa; biểu đồ và bảng doanh thu ngày/tài xế. Ngày tính theo giờ Việt Nam, doanh thu nhóm theo ngày tạo chuyến đã hoàn thành.
- **CSV:** tải tất cả chuyến theo bộ lọc, không chỉ trang đang xem; UTF-8 BOM cho Excel và vô hiệu hóa dữ liệu có thể bị diễn giải thành công thức.
- **Nhật ký:** lưu người thao tác, hành động, đối tượng, thời gian; phân trang 50 dòng, không lưu mật khẩu/hash/session token trong nhật ký.

Các chức năng sửa hồ sơ, tài khoản, báo cáo, export và audit đều được kiểm tra quyền admin ở server.

| Method | API admin bổ sung | Chức năng |
|---|---|---|
| PATCH / DELETE | /api/customers/:id, /api/drivers/:id | Sửa / lưu trữ hồ sơ; PATCH `archived:false` để khôi phục |
| GET / POST | /api/admin/users | Xem / tạo tài khoản (`username`, `password`, `role`; `profile_id` cho khách/tài xế) |
| PATCH | /api/admin/users/:id | Khóa/mở với `active`; reset bằng `password` |
| GET | /api/trips/:id | Chi tiết chuyến, vẫn giới hạn theo chủ sở hữu với khách/tài xế |
| PATCH | /api/admin/trips/:id | Sửa `pickup`, `destination`, `distance` khi pending |
| GET | /api/admin/reports | Báo cáo ngày, tài xế và các số đếm quản trị |
| GET | /api/admin/export | CSV theo bộ lọc |
| GET | /api/admin/audit?page=1 | Nhật ký thao tác |

`GET /api/trips` nhận `q`, `status`, `customer_id`, `driver_id`, `from`, `to`, `page`, `limit` (1–500); `stats`, `reports`, `export` nhận cùng bộ lọc nghiệp vụ. Giữ toàn bộ lịch sử chuyến, không có API xóa chuyến đã hoàn thành.

## Demo để trình bày

1. Mở ứng dụng, đăng nhập tài khoản `admin`.
2. Thêm khách hàng và tài xế, hoặc dùng dữ liệu mẫu.
3. Chọn khách, nhập hai địa chỉ và số km → Tạo chuyến.
4. Đăng nhập `khach`, đặt chuyến; ở cửa sổ ẩn danh đăng nhập `taixe` → Chuyến đang chờ → Nhận chuyến → Đã đến → Bắt đầu → Hoàn thành. Admin vẫn có thể điều phối bằng menu Chuyến đi.
5. Doanh thu chỉ cộng những chuyến đã hoàn thành. Tài xế được giải phóng khi hoàn thành/hủy.
6. Thử phân công tài xế đang bận để thấy hệ thống ngăn nhận hai chuyến.
7. Mở Grafana → Dashboards → Taxi Booking → Taxi Booking — Operations. Sau khoảng 30 giây và vài yêu cầu, có biểu đồ request, latency và log Nginx.

Cước mặc định: **xe máy = 10.000 + 5.000 × km**, **xe 4 chỗ = 15.000 + 12.000 × km**, **xe 7 chỗ = 20.000 + 15.000 × km**. Admin sửa biểu giá trong Cài đặt; giá mới chỉ áp dụng cho chuyến đặt sau đó. Khách chọn vị trí trên bản đồ OpenStreetMap; OSRM tính quãng đường ô tô, máy chủ lưu tuyến và tính giá. Chuyến cũ/admin đặt thủ công giữ dữ liệu lịch sử. Hỗ trợ tiền mặt và chuyển khoản QR tạo cục bộ, admin đối soát thành công/thất bại.

## Cấu trúc và kiến trúc

```text
Browser → Nginx :8080 → Flask :8000 → PostgreSQL :5432
                       ↑ Prometheus → Grafana
Nginx log files → Promtail → Loki → Grafana
pgAdmin → PostgreSQL
```

- `app.py`: REST API, phiên đăng nhập, phân quyền, validation, giao dịch và metrics.
- `migrate.py` + `db/auth.sql`: tự bổ sung bảng tài khoản/phiên và tài khoản demo, giữ dữ liệu cũ.
- `static/`: giao diện responsive, không cần npm hay CDN.
- `db/init.sql`: schema, ràng buộc, index và dữ liệu mẫu.
- `infra/`: reverse proxy, metrics, log và dashboard tự provision.
- `tests/smoke.py`: kiểm tra HTTP thực với stack đang chạy.
- `.github/workflows/ci.yml`: CI dành cho GitHub.

Quan hệ dữ liệu: một khách hàng có nhiều chuyến; một tài xế có nhiều chuyến nhưng chỉ một chuyến đang hoạt động. Trạng thái chuyến:

```text
pending → assigned → ongoing → completed
   ↓          ↓
cancelled  cancelled
```

Phân công dùng `SELECT ... FOR UPDATE` trên chuyến và tài xế, cùng unique partial index chống trùng chuyến hoạt động. Các truy vấn dùng tham số để tránh SQL injection.

## API

Đăng nhập bằng `POST /api/auth/login` với `username`, `password`. Giữ cookie `taxi_session` từ response. Với POST/PATCH đã đăng nhập, gửi header `X-CSRF-Token` lấy từ response đăng nhập hoặc `GET /api/auth/me`. `POST /api/auth/logout` thu hồi phiên. Token quản trị cũ không còn được chấp nhận.

| Method | Endpoint | Chức năng |
|---|---|---|
| GET | /api/health | Kiểm tra kết nối database, không yêu cầu đăng nhập |
| POST | /api/auth/register | Đăng ký khách (`name`, `phone`, `username`, `password`); không được tự chọn quyền admin/tài xế |
| GET / POST | /api/customers | Admin: danh sách / thêm khách và tài khoản (`name`, `phone`, `username`, `password`) |
| GET / POST | /api/drivers | Admin: danh sách / thêm tài xế và tài khoản (`name`, `phone`, `plate`, `username`, `password`) |
| GET / POST | /api/trips | 500 chuyến mới nhất / tạo (`customer_id`, `pickup`, `destination`, `distance`) |
| PATCH | /api/trips/:id | Chuyển `status`, thêm `driver_id` khi phân công |
| GET | /api/stats | Tổng chuyến, đang hoạt động, hoàn thành và doanh thu |
| GET | /metrics | Prometheus nội bộ; Nginx chặn truy cập công khai |

## Kiểm tra

Với Python 3.12 và stack đang chạy:

```powershell
python tests/smoke.py
python tests/admin.py # CRUD, khóa/reset, điều phối, báo cáo, CSV, audit và kiểm tra quyền.
python tests/features.py # Các chức năng theo kế hoạch và hai tài xế cùng nhận chuyến.
python tests/monitoring.py # Kiểm tra dashboard, metrics, log và pgAdmin; đọc mật khẩu từ .env.
```

Test đọc mật khẩu admin từ `.env` hoặc `ADMIN_PASSWORD` trong môi trường, tạo khách/tài xế/chuyến riêng và giữ lại dữ liệu. Kiểm tra cả ba vai trò, truy cập chuyến người khác, thống kê riêng, đăng ký không thể tự nâng quyền, CSRF, thu hồi phiên sau logout và luồng chuyến/concurrency. CI tự chạy bằng thông tin thử nghiệm từ `.env.example` trên runner tạm.

Test email reset với SMTP giả lập, không gửi thư (PowerShell):

```powershell
Get-Content -Raw -Encoding utf8 tests/password_reset.py | docker compose exec -T app python -
```

Email khôi phục thật cần điền `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_TLS`, `PUBLIC_URL` trong `.env`, rồi `docker compose up -d app`. `ADMIN_RESET_EMAIL` dành cho admin. Khách/tài xế cần lưu email trong Hồ sơ. Token có hiệu lực 30 phút và dùng một lần; gửi trong URL fragment để không nằm trong access log. Khi chưa cấu hình SMTP, dùng reset mật khẩu trong trang tài khoản admin.

Kiểm tra giao diện thực trên Windows có Chrome và Node.js 22:

```powershell
node tests/browser.cjs
```

Có thể đặt `CHROME_PATH` nếu Chrome ở vị trí khác. Test dùng hồ sơ trình duyệt tạm, kiểm tra đăng nhập ba vai trò, bảng admin, sửa hồ sơ, hộp thoại tạo tài khoản, bộ lọc và chi tiết chuyến. Test sửa một hồ sơ bằng giá trị hiện tại và thêm một dòng nhật ký, giữ hồ sơ trình duyệt trong thư mục tạm.

## Hardening và vận hành

- Chỉ Nginx công bố ứng dụng; database, Loki, Alloy và app không mở port host. Các cổng quản trị chỉ bind `127.0.0.1`.
- App chạy user không phải root, filesystem read-only, bỏ capabilities, giới hạn body, CSP, chống iframe và MIME sniffing.
- Nginx giới hạn request API và ẩn phiên bản. Mật khẩu hash bằng scrypt, cookie HttpOnly/SameSite, phiên lưu hash token và hết hạn sau 24 giờ. POST/PATCH kiểm tra CSRF và Origin. Thông tin đăng nhập không lưu localStorage.
- Mật khẩu cấu hình qua `.env`; dữ liệu lưu volume bền vững; Loki giữ log 7 ngày.
- Khi đưa ra Internet cần HTTPS, đặt `COOKIE_SECURE=true`, secret manager, backup và log rotation cho file Nginx. Không mở các dashboard quản trị trực tiếp ra Internet.

```powershell
docker compose logs --tail=100 app nginx
docker compose restart app
docker compose down
```

`down` giữ dữ liệu. Không chạy `down -v` trừ khi muốn xóa toàn bộ dữ liệu. Đổi POSTGRES_PASSWORD trong `.env` không tự đổi mật khẩu của database đã có volume.

Backup từ PowerShell (tránh redirect binary qua PowerShell cũ):

```powershell
docker compose exec db pg_dump -U taxi -d taxi -Fc -f /tmp/taxi.dump
docker compose cp db:/tmp/taxi.dump ./taxi.dump
```

## Đưa lên GitHub

Tạo repository trống trên GitHub rồi chạy (thay URL):

```powershell
git init
git add .
git commit -m "Build taxi booking system with monitoring"
git branch -M main
git remote add origin https://github.com/YOUR_USER/taxi-booking.git
git push -u origin main
```

Chưa tự tạo/push repository vì dự án chưa có URL repository đích.

Ảnh ba giao diện: `docs/screenshots/`. Đối chiếu chức năng: [tài liệu](docs/DOI_CHIEU_CHUC_NANG.md).

## Bổ sung ảnh và thanh toán chuyển khoản

Đã có chọn ảnh tài xế từ thư viện và thanh toán chuyển khoản QR tạo cục bộ, admin đối soát thành công/thất bại. Xem [hướng dẫn chi tiết](docs/ANH_VA_THANH_TOAN.md).

## Bản đồ khách và tài xế

Đã tích hợp Leaflet + OpenStreetMap, tìm địa điểm Photon, tuyến ô tô OSRM, giá theo quãng đường máy chủ và GPS tài xế chia sẻ tự nguyện. Xem [hướng dẫn và giới hạn dịch vụ demo](docs/BAN_DO_THUC_TE.md).

Xe máy và ưu đãi: [hướng dẫn](docs/XE_MAY_VA_UU_DAI.md).


## Đối chiếu yêu cầu học phần và demo

Xem [hướng dẫn nộp bài/demo](docs/NOP_BAI_VA_DEMO.md), [báo cáo Word](docs/BAO_CAO_TAXI_BOOKING.docx), [báo cáo PDF](docs/BAO_CAO_TAXI_BOOKING.pdf) và [bản Markdown](docs/BAO_CAO.md).

- Nginx có security headers và rate limit; nhánh HTTP + security headers đáp ứng lựa chọn trong đề, chưa có HTTPS.
- Prometheus có năm job: API, Prometheus, Nginx exporter, PostgreSQL exporter và Docker Engine container exporter. Grafana có 11 panel, được provision tự động.
- Loki + Promtail chạy mặc định; label collector="promtail" xác định log mới. Promtail EOL, giữ Alloy trong profile thay thế; không chạy hai collector cùng lúc.
- App non-root/read-only/cap_drop/no-new-privileges; mạng DB và monitoring internal; DB không map port; runtime taxi_app chỉ DML; migrate chạy riêng một lần, không gửi secret quản trị DB cho app.
- Container-exporter là ngoại lệ đọc Docker socket, không privileged và không mở port host. Socket :ro không bảo đảm API read-only; cần kiểm soát kỹ nếu triển khai production.
- Mật khẩu admin/tài xế demo còn theo yêu cầu trước; đổi thành mật khẩu mạnh trước triển khai public. Secret hạ tầng không nằm trong Git.

```powershell
python tests/monitoring.py
python tests/hardening.py
```

Trong Grafana Explore chọn Loki và chạy:

```logql
{job="taxi-nginx",collector="promtail"}
{job="taxi-nginx",collector="promtail"} |= "GET"
sum(count_over_time({job="taxi-nginx",collector="promtail"}[5m]))
```

Đổi collector (không chạy đồng thời):

```powershell
docker compose stop promtail
docker compose --profile alloy up -d alloy
# Quay lại yêu cầu đề:
docker compose stop alloy
docker compose up -d promtail
```

Điền thông tin thật vào `docs/student.json`, rồi tạo lại báo cáo:

```powershell
python -m pip install python-docx reportlab
python docs/build_report.py
```

Bản PDF/Word hiện để placeholder cho thông tin sinh viên và repo GitHub; chưa push khi chưa được cung cấp URL/xác thực. Tài khoản/repo phải đặt tên theo MSSV theo yêu cầu giảng viên.

Trang chủ mới: menu xanh, ảnh taxi, đăng ký/khôi phục mật khẩu, ưu đãi công khai và thẻ dịch vụ. Đăng nhập bằng username hoặc SĐT/email đã lưu (alias trùng tài khoản bị từ chối). Ghi nhớ đăng nhập giữ phiên 30 ngày; không chọn thì cookie theo phiên trình duyệt và hết hạn server sau 24 giờ. Ưu đãi lấy từ mã còn hiệu lực; chọn dịch vụ/mã trước đăng nhập được chuyển vào form đặt xe. Ảnh minh họa mới trong static/assets/taxi-hero.png và taxi-services.png.


### Trang đăng nhập và chatbot hỗ trợ
Trang chủ không chứa biểu mẫu đăng nhập. Truy cập `/#login` hoặc `/#register` để mở trang riêng; hỗ trợ quên mật khẩu vẫn hoạt động. Nút tin nhắn góc dưới mở khung trò chuyện ở cả trang công khai và sau đăng nhập.

Chat hỗ trợ đặt xe, các loại phương tiện/dịch vụ và xử lý lỗi. Để bật AI, điền `OPENAI_API_KEY` vào `.env` (không đưa khóa vào Git hoặc JavaScript), tùy chọn `OPENAI_MODEL` rồi chạy `docker-compose up -d --build app` và `docker-compose restart nginx`. Tích hợp phía máy chủ theo [OpenAI Responses API](https://developers.openai.com/api/docs/guides/text), gửi tối đa 8 tin gần nhất, `store=false`, timeout 20 giây và giới hạn 30 yêu cầu/phút trên tiến trình. Không tự gửi hồ sơ, chuyến đi hoặc cookie đến AI. Tin nhắn do người dùng nhập được gửi đến nhà cung cấp khi AI bật. Chat chỉ tư vấn, không thực hiện đặt xe hoặc xác nhận thanh toán. Chưa có khóa hoặc AI lỗi thì hiển thị rõ **Hướng dẫn cơ bản**, không giả lập AI.
