import os, json, time, threading, unicodedata
from urllib.request import Request, urlopen
from flask import request, jsonify

GUIDE = """Bạn là trợ lý Taxi Booking, trả lời tiếng Việt ngắn gọn, chỉ tư vấn đặt xe, dịch vụ và xử lý lỗi.
Khách đăng ký/đăng nhập, chọn điểm đón và điểm đến bằng tìm địa chỉ hoặc bản đồ, chọn xe máy/4 chỗ/7 chỗ, xem giá dự kiến, áp dụng mã hợp lệ và xác nhận đặt xe. Có dịch vụ nội thành và đưa đón sân bay; không cam kết thời gian tài xế đến.
Chuyển khoản: mở thanh toán QR đúng chuyến, kiểm tra số tiền/nội dung, chuyển trong ứng dụng ngân hàng, bấm Tôi đã chuyển khoản. Chỉ thành công sau admin đối soát; nếu chờ/lỗi không chuyển lại ngay, giữ biên nhận và gửi phản ánh.
Quên mật khẩu: dùng email đã lưu trong hồ sơ; nếu không nhận thư kiểm tra spam và nhờ admin kiểm tra cấu hình email. Không tiết lộ hay xin mật khẩu, OTP, khóa API.
Lỗi bản đồ/GPS: kiểm tra mạng, quyền vị trí trình duyệt; có thể tìm địa chỉ hoặc chọn điểm thủ công. Tài xế bật chia sẻ GPS để khách chuyến đang phục vụ theo dõi.
Tài xế bật sẵn sàng, vào Danh sách chuyến, chỉ nhận một chuyến phù hợp phương tiện; bắt đầu và hoàn thành đúng trạng thái. Giấy phép/phương tiện gửi admin duyệt trong Hồ sơ.
Khách hủy chuyến khi chờ tài xế, xem Lịch sử chuyến và gửi phản ánh trong chi tiết chuyến.
Không có quyền xem dữ liệu chuyến, xác nhận thanh toán, đặt/hủy xe hay sửa tài khoản. Không giả vờ đã thực hiện hành động. Không bịa giá/mã/địa chỉ liên hệ. Nếu khách cần người hỗ trợ hoặc liên hệ Admin, hướng dẫn gọi 0325907434. Hỏi thêm mã lỗi/trạng thái nếu thiếu thông tin, tránh yêu cầu dữ liệu nhạy cảm."""

def basic(message):
    text=''.join(c for c in unicodedata.normalize('NFD',message.lower()) if unicodedata.category(c)!='Mn').replace('đ','d')
    if any(w in text for w in ['lien he','admin','nguoi that','ho tro truc tiep','so dien thoai']):
        return 'Bạn có thể liên hệ chúng tôi qua số 0325907434. Bấm nút Liên hệ trong khung chat để gọi trực tiếp. Khi trao đổi, chuẩn bị mã chuyến hoặc nội dung lỗi; không cung cấp mật khẩu hay OTP.'
    if any(w in text for w in ['chuyen khoan','thanh toan','qr']):
        return 'Mở Thanh toán của chuyến, kiểm tra QR, số tiền và nội dung rồi chuyển trong ứng dụng ngân hàng. Bấm “Tôi đã chuyển khoản”. Admin cần đối soát trước khi trạng thái thành công. Nếu đang chờ hoặc thất bại, giữ biên nhận và gửi phản ánh; đừng chuyển lại ngay.'
    if any(w in text for w in ['mat khau','dang nhap','email']):
        return 'Vào trang Đăng nhập, kiểm tra email/số điện thoại hoặc tên đăng nhập. Quên mật khẩu thì chọn “Quên mật khẩu” và nhập email đã lưu trong hồ sơ. Kiểm tra thư rác; nếu chưa nhận thư, liên hệ admin kiểm tra cấu hình gửi email.'
    if any(w in text for w in ['ban do','gps','vi tri']):
        return 'Kiểm tra kết nối mạng và cho phép trình duyệt truy cập vị trí. Bạn vẫn có thể tìm địa chỉ hoặc chọn điểm trực tiếp trên bản đồ. Nếu còn lỗi, cho mình biết thao tác và thông báo lỗi đang hiện nhé.'
    if any(w in text for w in ['tai xe','nhan chuyen']):
        return 'Tài xế bật “Sẵn sàng nhận chuyến”, vào Danh sách chuyến và chọn Nhận chuyến phù hợp phương tiện. Chỉ nhận một chuyến tại một thời điểm. Nếu không nhận được, kiểm tra trạng thái sẵn sàng, loại xe và chuyến đang phục vụ.'
    if any(w in text for w in ['loai xe','dich vu','san bay','7 cho','xe may']):
        return 'Có xe máy, xe 4 chỗ và xe 7 chỗ; hỗ trợ nội thành và đưa đón sân bay. Chọn phương tiện theo số người/hành lý, nhập đúng điểm đón và điểm đến rồi xem giá dự kiến trước khi xác nhận.'
    if any(w in text for w in ['loi','khong','that bai']):
        return 'Bạn gặp lỗi ở đăng nhập, bản đồ, đặt xe hay thanh toán? Cho mình biết thao tác và nội dung lỗi để hướng dẫn cụ thể. Có thể tải lại trang và kiểm tra mạng. Nếu chuyển tiền rồi, giữ biên nhận và gửi phản ánh trong chi tiết chuyến.'
    return 'Để đặt xe: đăng nhập → nhập điểm đón/điểm đến → chọn xe máy, 4 chỗ hoặc 7 chỗ → kiểm tra giá và mã ưu đãi → xác nhận. Xem trạng thái trong Lịch sử chuyến. Bạn cần tư vấn bước nào?'

def register_chat(app):
    lock=threading.Lock();requests=[]
    @app.post('/api/public/chat')
    def chat():
        data=request.get_json(silent=True)
        if not isinstance(data,dict):return jsonify(error='Tin nhắn không hợp lệ'),400
        message=data.get('message');history=data.get('history',[])
        if not isinstance(message,str) or not 1<=len(message.strip())<=1000 or not isinstance(history,list) or len(history)>8:
            return jsonify(error='Nhập tin nhắn từ 1 đến 1000 ký tự'),400
        for item in history:
            if not isinstance(item,dict) or item.get('role') not in ('user','assistant') or not isinstance(item.get('content'),str) or len(item['content'])>4000:
                return jsonify(error='Lịch sử trò chuyện không hợp lệ'),400
        with lock:
            now=time.monotonic();requests[:]=[t for t in requests if now-t<60]
            if len(requests)>=30:return jsonify(error='Có nhiều yêu cầu hỗ trợ. Bạn thử lại sau một phút nhé.'),429
            requests.append(now)
        key=os.getenv('OPENAI_API_KEY','').strip()
        if key:
            try:
                payload={'model':os.getenv('OPENAI_MODEL','gpt-4.1-mini'),'instructions':GUIDE,'input':history+[{'role':'user','content':message.strip()}],'max_output_tokens':600,'store':False}
                req=Request('https://api.openai.com/v1/responses',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
                with urlopen(req,timeout=20) as response:result=json.load(response)
                answer='\n'.join(part['text'] for item in result.get('output',[]) if item.get('type')=='message' for part in item.get('content',[]) if part.get('type')=='output_text').strip()
                if not answer:raise ValueError('empty answer')
                return jsonify(answer=answer[:4000],mode='ai')
            except Exception:
                app.logger.warning('AI support unavailable; using basic guidance')
        return jsonify(answer=basic(message),mode='basic')
