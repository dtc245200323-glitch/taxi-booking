"""Driver photos and manually reconciled bank transfers (no simulated bank success)."""
import io
import re
import secrets
import warnings
import binascii
from decimal import ROUND_HALF_UP
from flask import request, jsonify, g, Response
from PIL import Image, ImageOps, UnidentifiedImageError
import qrcode


def vietqr_payload(bank_bin, account_no, amount, reference):
    """NAPAS transfer-to-account TLV with CRC-16/CCITT-FALSE, generated offline."""
    def tlv(tag,value):
        value=str(value)
        if not value.isascii() or len(value)>99:
            raise ValueError('qr_field')
        return tag+f'{len(value):02d}'+value
    if not re.fullmatch(r'[0-9]{6}',bank_bin) or not re.fullmatch(r'[0-9]{6,19}',account_no):
        raise ValueError('qr_account')
    if not re.fullmatch(r'[0-9]{1,13}',str(amount)) or int(amount)<=0 or len(reference)>25:
        raise ValueError('qr_payment')
    beneficiary=tlv('00',bank_bin)+tlv('01',account_no)
    merchant=tlv('00','A000000727')+tlv('01',beneficiary)+tlv('02','QRIBFTTA')
    payload=tlv('00','01')+tlv('01','12')+tlv('38',merchant)+tlv('53','704')+tlv('54',amount)+tlv('58','VN')+tlv('62',tlv('08',reference))+'6304'
    return payload+f'{binascii.crc_hqx(payload.encode("ascii"),0xffff):04X}'


def register(app, db, roles, scope, body, field, audit):
    def scoped_trip(conn, trip_id, lock=False):
        where, params = scope()
        return conn.execute('SELECT t.* FROM trips t WHERE t.id=%s AND '+where+
                            (' FOR UPDATE' if lock else ''), (trip_id,)+params).fetchone()

    def present(row):
        if row:
            row['qr_url'] = f"/api/trips/{row['trip_id']}/payment/{row['id']}/qr"
        return row

    @app.get('/api/trips/<int:trip_id>/payment/<int:payment_id>/qr')
    def payment_qr(trip_id,payment_id):
        with db() as conn:
            trip=scoped_trip(conn,trip_id)
            if not trip:
                return jsonify(error='Không tìm thấy chuyến'),404
            row=conn.execute('SELECT * FROM payment_attempts WHERE id=%s AND trip_id=%s',(payment_id,trip_id)).fetchone()
            if not row:
                return jsonify(error='Không tìm thấy thanh toán'),404
            if row['status']!='awaiting_transfer' or trip['status']=='cancelled':
                return jsonify(error='QR không còn hiệu lực cho yêu cầu thanh toán này'),409
        payload=vietqr_payload(row['bank_bin'],row['account_no'],int(row['amount']),row['reference'])
        image=qrcode.make(payload,error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=8,border=4)
        output=io.BytesIO();image.save(output,format='PNG')
        return Response(output.getvalue(),mimetype='image/png')

    @app.route('/api/profile/avatar', methods=['GET','PUT', 'DELETE'])
    @roles('driver','customer','admin')
    def avatar_upload():
        role=g.user['role'];profile_id=g.user['id'] if role=='admin' else g.user[role+'_id']
        table={'driver':'driver_avatars','customer':'customer_avatars','admin':'admin_avatars'}[role]
        column=role+'_id'
        if request.method=='GET':
            with db() as conn:
                row=conn.execute('SELECT content FROM '+table+' WHERE '+column+'=%s',(profile_id,)).fetchone()
            if not row:return jsonify(error='Chưa có ảnh đại diện'),404
            return Response(bytes(row['content']),mimetype='image/jpeg')
        if request.method == 'DELETE':
            with db() as conn:
                conn.execute('DELETE FROM '+table+' WHERE '+column+'=%s', (profile_id,))
                audit(conn, 'remove_avatar', role, profile_id)
            return jsonify(avatar_url=None)
        uploaded = request.files.get('image')
        if not uploaded:
            return jsonify(error='Chọn ảnh JPG, PNG hoặc WebP từ thư viện'), 400
        raw = uploaded.read(2*1024*1024+1)
        if len(raw)>2*1024*1024:
            return jsonify(error='Ảnh phải nhỏ hơn 2 MB'), 413
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as photo:
                    if photo.format not in {'JPEG', 'PNG', 'WEBP'} or photo.width*photo.height>16_000_000:
                        raise ValueError('image')
                    photo.load()
                    photo = ImageOps.exif_transpose(photo).convert('RGB')
                    photo = ImageOps.fit(photo, (512, 512), method=Image.Resampling.LANCZOS)
                    output = io.BytesIO()
                    photo.save(output, format='JPEG', quality=85)
        except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombWarning, Image.DecompressionBombError):
            return jsonify(error='Ảnh không hợp lệ. Chọn JPG, PNG hoặc WebP, tối đa 16 triệu điểm ảnh.'), 400
        version = secrets.token_hex(12)
        with db() as conn:
            conn.execute('INSERT INTO '+table+'('+column+',content,version) VALUES (%s,%s,%s) ON CONFLICT('+column+') DO UPDATE SET content=excluded.content,version=excluded.version,updated_at=now()',
                         (profile_id, output.getvalue(), version))
            audit(conn, 'upload_avatar', role, profile_id)
        return jsonify(avatar_url=f'/api/drivers/{profile_id}/avatar?v={version}' if role=='driver' else f'/api/profile/avatar?v={version}')

    @app.get('/api/drivers/<int:driver_id>/avatar')
    def avatar_get(driver_id):
        with db() as conn:
            allowed = g.user['role']=='admin' or (g.user['role']=='driver' and g.user['driver_id']==driver_id)
            if g.user['role']=='customer':
                allowed = conn.execute('SELECT 1 FROM trips WHERE customer_id=%s AND driver_id=%s LIMIT 1',
                                       (g.user['customer_id'], driver_id)).fetchone() is not None
            if not allowed:
                return jsonify(error='Không có quyền xem ảnh này'), 403
            row = conn.execute('SELECT content FROM driver_avatars WHERE driver_id=%s', (driver_id,)).fetchone()
        if not row:
            return jsonify(error='Chưa có ảnh đại diện'), 404
        return Response(bytes(row['content']), mimetype='image/jpeg')

    @app.errorhandler(413)
    def too_large(error):
        if re.fullmatch(r'/api/admin/promotions/[0-9]+/image',request.path):
            return jsonify(error='Ảnh quảng cáo tối đa 10 MB.'),413
        return jsonify(error='Tệp tải lên quá lớn. Chọn ảnh nhỏ hơn 2 MB.'), 413

    def bank_fields(data):
        values = tuple(field(data,key,limit) for key,limit in
                       [('bank_bin',6),('bank_name',100),('account_no',19),('account_name',100)])
        if not re.fullmatch(r'[0-9]{6}',values[0]) or not re.fullmatch(r'[0-9]{6,19}',values[2]) or not re.fullmatch(r'[A-Z ]{5,100}',values[3]):
            raise ValueError('bank_account')
        return values

    @app.route('/api/admin/bank-accounts', methods=['GET','POST'])
    @roles('admin')
    def bank_accounts():
        with db() as conn:
            if request.method=='POST':
                values=bank_fields(body())
                row=conn.execute('''INSERT INTO bank_accounts(bank_bin,bank_name,account_no,account_name)
                    VALUES (%s,%s,%s,%s) ON CONFLICT (bank_bin,account_no) DO NOTHING RETURNING *''',values).fetchone()
                if not row:
                    return jsonify(error='Tài khoản ngân hàng này đã có trong danh sách.'),409
                audit(conn,'create_bank_account','bank_account',row['id'])
                return jsonify(row),201
            rows=conn.execute('''SELECT b.*,b.id=s.bank_account_id AS selected FROM bank_accounts b
                CROSS JOIN payment_settings s WHERE s.id=1 ORDER BY selected DESC,b.id''').fetchall()
        return jsonify(rows)

    @app.post('/api/admin/bank-accounts/<int:account_id>/select')
    @roles('admin')
    def select_bank_account(account_id):
        with db() as conn:
            conn.execute('SELECT id FROM payment_settings WHERE id=1 FOR UPDATE')
            bank=conn.execute('SELECT * FROM bank_accounts WHERE id=%s FOR UPDATE',(account_id,)).fetchone()
            if not bank:
                return jsonify(error='Không tìm thấy tài khoản ngân hàng.'),404
            conn.execute('''UPDATE payment_settings SET bank_account_id=%s,bank_bin=%s,bank_name=%s,
                account_no=%s,account_name=%s WHERE id=1''',
                (account_id,bank['bank_bin'],bank['bank_name'],bank['account_no'],bank['account_name']))
            audit(conn,'select_bank_account','bank_account',account_id)
        return jsonify(bank)

    @app.route('/api/payment/settings', methods=['GET', 'PATCH'])
    def settings():
        if request.method=='PATCH' and g.user['role']!='admin':
            return jsonify(error='Chỉ admin được đổi tài khoản nhận tiền'), 403
        with db() as conn:
            if request.method=='PATCH':
                data=body()
                bank_bin,bank_name,account_no,account_name=bank_fields(data)
                current=conn.execute('SELECT bank_account_id FROM payment_settings WHERE id=1 FOR UPDATE').fetchone()
                duplicate=conn.execute('SELECT id FROM bank_accounts WHERE bank_bin=%s AND account_no=%s',
                                       (bank_bin,account_no)).fetchone()
                if duplicate and duplicate['id']!=current['bank_account_id']:
                    return jsonify(error='Tài khoản ngân hàng này đã có trong danh sách.'),409
                conn.execute('UPDATE bank_accounts SET bank_bin=%s,bank_name=%s,account_no=%s,account_name=%s WHERE id=%s',
                             (bank_bin,bank_name,account_no,account_name,current['bank_account_id']))
                conn.execute('UPDATE payment_settings SET bank_bin=%s,bank_name=%s,account_no=%s,account_name=%s WHERE id=1',
                             (bank_bin,bank_name,account_no,account_name))
                audit(conn,'update_payment_settings','payment_settings',1)
            row=conn.execute('SELECT * FROM payment_settings WHERE id=1').fetchone()
        return jsonify(row)

    @app.route('/api/trips/<int:trip_id>/payment', methods=['GET','POST'])
    def trip_payment(trip_id):
        if request.method=='POST' and g.user['role']!='customer':
            return jsonify(error='Chỉ khách hàng của chuyến được tạo chuyển khoản'),403
        with db() as conn:
            trip=scoped_trip(conn,trip_id,request.method=='POST')
            if not trip:
                return jsonify(error='Không tìm thấy chuyến'),404
            row=conn.execute('SELECT * FROM payment_attempts WHERE trip_id=%s ORDER BY id DESC LIMIT 1',(trip_id,)).fetchone()
            if request.method=='POST':
                if trip['status']=='cancelled':
                    return jsonify(error='Chuyến đã hủy không thể thanh toán'),409
                if not row or row['status']=='failed':
                    bank=conn.execute('SELECT * FROM payment_settings WHERE id=1').fetchone()
                    amount=trip['fare'].quantize(1,rounding=ROUND_HALF_UP)
                    if amount<=0:
                        return jsonify(error='Chuyến không có phí cần chuyển khoản'),409
                    reference=f"TX{trip_id} {secrets.token_hex(4).upper()}"
                    row=conn.execute('''INSERT INTO payment_attempts(trip_id,amount,reference,bank_bin,bank_name,account_no,account_name)
                        VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                                     (trip_id,amount,reference,bank['bank_bin'],bank['bank_name'],bank['account_no'],bank['account_name'])).fetchone()
                    conn.execute("UPDATE trips SET payment='transfer' WHERE id=%s",(trip_id,))
                    audit(conn,'create_transfer','trip',trip_id)
            history=conn.execute('SELECT id,status,note,created_at,submitted_at,reviewed_at FROM payment_attempts WHERE trip_id=%s ORDER BY id DESC',(trip_id,)).fetchall()
        return jsonify(payment=present(row),history=history,method=trip['payment'] if request.method=='GET' else 'transfer')

    @app.post('/api/trips/<int:trip_id>/payment/submit')
    @roles('customer')
    def submit_transfer(trip_id):
        data=body()
        with db() as conn:
            trip=scoped_trip(conn,trip_id,True)
            if not trip:
                return jsonify(error='Không tìm thấy chuyến'),404
            if trip['status']=='cancelled':
                return jsonify(error='Chuyến đã hủy không thể thanh toán'),409
            row=conn.execute('SELECT * FROM payment_attempts WHERE trip_id=%s ORDER BY id DESC LIMIT 1 FOR UPDATE',(trip_id,)).fetchone()
            if not row or row['id']!=int(data.get('payment_id',0)):
                return jsonify(error='Yêu cầu thanh toán không còn hiện hành. Mở lại thanh toán.'),409
            if row['status']=='pending':
                return jsonify(payment=present(row))
            if row['status']!='awaiting_transfer':
                return jsonify(error='Không thể gửi xác nhận cho giao dịch này'),409
            row=conn.execute("UPDATE payment_attempts SET status='pending',submitted_at=now() WHERE id=%s RETURNING *",(row['id'],)).fetchone()
            audit(conn,'submit_transfer','trip',trip_id)
        return jsonify(payment=present(row))

    @app.get('/api/admin/payments')
    @roles('admin')
    def payments():
        status=request.args.get('status','')
        if status and status not in {'awaiting_transfer','pending','success','failed'}:
            raise ValueError('status')
        with db() as conn:
            rows=conn.execute('''SELECT p.*,c.name customer_name,t.status trip_status FROM payment_attempts p
                JOIN trips t ON t.id=p.trip_id JOIN customers c ON c.id=t.customer_id
                WHERE (%s='' OR p.status=%s) ORDER BY p.id DESC LIMIT 200''',(status,status)).fetchall()
        return jsonify(rows)

    @app.get('/api/payments')
    @roles('customer')
    def own_payments():
        with db() as conn:
            rows=conn.execute('''SELECT p.*,t.pickup,t.destination,t.status trip_status FROM payment_attempts p
                JOIN trips t ON t.id=p.trip_id WHERE t.customer_id=%s ORDER BY p.id DESC LIMIT 200''',
                              (g.user['customer_id'],)).fetchall()
        return jsonify(rows)

    @app.patch('/api/admin/payments/<int:payment_id>')
    @roles('admin')
    def reconcile(payment_id):
        data=body()
        decision=data.get('status')
        if decision not in {'success','failed'}:
            raise ValueError('status')
        note=field(data,'note',500)
        with db() as conn:
            link=conn.execute('SELECT trip_id FROM payment_attempts WHERE id=%s',(payment_id,)).fetchone()
            if not link:
                return jsonify(error='Không tìm thấy thanh toán'),404
            # Same lock order as customer submission and cancellation.
            trip=conn.execute('SELECT * FROM trips WHERE id=%s FOR UPDATE',(link['trip_id'],)).fetchone()
            row=conn.execute('SELECT * FROM payment_attempts WHERE id=%s FOR UPDATE',(payment_id,)).fetchone()
            if row['status']!='pending':
                return jsonify(error='Chỉ xác nhận giao dịch đang chờ đối soát; kết quả đã lưu không thể thay đổi'),409
            if decision=='success' and trip['status']=='cancelled':
                return jsonify(error='Chuyến đã hủy. Kiểm tra và xử lý hoàn tiền ngoài hệ thống.'),409
            row=conn.execute('''UPDATE payment_attempts SET status=%s,note=%s,reviewed_at=now(),reviewed_by=%s
                WHERE id=%s RETURNING *''',(decision,note,g.user['id'],payment_id)).fetchone()
            audit(conn,'transfer_'+decision,'trip',trip['id'])
        return jsonify(payment=present(row))
