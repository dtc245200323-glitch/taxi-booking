import re
from decimal import Decimal, ROUND_HALF_UP
from flask import request, jsonify, g


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
            return jsonify(conn.execute(query + ' ORDER BY id DESC').fetchall())

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
