# Bản đồ thực tế: khách và tài xế

Khách có thể tìm địa điểm rồi chọn kết quả, hoặc dùng nút **Chọn điểm đón / Chọn điểm đến** và bấm trên bản đồ. Có thể kéo thả các ghim A/B. Nhập địa chỉ mới sẽ xóa tọa độ cũ; phải chọn lại kết quả hoặc ghim để tránh đặt nhầm điểm. Nút **Vị trí của tôi** chỉ lấy GPS khi người dùng bấm và cho phép quyền định vị.

**Tính tuyến đường và giá** lấy tuyến ô tô từ OSRM. Quãng đường là đường đi, không phải đường thẳng. Thời gian chỉ là ước tính theo dữ liệu đường, chưa có giao thông thời gian thực. Backend tạo báo giá tuyến có hiệu lực 15 phút, gắn với người đăng nhập, chỉ dùng cho một lần đặt; giá chuyến dùng quãng đường máy chủ lưu, không tin số km gửi từ trình duyệt. Giá cước vẫn lấy biểu giá 4/7 chỗ hiện tại và giữ nguyên sau khi đặt. Tọa độ, hình học tuyến đường và thời gian được lưu cùng chuyến.

Tài xế chọn chuyến trong **Bản đồ chuyến và vị trí tài xế**, hoặc bấm **Xem bản đồ** trong chi tiết chuyến. Xem điểm đón/đến, tuyến ô tô và khoảng cách. Tài xế có thể xem bản đồ chuyến chờ phù hợp phương tiện, nhưng không xem GPS hay bản đồ chuyến đã được tài xế khác nhận.

**Chia sẻ vị trí GPS** dùng định vị thật của trình duyệt. Chỉ bắt đầu sau khi tài xế bấm nút và cấp quyền. Vị trí cập nhật tối đa một lần mỗi 10 giây khi có bản tin GPS mới, gồm sai số thiết bị. **Dừng chia sẻ** xóa vị trí khỏi máy chủ; đăng xuất cũng xóa. Khách bấm **Xem trên bản đồ** tại chuyến của mình để theo dõi. Chỉ khách của chuyến đã nhận/đang chạy và admin được xem vị trí; chuyến kết thúc không còn trả GPS. Vị trí quá 2 phút bị ẩn. Không tạo vị trí giả nếu không có quyền GPS hoặc thiết bị chưa lấy được vị trí.

Bản đồ nền dùng Leaflet 1.9.4 và OpenStreetMap, thư viện JS/CSS lưu trong dự án. Tìm địa điểm dùng Photon, chỉ khi người dùng bấm Tìm hoặc Enter, không tìm tự động mỗi ký tự. Photon và OSRM đi qua backend, có cache 24 giờ và giới hạn một request/giây cho từng dịch vụ; cấu hình hiện tại dùng một worker Gunicorn. Khi tăng số worker/máy, cần thay giới hạn trong bộ nhớ bằng Redis hoặc giới hạn dùng chung trước khi sử dụng dịch vụ demo. Bản đồ nền giữ ghi công OpenStreetMap và dùng cache của trình duyệt, không có tải hàng loạt/offline.

Chuyến cũ và chuyến do admin đặt bằng khoảng cách thủ công giữ nhãn `manual`, không tự suy đoán tọa độ hoặc thay giá lịch sử. Chuyến khách đặt bằng giao diện mới dùng `map`. Admin không sửa tuyến đã lưu bằng form khoảng cách thủ công để tránh địa chỉ và tọa độ không khớp.

## Cấu hình và giới hạn

Các dịch vụ công cộng hiện tại phù hợp đồ án/dùng thử ít người, không có SLA. OSRM demo giới hạn sử dụng hợp lý, phi thương mại và tối đa một request/giây. Photon demo có thể giới hạn hoặc chặn tải lớn. Khi triển khai dịch vụ taxi thật, dùng nhà cung cấp theo hợp đồng hoặc tự host; không tăng tải lên máy chủ demo.

Các biến `.env` có thể thay thế nhà cung cấp:

```dotenv
MAP_SEARCH_URL=https://photon.komoot.io/api/
MAP_ROUTING_URL=https://router.project-osrm.org/route/v1/driving
MAP_TILE_URL=https://tile.openstreetmap.org/{z}/{x}/{y}.png
MAP_USER_AGENT=TaxiBookingStudentProject/1.0 (+http://127.0.0.1:8080)
```

Nhà cung cấp tìm địa điểm phải tương thích API Photon; định tuyến tương thích OSRM. Khi đổi cấu hình chạy `docker compose up -d app`, rồi khởi động lại Nginx. Muốn thay nhà cung cấp qua môi trường cần tải lại trang để lấy cấu hình tile mới. CSP tự cho phép host tile được cấu hình; không tải script từ bên ngoài.

Trình duyệt tải tile trực tiếp từ nhà cung cấp. Nội dung tìm địa điểm và hai tọa độ được gửi tới dịch vụ tương ứng để tìm và tính tuyến; không gửi tên khách, tài khoản, số điện thoại hoặc thông tin thanh toán. GPS tài xế lưu điểm mới nhất trong PostgreSQL và không gửi tới nhà cung cấp tìm địa điểm/định tuyến trong luồng theo dõi hiện tại.

GPS cần thiết bị có định vị và quyền trình duyệt. `http://127.0.0.1` được hỗ trợ khi chạy trên máy local; mở qua tên miền/IP máy khác cần HTTPS để dùng định vị. Nếu mạng lỗi, web báo không tải bản đồ/không tính được tuyến, không thay bằng tuyến giả. Có thể vẫn xem các điểm và tuyến đã lưu khi nền bản đồ không tải được.

## Kiểm tra

```powershell
Get-Content -Raw -Encoding utf8 tests/map_features.py | docker compose exec -T app python -
node tests/maps_browser.cjs
```

Test backend dùng fixture dịch vụ, kiểm tra giá/khoảng cách máy chủ, báo giá hết hạn/tái sử dụng/quyền sở hữu/rollback, phạm vi GPS, dừng chia sẻ, đăng xuất, hết chuyến và lỗi dịch vụ. Test Chrome dùng GPS mô phỏng ở địa điểm công cộng cho tài khoản thử riêng, kiểm tra tìm/chọn/click, tuyến đường và giá, bản đồ tài xế, bật/tắt GPS, khách theo dõi và mobile. Tile trong test được thay bằng ảnh kiểm thử để không dùng trình duyệt tự động tải nhiều tile OSM. Ảnh `customer-map-test.png` và `driver-map-test.png` chỉ là ảnh kiểm thử, không phải ảnh nền địa lý thật. Có thể kiểm tra nền thật bằng mở ứng dụng và chọn bản đồ bình thường.

Đã kiểm tra riêng tìm kiếm Photon và tuyến OSRM thật với hai địa điểm công cộng ở Hà Nội, không dùng dữ liệu cá nhân.

Tài liệu dịch vụ: [Leaflet](https://leafletjs.com/reference.html), [Photon](https://github.com/komoot/photon), [OSRM demo và giới hạn](https://github.com/Project-OSRM/osrm-backend/wiki/Demo-server), [OpenStreetMap tile policy](https://operations.osmfoundation.org/policies/tiles/).
