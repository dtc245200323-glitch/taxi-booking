import re
import io
import base64
import hashlib
from PIL import Image, ImageOps, UnidentifiedImageError
from decimal import Decimal, ROUND_HALF_UP
from flask import request, jsonify, g, Response


def discount(conn, code, customer_id, subtotal, lock=False):
    if not code:
        return None, Decimal(0)
    code = str(code).strip().upper()
    row = conn.execute("SELECT * FROM promotions WHERE code=%s" + (' FOR UPDATE' if lock else ''), (code,)).fetchone()
    if not row or not row['active'] or not conn.execute('SELECT %s::timestamptz>now() valid', (row['expires_at'],)).fetchone()['valid']:
        raise ValueError('Mã giảm giá không tồn tại hoặc đã hết hạn')
    used = conn.execute("SELECT count(*) n FROM trips WHERE promo_code=%s AND status!='cancelled'", (code,)).fetchone()['n']
    personal = conn.execute("SELECT count(*) n FROM trips WHERE promo_code=%s AND customer_id=%s AND status!='cancelled'", (code, customer_id)).fetchone()['n']
    if used >= row['usage_limit'] or personal >= row['per_customer_limit'] or subtotal < row['min_fare']:
        raise ValueError('Mã đã hết lượt hoặc giá chuyến chưa đạt mức tối thiểu')
    amount = subtotal * row['value'] / 100 if row['kind'] == 'percent' else row['value']
    return code, min(subtotal, amount, row['max_discount']).quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def register_promotions(app, db, roles, body, audit):
    def with_image_url(row):
        if row.get('image_data'):
            version=hashlib.sha256(row['image_data'].encode()).hexdigest()[:16]
            row['image_url']=f"/api/promotions/{row['id']}/image?v={version}"
        else:
            row['image_url']=None
        return row

    @app.get('/api/promotions/<int:promo_id>/image')
    def promotion_image(promo_id):
        with db() as conn:
            row=conn.execute('SELECT image_data FROM promotions WHERE id=%s',(promo_id,)).fetchone()
        if not row or not row['image_data']:
            return jsonify(error='Chưa có ảnh quảng cáo'),404
        return Response(base64.b64decode(row['image_data'].split(',',1)[1]),mimetype='image/jpeg')

    @app.get('/api/public/promotions')
    def public_listing():
        with db() as conn:
            return jsonify(conn.execute('''SELECT p.code,p.title,p.kind,p.value,p.max_discount,p.min_fare,p.per_customer_limit,p.expires_at
                FROM promotions p WHERE p.active AND p.expires_at>now() AND
                (SELECT count(*) FROM trips t WHERE t.promo_code=p.code AND t.status!='cancelled')<p.usage_limit
                ORDER BY p.id LIMIT 5''').fetchall())

    @app.get('/api/promotions')
    def listing():
        with db() as conn:
            query = 'SELECT * FROM promotions'
            if g.user['role'] != 'admin':
                query += ' WHERE active AND expires_at>now()'
            return jsonify([with_image_url(row) for row in conn.execute(query + ' ORDER BY id DESC').fetchall()])

    @app.get('/api/promotions/saved')
    @roles('customer')
    def saved():
        with db() as conn:
            return jsonify([with_image_url(row) for row in conn.execute("SELECT p.* FROM saved_promotions s JOIN promotions p ON p.id=s.promotion_id WHERE s.user_id=%s ORDER BY s.saved_at DESC",(g.user['id'],)).fetchall()])

    @app.post('/api/promotions/<int:promotion_id>/save')
    @roles('customer')
    def save(promotion_id):
        with db() as conn:
            row=conn.execute('SELECT id FROM promotions WHERE id=%s AND active AND expires_at>now() FOR SHARE',(promotion_id,)).fetchone()
            if not row:return jsonify(error='Mã không còn khả dụng'),404
            conn.execute('INSERT INTO saved_promotions(user_id,promotion_id) VALUES (%s,%s) ON CONFLICT DO NOTHING',(g.user['id'],promotion_id))
        return jsonify(status='saved')

    @app.post('/api/promotions/preview')
    @roles('customer')
    def preview():
        data = body()
        seats = int(data.get('seats', 4))
        with db() as conn:
            quote = conn.execute('SELECT payload FROM route_quotes WHERE id=%s AND user_id=%s AND expires_at>now() AND NOT used', (data.get('route_quote_id'), g.user['id'])).fetchone()
            fare = conn.execute('SELECT * FROM fares WHERE seats=%s', (seats,)).fetchone()
            if not quote or not fare:
                raise ValueError('Vui lòng tính tuyến đường trước khi áp dụng mã')
            subtotal = (fare['base'] + Decimal(str(quote['payload']['distance_km'])) * fare['per_km']).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
            code, amount = discount(conn, data.get('code'), g.user['customer_id'], subtotal)
            return jsonify(code=code, discount=amount, subtotal=subtotal, total=subtotal-amount)

    @app.post('/api/admin/promotions')
    @roles('admin')
    def create():
        data = body()
        code = str(data.get('code', '')).strip().upper()
        title = str(data.get('title', '')).strip()
        kind = data.get('kind')
        value, cap, minimum = [Decimal(str(data.get(k, 0))) for k in ('value', 'max_discount', 'min_fare')]
        limit, personal, days = [int(data.get(k, 0)) for k in ('usage_limit', 'per_customer_limit', 'days')]
        if not re.fullmatch(r'[A-Z0-9]{3,30}', code) or not 1<=len(title)<=150 or kind not in {'percent','fixed'}:
            raise ValueError('Thông tin mã không hợp lệ')
        if any(not v.is_finite() or v<0 or v>10000000 for v in (value,cap,minimum)) or value<=0 or cap<=0 or (kind=='percent' and value>100) or not 1<=personal<=limit<=1000000 or not 1<=days<=365:
            raise ValueError('Giá trị hoặc giới hạn mã không hợp lệ')
        with db() as conn:
            row = conn.execute('''INSERT INTO promotions(code,title,kind,value,max_discount,min_fare,usage_limit,per_customer_limit,expires_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,now()+%s*interval '1 day') RETURNING *''', (code,title,kind,value,cap,minimum,limit,personal,days)).fetchone()
            audit(conn,'create','promotion',row['id'])
            return jsonify(row), 201

    @app.post('/api/admin/promotions/<int:promo_id>/image')
    @roles('admin')
    def upload_image(promo_id):
        upload=request.files.get('image')
        if not upload:return jsonify(error='Chọn ảnh quảng cáo trước'),400
        raw=upload.read(10*1024*1024+1)
        if len(raw)>10*1024*1024:return jsonify(error='Ảnh quảng cáo tối đa 10 MB'),400
        try:
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in ('JPEG','PNG','WEBP') or image.width*image.height>16000000:raise ValueError('image')
                image.load();image=ImageOps.exif_transpose(image)
                if image.mode in ('RGBA','LA') or 'transparency' in image.info:
                    rgba=image.convert('RGBA');image=Image.new('RGB',rgba.size,'white');image.paste(rgba,mask=rgba.getchannel('A'))
                else:
                    image=image.convert('RGB')
                image.thumbnail((1200,800))
                output=io.BytesIO();image.save(output,format='JPEG',quality=85)
        except (UnidentifiedImageError,ValueError,OSError,Image.DecompressionBombError):
            return jsonify(error='Chọn ảnh JPG, PNG hoặc WebP hợp lệ'),400
        uri='data:image/jpeg;base64,'+base64.b64encode(output.getvalue()).decode('ascii')
        with db() as conn:
            row=conn.execute('UPDATE promotions SET image_data=%s WHERE id=%s RETURNING id',(uri,promo_id)).fetchone()
            if not row:return jsonify(error='Không tìm thấy mã'),404
            audit(conn,'upload_image','promotion',promo_id)
        return jsonify(status='ok',image_url=with_image_url({'id':promo_id,'image_data':uri})['image_url'])

    @app.patch('/api/admin/promotions/<int:promo_id>')
    @roles('admin')
    def toggle(promo_id):
        active = body().get('active')
        if not isinstance(active, bool):
            raise ValueError('active')
        with db() as conn:
            row = conn.execute('UPDATE promotions SET active=%s WHERE id=%s RETURNING *', (active,promo_id)).fetchone()
            if not row:
                return jsonify(error='Không tìm thấy mã'),404
            audit(conn,'toggle','promotion',promo_id)
            return jsonify(row)
