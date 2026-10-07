# Ảnh tài xế và thanh toán chuyển khoản

## Ảnh đại diện

Đăng nhập tài xế, chọn **Chọn ảnh từ thư viện** trong thẻ Thông tin tài xế hoặc trang Hồ sơ. Chọn JPG, PNG hoặc WebP, tối đa 2 MB và 16 triệu điểm ảnh. Hệ thống kiểm tra nội dung ảnh, xoay theo EXIF, cắt giữa thành ảnh vuông 512×512 và lưu JPEG trong PostgreSQL, không giữ EXIF. Ảnh hiển thị trên thẻ tài xế, đầu trang và Hồ sơ; vẫn còn sau tải lại hoặc khởi động Docker. **Xóa ảnh** khôi phục hình mặc định.

## Chuyển khoản

1. Khách chọn **Chuyển khoản ngân hàng** khi đặt xe, hoặc bấm chuyển khoản trong chi tiết chuyến.
2. QR được tạo trực tiếp trong ứng dụng theo định dạng VietQR, gồm ngân hàng, số tài khoản, số tiền và nội dung riêng của yêu cầu. Không gọi dịch vụ QR bên ngoài.
3. Khách kiểm tra tên người nhận do ứng dụng ngân hàng hiển thị, chuyển đúng số tiền và nội dung. Bấm **Tôi đã chuyển khoản** để gửi yêu cầu đối soát.
4. Admin mở **Thanh toán**, kiểm tra sao kê ngân hàng, chọn **Đã nhận tiền** hoặc **Từ chối**. Phải ghi mã giao dịch/ghi chú hoặc lý do từ chối.
5. Khách thấy **Chuyển khoản thành công** hoặc **Chuyển khoản thất bại**, kèm ghi chú. Màn hình tự cập nhật; cũng có nút Kiểm tra trạng thái. Sau thất bại có thể tạo yêu cầu mới, nội dung mới; lịch sử cũ vẫn giữ.

**Thành công là kết quả admin đối soát**, không phải xác nhận tự động từ ngân hàng. Website không tự chuyển tiền, không trừ tiền và chưa tích hợp webhook ngân hàng. Lỗi tải QR chỉ là lỗi hiển thị QR; không kết luận giao dịch thất bại. Nếu đã bị trừ tiền nhưng bị từ chối, liên hệ admin trước khi chuyển lại. Hoàn tiền xử lý ngoài hệ thống.

Tài khoản nhận mặc định lấy theo ảnh người dùng cung cấp: Vietcombank, BIN `970436`, số tài khoản `9398142181`, chủ tài khoản `LY MINH PHUONG`. Admin thay đổi tại **Cài đặt → Tài khoản nhận chuyển khoản**. Thông tin này chưa được xác thực với ngân hàng. Cấu hình mới chỉ áp dụng cho yêu cầu thanh toán mới; yêu cầu cũ giữ nguyên tài khoản và số tiền. Tiền VND được làm tròn tới đồng cho chuyển khoản.

Các trạng thái: `awaiting_transfer` (chưa gửi xác nhận), `pending` (chờ admin), `success` và `failed`. Khách chỉ thao tác chuyến của mình; chỉ admin có thể ghi nhận thành công/thất bại. Chống gửi lặp và hai admin đồng thời xác nhận. Chuyến có giao dịch chờ xác nhận hoặc thành công không thể hủy trực tiếp. Chuyến đã tạo QR không thể thay đổi giá khi yêu cầu còn hiệu lực. Hủy chuyến trước khi gửi xác nhận làm yêu cầu QR thất bại và vô hiệu hóa QR.

## Kiểm tra

```powershell
python tests/payment_media.py
node tests/payment_browser.cjs
```

Test API kiểm tra ảnh hợp lệ/sai định dạng/quá kích thước/quyền truy cập, QR có phạm vi truy cập và hiệu lực, số tiền, gửi lặp, thử lại và đối soát đồng thời. Test Chrome chọn file qua ô tải ảnh, xác nhận ảnh sau tải lại, xóa ảnh; thực hiện chuyển khoản → chờ → thất bại → thử lại → thành công bằng các tài khoản thử riêng. Không thực hiện giao dịch ngân hàng thật. Test tạo dữ liệu thử trong database đang chạy. Ảnh minh họa kết quả ở `docs/screenshots/`.

Tham khảo định dạng: [mã nguồn và tài liệu VietQR](https://github.com/subiz/vietqr), [thư viện QR Python](https://pypi.org/project/qrcode/). Cấu trúc sử dụng NAPAS GUID, dịch vụ `QRIBFTTA`, tiền tệ VND và CRC-16/CCITT-FALSE; QR ảnh có khoảng trắng bảo vệ quanh mã.
