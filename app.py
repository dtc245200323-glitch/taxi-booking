import os
import time
import logging
import hashlib
import secrets
import hmac
import re
import csv
import io
from datetime import date, timedelta
from functools import wraps
from urllib.parse import urlsplit
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from flask import Flask, request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__, static_url_path='', static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 + 64 * 1024
logging.basicConfig(level=logging.INFO)
REQUESTS = Counter('taxi_http_requests_total', 'HTTP requests', ['method', 'route', 'status'])
LATENCY = Histogram('taxi_http_request_duration_seconds', 'Request duration', ['route'])
DATABASE_URL = os.environ['DATABASE_URL']
DUMMY_HASH = generate_password_hash(secrets.token_hex(16))
COOKIE_SECURE = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'

def db():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

@app.before_request
def before():
    request.started = time.monotonic()
    public = {'/api/health', '/api/auth/login', '/api/auth/register','/api/auth/forgot','/api/auth/reset'}
    if request.path.startswith('/api/') and request.path not in public:
        token = request.cookies.get('taxi_session', '')
        with db() as conn:
            g.user = conn.execute('''SELECT u.id,u.username,u.role,u.customer_id,u.driver_id,s.csrf_token
                FROM sessions s JOIN users u ON u.id=s.user_id
                WHERE s.token_hash=%s AND s.expires_at>now() AND u.active''',
                (hashlib.sha256(token.encode()).hexdigest(),)).fetchone() if token else None
        if not g.user:
            return jsonify(error='Vui lòng đăng nhập'), 401
        if request.method not in {'GET','HEAD','OPTIONS'} and not hmac.compare_digest(
                request.headers.get('X-CSRF-Token', ''), g.user['csrf_token']):
            return jsonify(error='Phiên thao tác không hợp lệ, vui lòng tải lại trang'), 403
    if request.path.startswith('/api/') and request.method not in {'GET','HEAD','OPTIONS'}:
        origin = request.headers.get('Origin')
        if origin and urlsplit(origin).netloc != request.host:
            return jsonify(error='Nguồn yêu cầu không hợp lệ'), 403

def roles(*allowed):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if g.user['role'] not in allowed:
                return jsonify(error='Bạn không có quyền thực hiện thao tác này'), 403
            return fn(*args, **kwargs)
        return wrapped
    return decorate

def scope():
    if g.user['role'] == 'customer':
        return 't.customer_id=%s', (g.user['customer_id'],)
    if g.user['role'] == 'driver':
        return 't.driver_id=%s', (g.user['driver_id'],)
    return 'TRUE', ()

def credentials(data):
    username = field(data, 'username', 50).lower()
    password = data.get('password')
    if not re.fullmatch(r'[a-z0-9_.-]{3,50}', username) or not isinstance(password, str) or not 8 <= len(password) <= 128:
        raise ValueError('credentials')
    return username, password

def create_user(conn, data, role, profile_id):
    username, password = credentials(data)
    conn.execute('''INSERT INTO users(username,password_hash,role,customer_id,driver_id)
        VALUES (%s,%s,%s,%s,%s)''', (username, generate_password_hash(password), role,
        profile_id if role=='customer' else None, profile_id if role=='driver' else None))

def audit(conn, action, entity, entity_id):
    conn.execute('INSERT INTO audit_logs(actor_id,action,entity,entity_id) VALUES (%s,%s,%s,%s)',
                 (g.user['id'], action, entity, entity_id))

def trip_filters():
    where, params = scope()
    params = list(params)
    status = request.args.get('status', '')
    if status:
        if status not in {'pending','assigned','ongoing','completed','cancelled'}:
            raise ValueError('status')
        where += ' AND t.status=%s'
        params.append(status)
    query = request.args.get('q', '').strip()
    if len(query)>100:
        raise ValueError('q')
    if query:
        where += " AND (t.id::text=%s OR c.name ILIKE %s OR c.phone ILIKE %s OR t.pickup ILIKE %s OR t.destination ILIKE %s OR d.name ILIKE %s OR d.plate ILIKE %s)"
        params.extend([query]+['%'+query+'%']*6)
    for key, column in [('customer_id','t.customer_id'),('driver_id','t.driver_id')]:
        if request.args.get(key):
            where += ' AND '+column+'=%s'
            params.append(int(request.args[key]))
    for key, op in [('from','>='),('to','<')]:
        if request.args.get(key):
            day = date.fromisoformat(request.args[key])
            if key=='to':
                day += timedelta(days=1)
            where += ' AND t.created_at '+op+' (%s::date::timestamp AT TIME ZONE \'Asia/Ho_Chi_Minh\')'
            params.append(day)
    return where, tuple(params)

TRIP_JOIN = ''' FROM trips t JOIN customers c ON c.id=t.customer_id
    LEFT JOIN drivers d ON d.id=t.driver_id '''

@app.post('/api/auth/login')
def login():
    data = body()
    username = field(data, 'username', 50).lower()
    password = data.get('password')
    if not isinstance(password, str) or len(password)>128:
        raise ValueError('password')
    with db() as conn:
        user = conn.execute('SELECT * FROM users WHERE username=%s FOR UPDATE', (username,)).fetchone()
        valid = check_password_hash(user['password_hash'] if user else DUMMY_HASH, password)
        if not user or not valid or not user['active']:
            return jsonify(error='Tên đăng nhập hoặc mật khẩu không đúng'), 401
        token, csrf = secrets.token_hex(32), secrets.token_hex(32)
        conn.execute('DELETE FROM sessions WHERE expires_at<=now()')
        old_token = request.cookies.get('taxi_session', '')
        if old_token:
            conn.execute('DELETE FROM sessions WHERE token_hash=%s', (hashlib.sha256(old_token.encode()).hexdigest(),))
        conn.execute('INSERT INTO sessions(token_hash,user_id,csrf_token) VALUES (%s,%s,%s)',
                     (hashlib.sha256(token.encode()).hexdigest(), user['id'], csrf))
    response = jsonify(user={k:user[k] for k in ['id','username','role','customer_id','driver_id']}, csrf_token=csrf)
    response.set_cookie('taxi_session', token, httponly=True, secure=COOKIE_SECURE, samesite='Lax', max_age=86400)
    return response

@app.get('/api/auth/me')
def me():
    return jsonify(user={k:v for k,v in g.user.items() if k!='csrf_token'}, csrf_token=g.user['csrf_token'])

@app.post('/api/auth/logout')
def logout():
    with db() as conn:
        if g.user['role']=='driver':
            conn.execute('SELECT id FROM drivers WHERE id=%s FOR UPDATE',(g.user['driver_id'],))
            conn.execute('DELETE FROM driver_locations WHERE driver_id=%s',(g.user['driver_id'],))
        conn.execute('DELETE FROM sessions WHERE token_hash=%s',
                     (hashlib.sha256(request.cookies['taxi_session'].encode()).hexdigest(),))
    response = jsonify(status='ok')
    response.delete_cookie('taxi_session', httponly=True, secure=COOKIE_SECURE, samesite='Lax')
    return response

@app.post('/api/auth/register')
def register():
    data = body()
    if 'role' in data and data['role'] != 'customer':
        return jsonify(error='Chỉ được đăng ký tài khoản khách hàng'), 403
    with db() as conn:
        row = conn.execute('INSERT INTO customers(name,phone) VALUES (%s,%s) RETURNING *',
                           (field(data,'name',100),field(data,'phone',20))).fetchone()
        create_user(conn, data, 'customer', row['id'])
    return jsonify(status='ok'), 201

@app.after_request
def after(response):
    route = request.url_rule.rule if request.url_rule else 'unmatched'
    REQUESTS.labels(request.method, route, response.status_code).inc()
    LATENCY.labels(route).observe(time.monotonic() - request.started)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    tile_origin=urlsplit(os.getenv('MAP_TILE_URL') or 'https://tile.openstreetmap.org/{z}/{x}/{y}.png')
    tile_source=tile_origin.scheme+'://'+tile_origin.netloc if tile_origin.scheme in {'https','http'} and re.fullmatch(r'[a-zA-Z0-9.:-]+',tile_origin.netloc) else 'https://tile.openstreetmap.org'
    response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' blob: "+tile_source+"; style-src 'self'; script-src 'self'; frame-ancestors 'none'"
    if request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    app.logger.info('%s %s status=%s', request.method, route, response.status_code)
    return response

@app.errorhandler(psycopg.Error)
def database_error(error):
    app.logger.exception('Database operation failed')
    if isinstance(error, psycopg.IntegrityError):
        return jsonify(error='Dữ liệu trùng hoặc tham chiếu không hợp lệ'), 409
    return jsonify(error='Cơ sở dữ liệu tạm thời không khả dụng'), 503

@app.errorhandler(400)
def bad_request(error):
    return jsonify(error='Dữ liệu không hợp lệ'), 400

def body():
    data = request.get_json()
    if not isinstance(data, dict):
        from werkzeug.exceptions import BadRequest
        raise BadRequest()
    return data

def field(data, key, limit=200):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError(key)
    return value.strip()

@app.errorhandler(ValueError)
@app.errorhandler(TypeError)
@app.errorhandler(InvalidOperation)
def invalid(error):
    return jsonify(error='Kiểm tra các trường bắt buộc và giá trị nhập'), 400

@app.get('/')
def index():
    return app.send_static_file('index.html')

@app.get('/api/health')
def health():
    with db() as conn:
        conn.execute('SELECT 1')
    return jsonify(status='ok')

@app.get('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

@app.get('/api/customers')
@roles('admin')
def customers():
    with db() as conn:
        return jsonify(conn.execute('''SELECT c.*,u.id user_id,u.username,u.active account_active
            FROM customers c LEFT JOIN users u ON u.customer_id=c.id ORDER BY c.id DESC''').fetchall())

@app.post('/api/customers')
@roles('admin')
def add_customer():
    data = body()
    with db() as conn:
        row = conn.execute('INSERT INTO customers(name,phone) VALUES (%s,%s) RETURNING *',
                           (field(data, 'name', 100), field(data, 'phone', 20))).fetchone()
        create_user(conn, data, 'customer', row['id'])
        audit(conn, 'create', 'customer', row['id'])
    return jsonify(row), 201

@app.get('/api/drivers')
@roles('admin')
def drivers():
    with db() as conn:
        return jsonify(conn.execute('''SELECT d.*,u.id user_id,u.username,u.active account_active,
            v.seats,v.model vehicle_model,v.active vehicle_active
            FROM drivers d LEFT JOIN users u ON u.driver_id=d.id
            LEFT JOIN vehicles v ON v.driver_id=d.id ORDER BY d.id DESC''').fetchall())

@app.post('/api/drivers')
@roles('admin')
def add_driver():
    data = body()
    with db() as conn:
        row = conn.execute('INSERT INTO drivers(name,phone,plate) VALUES (%s,%s,%s) RETURNING *',
                           (field(data, 'name', 100), field(data, 'phone', 20), field(data, 'plate', 20))).fetchone()
        create_user(conn, data, 'driver', row['id'])
        if data.get('license'):
            conn.execute('UPDATE drivers SET license=%s WHERE id=%s',(field(data,'license',50),row['id']))
        conn.execute('INSERT INTO vehicles(driver_id,plate,model,seats) VALUES (%s,%s,%s,%s)',
            (row['id'],row['plate'],field(data,'model',100) if data.get('model') else 'Toyota Vios',int(data.get('seats',4))))
        audit(conn, 'create', 'driver', row['id'])
    return jsonify(row), 201

@app.get('/api/trips')
def trips():
    where, params = trip_filters()
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 500))
    if page<1 or not 1<=limit<=500:
        raise ValueError('pagination')
    with db() as conn:
        return jsonify(conn.execute('''SELECT t.*, c.name customer_name, d.name driver_name, d.plate
            ''' + TRIP_JOIN + ' WHERE '+where+' ORDER BY t.id DESC LIMIT %s OFFSET %s', params+(limit,(page-1)*limit)).fetchall())

@app.post('/api/trips')
@roles('admin','customer')
def add_trip():
    data = body()
    customer_id = g.user['customer_id'] if g.user['role']=='customer' else int(data.get('customer_id', 0))
    if g.user['role']=='customer' and 'customer_id' in data and int(data['customer_id']) != customer_id:
        return jsonify(error='Không được đặt chuyến cho khách khác'), 403
    distance = Decimal('1') if data.get('route_quote_id') else Decimal(str(data.get('distance', 0)))
    seats = int(data.get('seats',4))
    if seats not in {1,4,7} or data.get('payment','cash') not in {'cash','transfer'}:
        raise ValueError('vehicle/payment')
    if not distance.is_finite() or not 0 < distance <= 1000 or distance != distance.quantize(Decimal('0.01')):
        raise ValueError('distance')
    with db() as conn:
        route=consume_quote(conn,data['route_quote_id'],g.user['id']) if data.get('route_quote_id') else None
        if route:distance=Decimal(route['distance_km'])
        customer = conn.execute('SELECT * FROM customers WHERE id=%s FOR UPDATE', (customer_id,)).fetchone()
        if not customer or customer['archived']:
            return jsonify(error='Khách hàng không tồn tại hoặc đã lưu trữ'), 409
        fare = conn.execute('SELECT * FROM fares WHERE seats=%s',(seats,)).fetchone()
        subtotal=(fare['base']+distance*fare['per_km']).quantize(Decimal('1'),rounding=ROUND_HALF_UP)
        promo_code, reduction=discount(conn,data.get('promo_code'),customer_id,subtotal,lock=True)
        row = conn.execute('''INSERT INTO trips(customer_id,pickup,destination,distance,fare,seats,base_fare,per_km,payment)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
            (customer_id, field(data, 'pickup'), field(data, 'destination'), distance,
             subtotal-reduction,seats,fare['base'],fare['per_km'],data.get('payment','cash'))).fetchone()
        conn.execute('UPDATE trips SET promo_code=%s,discount_amount=%s WHERE id=%s',(promo_code,reduction,row['id']))
        row['promo_code']=promo_code;row['discount_amount']=reduction
        record_status(conn,row['id'],None,'pending')
        if route:
            row=conn.execute('''UPDATE trips SET pickup_lat=%s,pickup_lng=%s,destination_lat=%s,destination_lng=%s,
                route_geometry=%s,route_duration_seconds=%s,location_source='map' WHERE id=%s RETURNING *''',
                (route['pickup']['lat'],route['pickup']['lng'],route['destination']['lat'],route['destination']['lng'],
                 Jsonb(route['geometry']),route['duration_seconds'],row['id'])).fetchone()
        audit(conn, 'create', 'trip', row['id'])
    return jsonify(row), 201

@app.patch('/api/trips/<int:trip_id>')
def update_trip(trip_id):
    data = body()
    status = data.get('status')
    transitions = {'pending': {'assigned', 'cancelled'}, 'assigned': {'ongoing', 'cancelled'},
                   'ongoing': {'completed'}, 'completed': set(), 'cancelled': set()}
    with db() as conn:
        where, params = scope()
        trip = conn.execute('SELECT t.* FROM trips t WHERE t.id=%s AND '+where+' FOR UPDATE', (trip_id,)+params).fetchone()
        if not trip:
            return jsonify(error='Không tìm thấy chuyến'), 404
        if status=='cancelled' and conn.execute("SELECT 1 FROM payment_attempts WHERE trip_id=%s AND status IN ('pending','success')",(trip_id,)).fetchone():
            return jsonify(error='Chuyến có thanh toán đang xác nhận hoặc đã nhận tiền. Liên hệ admin xử lý trước khi hủy.'),409
        role = g.user['role']
        if role=='customer' and status!='cancelled':
            return jsonify(error='Khách hàng chỉ có thể hủy chuyến trước khi di chuyển'), 403
        if role=='customer' and trip['status']!='pending':
            return jsonify(error='Chỉ được hủy khi chuyến đang chờ tài xế nhận'),409
        if role=='driver' and status not in {'ongoing','completed'}:
            return jsonify(error='Tài xế chỉ được bắt đầu hoặc hoàn thành chuyến của mình'), 403
        if role!='admin' and 'driver_id' in data:
            return jsonify(error='Chỉ admin được phân công tài xế'), 403
        reassign = role=='admin' and status=='assigned' and trip['status']=='assigned'
        if status not in transitions[trip['status']] and not reassign:
            return jsonify(error='Chuyển trạng thái không hợp lệ'), 409
        if status=='cancelled':
            conn.execute("UPDATE payment_attempts SET status='failed',note='Chuyến đã hủy trước khi gửi xác nhận chuyển khoản',reviewed_at=now() WHERE trip_id=%s AND status='awaiting_transfer'",(trip_id,))
        driver_id = trip['driver_id']
        if status == 'assigned':
            driver_id = int(data.get('driver_id', 0))
            # Lock both drivers in ID order when changing an assignment.
            ids = sorted(set([driver_id]+([trip['driver_id']] if trip['driver_id'] else [])))
            locked = conn.execute('SELECT * FROM drivers WHERE id=ANY(%s) ORDER BY id FOR UPDATE', (ids,)).fetchall()
            driver = next((d for d in locked if d['id']==driver_id), None)
            account = conn.execute('SELECT active FROM users WHERE driver_id=%s', (driver_id,)).fetchone()
            vehicle = conn.execute('SELECT * FROM vehicles WHERE driver_id=%s AND active',(driver_id,)).fetchone()
            if not vehicle or vehicle['seats']!=trip['seats']:
                return jsonify(error='Phương tiện không phù hợp loại xe của chuyến'),409
            if not driver or driver['archived'] or (account and not account['active']) or (driver['status']!='available' and driver_id!=trip['driver_id']):
                return jsonify(error='Tài xế không sẵn sàng'), 409
            if reassign and trip['driver_id']!=driver_id:
                conn.execute("UPDATE drivers SET status='available' WHERE id=%s", (trip['driver_id'],))
            conn.execute("UPDATE drivers SET status='busy' WHERE id=%s", (driver_id,))
            conn.execute('UPDATE trips SET vehicle_plate=%s,vehicle_model=%s,arrived_at=NULL WHERE id=%s',
                         (vehicle['plate'],vehicle['model'],trip_id))
        if status in {'completed', 'cancelled'} and driver_id:
            conn.execute("UPDATE drivers SET status='available' WHERE id=%s", (driver_id,))
        row = conn.execute('UPDATE trips SET status=%s,driver_id=%s WHERE id=%s RETURNING *',
                           (status, driver_id, trip_id)).fetchone()
        record_status(conn,trip_id,trip['status'],status)
        stamp={'assigned':'accepted_at','ongoing':'started_at','completed':'completed_at','cancelled':'cancelled_at'}[status]
        row=conn.execute('UPDATE trips SET '+stamp+'=now() WHERE id=%s RETURNING *',(trip_id,)).fetchone()
        audit(conn, 'reassign' if reassign else status, 'trip', trip_id)
    return jsonify(row)

@app.get('/api/stats')
def stats():
    where, params = trip_filters()
    with db() as conn:
        return jsonify(conn.execute('''SELECT count(*) total,
          count(*) FILTER (WHERE t.status IN ('pending','assigned','ongoing')) active,
          count(*) FILTER (WHERE t.status='completed') completed,
          count(*) FILTER (WHERE t.status='cancelled') cancelled,
          coalesce(sum(t.fare) FILTER (WHERE t.status='completed'),0) revenue '''+TRIP_JOIN+' WHERE '+where, params).fetchone())

@app.route('/api/customers/<int:profile_id>', methods=['PATCH','DELETE'])
@roles('admin')
def edit_customer(profile_id):
    return edit_profile('customers', 'customer', profile_id)

@app.route('/api/drivers/<int:profile_id>', methods=['PATCH','DELETE'])
@roles('admin')
def edit_driver(profile_id):
    return edit_profile('drivers', 'driver', profile_id)

def edit_profile(table, entity, profile_id):
    data = body() if request.method=='PATCH' else {'archived':True}
    allowed = {'name','phone','archived'} | ({'plate','status','license'} if entity=='driver' else set())
    if not data or set(data)-allowed:
        raise ValueError('fields')
    with db() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(220023)')
        row = conn.execute('SELECT * FROM '+table+' WHERE id=%s FOR UPDATE', (profile_id,)).fetchone()
        if not row:
            return jsonify(error='Không tìm thấy hồ sơ'), 404
        changes = {}
        for key in ['name','phone']+(['plate'] if entity=='driver' else []):
            if key in data:
                changes[key] = field(data, key, 100 if key=='name' else 20)
        if 'license' in data:
            changes['license']=field(data,'license',50)
        if 'archived' in data:
            if not isinstance(data['archived'], bool):
                raise ValueError('archived')
            changes['archived'] = data['archived']
        if 'status' in data:
            if data['status'] not in {'available','offline'} or row['archived']:
                return jsonify(error='Chỉ được đổi tài xế đang hoạt động sang sẵn sàng/nghỉ'), 409
            changes['status'] = data['status']
        if changes.get('archived') or 'status' in changes:
            active = conn.execute('SELECT 1 FROM trips WHERE '+entity+'_id=%s AND status IN (\'pending\',\'assigned\',\'ongoing\') LIMIT 1', (profile_id,)).fetchone()
            if active:
                return jsonify(error='Hồ sơ đang có chuyến hoạt động, hãy xử lý chuyến trước'), 409
        if entity=='driver' and 'archived' in changes:
            changes['status'] = 'offline' if changes['archived'] else 'available'
        if changes.get('archived'):
            conn.execute('UPDATE users SET active=false WHERE '+entity+'_id=%s', (profile_id,))
            conn.execute('DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE '+entity+'_id=%s)', (profile_id,))
        if entity=='driver' and 'plate' in changes:
            if row['status']=='busy':
                return jsonify(error='Không đổi phương tiện khi tài xế đang có chuyến'),409
            conn.execute('UPDATE vehicles SET plate=%s WHERE driver_id=%s',(changes['plate'],profile_id))
        assignments = ','.join(k+'=%s' for k in changes)
        row = conn.execute('UPDATE '+table+' SET '+assignments+' WHERE id=%s RETURNING *', tuple(changes.values())+(profile_id,)).fetchone()
        audit(conn, 'archive' if changes.get('archived') else 'update', entity, profile_id)
    return jsonify(row)

@app.get('/api/admin/users')
@roles('admin')
def users():
    with db() as conn:
        return jsonify(conn.execute('''SELECT u.id,u.username,u.role,u.active,u.customer_id,u.driver_id,
            coalesce(c.name,d.name,u.username) name,coalesce(c.archived,d.archived,false) archived
            FROM users u LEFT JOIN customers c ON c.id=u.customer_id
            LEFT JOIN drivers d ON d.id=u.driver_id ORDER BY u.id DESC''').fetchall())

@app.post('/api/admin/users')
@roles('admin')
def add_user():
    data = body()
    role = data.get('role')
    if role not in {'admin','driver','customer'}:
        raise ValueError('role')
    username, password = credentials(data)
    with db() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(220023)')
        profile_id = None
        if role!='admin':
            profile_id = int(data.get('profile_id',0))
            table = 'customers' if role=='customer' else 'drivers'
            profile = conn.execute('SELECT * FROM '+table+' WHERE id=%s FOR UPDATE', (profile_id,)).fetchone()
            if not profile or profile['archived']:
                return jsonify(error='Hồ sơ không tồn tại hoặc đã lưu trữ'), 409
        row = conn.execute('''INSERT INTO users(username,password_hash,role,customer_id,driver_id)
            VALUES (%s,%s,%s,%s,%s) RETURNING id,username,role,active''',
            (username,generate_password_hash(password),role,profile_id if role=='customer' else None,
             profile_id if role=='driver' else None)).fetchone()
        audit(conn, 'create', 'user', row['id'])
    return jsonify(row), 201

@app.patch('/api/admin/users/<int:user_id>')
@roles('admin')
def edit_user(user_id):
    data = body()
    if not data or set(data)-{'active','password'}:
        raise ValueError('fields')
    if 'active' in data and not isinstance(data['active'],bool):
        raise ValueError('active')
    if 'password' in data and (not isinstance(data['password'],str) or not 8<=len(data['password'])<=128):
        raise ValueError('password')
    with db() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(220023)')
        target = conn.execute('SELECT * FROM users WHERE id=%s FOR UPDATE', (user_id,)).fetchone()
        if not target:
            return jsonify(error='Không tìm thấy tài khoản'), 404
        if data.get('active') is False:
            if user_id==g.user['id']:
                return jsonify(error='Không được khóa tài khoản đang đăng nhập'), 409
            if target['role']=='admin' and conn.execute("SELECT count(*) n FROM users WHERE role='admin' AND active").fetchone()['n']<=1:
                return jsonify(error='Phải giữ ít nhất một admin hoạt động'), 409
        if target['role']!='admin':
            table = 'drivers' if target['role']=='driver' else 'customers'
            profile = conn.execute('SELECT * FROM '+table+' WHERE id=%s FOR UPDATE', (target[target['role']+'_id'],)).fetchone()
            if data.get('active') and profile['archived']:
                return jsonify(error='Hãy khôi phục hồ sơ trước khi mở tài khoản'), 409
            if target['role']=='driver' and profile['status']=='busy' and (data.get('active') is False or 'password' in data):
                return jsonify(error='Tài xế đang có chuyến, hãy xử lý chuyến trước khi thu hồi phiên'), 409
        if 'active' in data:
            conn.execute('UPDATE users SET active=%s WHERE id=%s', (data['active'],user_id))
        if 'password' in data:
            conn.execute('UPDATE users SET password_hash=%s WHERE id=%s', (generate_password_hash(data['password']),user_id))
        if data.get('active') is False or 'password' in data:
            conn.execute('DELETE FROM sessions WHERE user_id=%s', (user_id,))
        audit(conn, 'reset_password' if 'password' in data else ('unlock' if data['active'] else 'lock'), 'user', user_id)
    return jsonify(status='ok')

@app.get('/api/trips/<int:trip_id>')
def trip_detail(trip_id):
    where, params = scope()
    with db() as conn:
        row = conn.execute('''SELECT t.*,c.name customer_name,c.phone customer_phone,
            d.name driver_name,d.phone driver_phone,d.plate'''+TRIP_JOIN+' WHERE t.id=%s AND '+where,
            (trip_id,)+params).fetchone()
        if row:
            row['review']=conn.execute('SELECT stars,comment,created_at FROM reviews WHERE trip_id=%s',(trip_id,)).fetchone()
    if not row:
        return jsonify(error='Không tìm thấy chuyến'),404
    return jsonify(row)

@app.patch('/api/admin/trips/<int:trip_id>')
@roles('admin')
def edit_trip(trip_id):
    data = body()
    pickup, destination = field(data,'pickup'), field(data,'destination')
    distance = Decimal(str(data.get('distance',0)))
    if not distance.is_finite() or not 0<distance<=1000 or distance!=distance.quantize(Decimal('0.01')):
        raise ValueError('distance')
    with db() as conn:
        trip = conn.execute('SELECT * FROM trips WHERE id=%s FOR UPDATE',(trip_id,)).fetchone()
        if not trip:
            return jsonify(error='Không tìm thấy chuyến'),404
        if trip['status']!='pending':
            return jsonify(error='Chỉ được sửa hành trình khi chuyến đang chờ điều phối'),409
        if trip.get('promo_code'):
            return jsonify(error='Chuyến có mã giảm giá giữ nguyên giá và tuyến đã đặt'),409
        if trip['location_source']=='map':
            return jsonify(error='Chuyến đặt từ bản đồ giữ nguyên tọa độ và tuyến đường; không sửa bằng khoảng cách thủ công.'),409
        if conn.execute("SELECT 1 FROM payment_attempts WHERE trip_id=%s AND status IN ('awaiting_transfer','pending','success')",(trip_id,)).fetchone():
            return jsonify(error='Không thể đổi giá của chuyến đã tạo yêu cầu chuyển khoản'),409
        row = conn.execute('''UPDATE trips SET pickup=%s,destination=%s,distance=%s,fare=%s
            WHERE id=%s RETURNING *''',(pickup,destination,distance,trip['base_fare']+distance*trip['per_km'],trip_id)).fetchone()
        audit(conn,'edit_route','trip',trip_id)
    return jsonify(row)

@app.get('/api/admin/reports')
@roles('admin')
def reports():
    where,params = trip_filters()
    with db() as conn:
        daily = conn.execute('''SELECT (t.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS "day",
            count(*) trips,coalesce(sum(t.fare) FILTER(WHERE t.status='completed'),0) revenue
            '''+TRIP_JOIN+' WHERE '+where+' GROUP BY 1 ORDER BY 1 DESC LIMIT 30',params).fetchall()
        by_driver = conn.execute('''SELECT d.id,d.name,d.plate,count(t.id) trips,
            count(t.id) FILTER(WHERE t.status='completed') completed,
            coalesce(sum(t.fare) FILTER(WHERE t.status='completed'),0) revenue
            '''+TRIP_JOIN+' WHERE '+where+' AND d.id IS NOT NULL GROUP BY d.id ORDER BY revenue DESC,d.id',params).fetchall()
        counts = conn.execute('''SELECT
            (SELECT count(*) FROM customers WHERE NOT archived) customers,
            (SELECT count(*) FROM drivers WHERE NOT archived) drivers,
            (SELECT count(*) FROM drivers d LEFT JOIN users u ON u.driver_id=d.id
                WHERE NOT d.archived AND d.status='available' AND coalesce(u.active,true)) available_drivers,
            (SELECT count(*) FROM users WHERE NOT active) locked_accounts''').fetchone()
    return jsonify(daily=daily,drivers=by_driver,counts=counts)

@app.get('/api/admin/audit')
@roles('admin')
def audit_logs():
    page = int(request.args.get('page',1))
    if page<1:
        raise ValueError('page')
    with db() as conn:
        return jsonify(conn.execute('''SELECT a.*,u.username actor FROM audit_logs a
            JOIN users u ON u.id=a.actor_id ORDER BY a.id DESC LIMIT 50 OFFSET %s''',((page-1)*50,)).fetchall())

@app.get('/api/admin/export')
@roles('admin')
def export():
    where,params = trip_filters()
    with db() as conn:
        rows = conn.execute('''SELECT t.id,c.name customer,d.name driver,d.plate,t.pickup,
            t.destination,t.distance,t.fare,t.status,t.created_at'''+TRIP_JOIN+' WHERE '+where+' ORDER BY t.id DESC',params).fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID','Customer','Driver','Plate','Pickup','Destination','Km','Fare VND','Status','Created at'])
    for row in rows:
        values = [str(v) if v is not None else '' for v in row.values()]
        writer.writerow(["'"+v if v.startswith(('=','+','-','@','\t','\r','\n')) else v for v in values])
    return '\ufeff'+output.getvalue(),200,{'Content-Type':'text/csv; charset=utf-8','Content-Disposition':'attachment; filename=taxi-trips.csv'}

def record_status(conn,trip_id,old,new):
    conn.execute('INSERT INTO trip_status_history(trip_id,old_status,new_status,actor_id) VALUES (%s,%s,%s,%s)',
                 (trip_id,old,new,g.user['id']))

@app.route('/api/profile',methods=['GET','PATCH'])
def profile():
    role=g.user['role']
    if role=='admin':
        return jsonify(id=g.user['id'],name=g.user['username'],username=g.user['username'],role=role)
    table='customers' if role=='customer' else 'drivers'
    profile_id=g.user[role+'_id']
    with db() as conn:
        if request.method=='PATCH':
            data=body()
            if set(data)-{'name','phone','email'}:
                raise ValueError('fields')
            name,phone=field(data,'name',100),field(data,'phone',20)
            email=data.get('email','').strip()
            if email and (len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email)):
                raise ValueError('email')
            conn.execute('UPDATE '+table+' SET name=%s,phone=%s,email=%s WHERE id=%s',(name,phone,email or None,profile_id))
            audit(conn,'update_profile',role,profile_id)
        row=conn.execute('SELECT * FROM '+table+' WHERE id=%s',(profile_id,)).fetchone()
        if role=='driver':
            row['vehicle']=conn.execute('SELECT * FROM vehicles WHERE driver_id=%s',(profile_id,)).fetchone()
            avatar=conn.execute('SELECT version FROM driver_avatars WHERE driver_id=%s',(profile_id,)).fetchone()
            row['avatar_url']='/api/drivers/'+str(profile_id)+'/avatar?v='+avatar['version'] if avatar else None
        row.update(username=g.user['username'],role=role)
    return jsonify(row)

@app.post('/api/auth/password')
def change_password():
    data=body()
    password=data.get('password')
    if not isinstance(password,str) or not 8<=len(password)<=128:
        raise ValueError('password')
    with db() as conn:
        user=conn.execute('SELECT * FROM users WHERE id=%s FOR UPDATE',(g.user['id'],)).fetchone()
        if not isinstance(data.get('old_password'),str) or not check_password_hash(user['password_hash'],data['old_password']):
            return jsonify(error='Mật khẩu hiện tại không đúng'),400
        conn.execute('UPDATE users SET password_hash=%s WHERE id=%s',(generate_password_hash(password),user['id']))
        conn.execute('DELETE FROM sessions WHERE user_id=%s',(user['id'],))
        audit(conn,'change_password','user',user['id'])
    response=jsonify(status='ok')
    response.delete_cookie('taxi_session')
    return response

@app.get('/api/fares')
def fare_list():
    with db() as conn:
        return jsonify(conn.execute('SELECT * FROM fares ORDER BY seats').fetchall())

@app.patch('/api/admin/fares/<int:seats>')
@roles('admin')
def update_fare(seats):
    data=body()
    base,per_km=Decimal(str(data.get('base',-1))),Decimal(str(data.get('per_km',-1)))
    if seats not in {1,4,7} or any(not x.is_finite() or x<0 or x>1000000 or x!=x.quantize(Decimal('1')) for x in [base,per_km]):
        raise ValueError('fare')
    with db() as conn:
        row=conn.execute('UPDATE fares SET base=%s,per_km=%s WHERE seats=%s RETURNING *',(base,per_km,seats)).fetchone()
        audit(conn,'update_fare','fare',seats)
    return jsonify(row)

@app.get('/api/driver/queue')
@roles('driver')
def driver_queue():
    with db() as conn:
        return jsonify(conn.execute('''SELECT t.id,t.pickup,t.destination,t.distance,t.fare,t.seats,t.created_at,t.location_source,c.name customer_name
            FROM trips t JOIN customers c ON c.id=t.customer_id
            JOIN vehicles v ON v.driver_id=%s AND v.active AND v.seats=t.seats
            WHERE t.status='pending' AND t.driver_id IS NULL ORDER BY t.created_at DESC LIMIT 100''',(g.user['driver_id'],)).fetchall())

@app.post('/api/driver/trips/<int:trip_id>/accept')
@roles('driver')
def accept_trip(trip_id):
    driver_id=g.user['driver_id']
    with db() as conn:
        trip=conn.execute('SELECT * FROM trips WHERE id=%s FOR UPDATE',(trip_id,)).fetchone()
        driver=conn.execute('SELECT * FROM drivers WHERE id=%s FOR UPDATE',(driver_id,)).fetchone()
        if not trip:
            return jsonify(error='Không tìm thấy chuyến'),404
        if trip['status']!='pending' or trip['driver_id']:
            return jsonify(error='Chuyến đã được nhận hoặc đã hủy'),409
        vehicle=conn.execute('SELECT * FROM vehicles WHERE driver_id=%s AND active',(driver_id,)).fetchone()
        if driver['status']!='available' or driver['archived'] or not vehicle or vehicle['seats']!=trip['seats']:
            return jsonify(error='Bạn chưa sẵn sàng hoặc phương tiện không phù hợp'),409
        row=conn.execute('''UPDATE trips SET status='assigned',driver_id=%s,accepted_at=now(),vehicle_plate=%s,vehicle_model=%s
            WHERE id=%s RETURNING *''',(driver_id,vehicle['plate'],vehicle['model'],trip_id)).fetchone()
        conn.execute("UPDATE drivers SET status='busy' WHERE id=%s",(driver_id,))
        record_status(conn,trip_id,'pending','assigned')
        audit(conn,'accept','trip',trip_id)
    return jsonify(row)

@app.patch('/api/driver/status')
@roles('driver')
def driver_status():
    status=body().get('status')
    if status not in {'available','offline'}:
        raise ValueError('status')
    with db() as conn:
        driver=conn.execute('SELECT * FROM drivers WHERE id=%s FOR UPDATE',(g.user['driver_id'],)).fetchone()
        if driver['status']=='busy':
            return jsonify(error='Hãy hoàn thành chuyến trước khi đổi trạng thái'),409
        row=conn.execute('UPDATE drivers SET status=%s WHERE id=%s RETURNING *',(status,driver['id'])).fetchone()
        audit(conn,'availability','driver',driver['id'])
    return jsonify(row)

@app.post('/api/driver/trips/<int:trip_id>/arrive')
@roles('driver')
def arrived(trip_id):
    with db() as conn:
        row=conn.execute("UPDATE trips SET arrived_at=coalesce(arrived_at,now()) WHERE id=%s AND driver_id=%s AND status='assigned' RETURNING *",
                         (trip_id,g.user['driver_id'])).fetchone()
        if not row:
            return jsonify(error='Chuyến không thuộc bạn hoặc không ở trạng thái đã nhận'),409
        audit(conn,'arrive','trip',trip_id)
    return jsonify(row)

@app.get('/api/driver/income')
@roles('driver')
def income():
    where,params=trip_filters()
    with db() as conn:
        daily=conn.execute('''SELECT (coalesce(t.completed_at,t.created_at) AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS "day",
            count(*) trips,sum(t.fare) revenue'''+TRIP_JOIN+" WHERE "+where+" AND t.status='completed' GROUP BY 1 ORDER BY 1 DESC",params).fetchall()
        today=conn.execute('''SELECT count(*) trips,coalesce(sum(fare),0) revenue FROM trips
            WHERE driver_id=%s AND status='completed' AND
            (coalesce(completed_at,created_at) AT TIME ZONE 'Asia/Ho_Chi_Minh')::date=(now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date''',(g.user['driver_id'],)).fetchone()
    return jsonify(daily=daily,today=today)

@app.get('/api/trips/<int:trip_id>/history')
def history(trip_id):
    where,params=scope()
    with db() as conn:
        if not conn.execute('SELECT t.id FROM trips t WHERE t.id=%s AND '+where,(trip_id,)+params).fetchone():
            return jsonify(error='Không tìm thấy chuyến'),404
        return jsonify(conn.execute('''SELECT h.id,h.old_status,h.new_status,h.created_at,u.role actor_role
            FROM trip_status_history h LEFT JOIN users u ON u.id=h.actor_id WHERE trip_id=%s ORDER BY h.id''',(trip_id,)).fetchall())

@app.post('/api/trips/<int:trip_id>/review')
@roles('customer')
def review(trip_id):
    data=body()
    stars=int(data.get('stars',0));comment=data.get('comment','')
    if not 1<=stars<=5 or not isinstance(comment,str) or len(comment)>1000:
        raise ValueError('review')
    with db() as conn:
        trip=conn.execute("SELECT id FROM trips WHERE id=%s AND customer_id=%s AND status='completed'",(trip_id,g.user['customer_id'])).fetchone()
        if not trip:
            return jsonify(error='Chỉ được đánh giá chuyến của mình đã hoàn thành'),409
        conn.execute('INSERT INTO reviews(trip_id,customer_id,stars,comment) VALUES (%s,%s,%s,%s)',(trip_id,g.user['customer_id'],stars,comment.strip()))
        audit(conn,'review','trip',trip_id)
    return jsonify(status='ok'),201

@app.route('/api/complaints',methods=['GET','POST'])
@roles('customer','admin')
def complaints():
    with db() as conn:
        if request.method=='POST':
            if g.user['role']!='customer':
                return jsonify(error='Chỉ khách gửi phản ánh'),403
            data=body();trip_id=int(data.get('trip_id',0))
            if not conn.execute('SELECT id FROM trips WHERE id=%s AND customer_id=%s',(trip_id,g.user['customer_id'])).fetchone():
                return jsonify(error='Không tìm thấy chuyến'),404
            row=conn.execute('INSERT INTO complaints(trip_id,customer_id,content) VALUES (%s,%s,%s) RETURNING *',
                             (trip_id,g.user['customer_id'],field(data,'content',2000))).fetchone()
            audit(conn,'complaint','trip',trip_id)
            return jsonify(row),201
        where='TRUE' if g.user['role']=='admin' else 'p.customer_id=%s'
        params=() if g.user['role']=='admin' else (g.user['customer_id'],)
        return jsonify(conn.execute('SELECT p.*,c.name customer_name FROM complaints p JOIN customers c ON c.id=p.customer_id WHERE '+where+' ORDER BY p.id DESC',params).fetchall())

@app.patch('/api/admin/complaints/<int:complaint_id>')
@roles('admin')
def resolve_complaint(complaint_id):
    data=body();status=data.get('status');resolution=data.get('resolution','')
    if status not in {'open','processing','resolved'} or not isinstance(resolution,str) or len(resolution)>2000 or (status=='resolved' and not resolution.strip()):
        raise ValueError('complaint')
    with db() as conn:
        row=conn.execute('UPDATE complaints SET status=%s,resolution=%s WHERE id=%s RETURNING *',(status,resolution,complaint_id)).fetchone()
        if not row:return jsonify(error='Không tìm thấy phản ánh'),404
        audit(conn,'resolve','complaint',complaint_id)
    return jsonify(row)

@app.get('/api/admin/reviews')
@roles('admin')
def review_list():
    with db() as conn:
        return jsonify(conn.execute('SELECT r.*,c.name customer_name FROM reviews r JOIN customers c ON c.id=r.customer_id ORDER BY r.created_at DESC LIMIT 500').fetchall())

@app.route('/api/driver/requests',methods=['GET','POST'])
@roles('driver')
def vehicle_requests():
    with db() as conn:
        if request.method=='POST':
            data=body();seats=int(data.get('seats',0))
            if seats not in {1,4,7}:raise ValueError('seats')
            row=conn.execute('''INSERT INTO driver_requests(driver_id,model,plate,seats,license)
                VALUES (%s,%s,%s,%s,%s) RETURNING *''',(g.user['driver_id'],field(data,'model',100),field(data,'plate',20),seats,field(data,'license',50))).fetchone()
            audit(conn,'request_vehicle','driver',g.user['driver_id'])
            return jsonify(row),201
        return jsonify(conn.execute('SELECT * FROM driver_requests WHERE driver_id=%s ORDER BY id DESC',(g.user['driver_id'],)).fetchall())

@app.get('/api/admin/requests')
@roles('admin')
def request_list():
    with db() as conn:
        return jsonify(conn.execute('SELECT r.*,d.name driver_name FROM driver_requests r JOIN drivers d ON d.id=r.driver_id ORDER BY r.id DESC').fetchall())

@app.patch('/api/admin/requests/<int:request_id>')
@roles('admin')
def approve_request(request_id):
    data=body();status=data.get('status');note=data.get('note','')
    if status not in {'approved','rejected'} or not isinstance(note,str) or len(note)>500:
        raise ValueError('status')
    with db() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(220023)')
        row=conn.execute('SELECT * FROM driver_requests WHERE id=%s FOR UPDATE',(request_id,)).fetchone()
        if not row:return jsonify(error='Không tìm thấy yêu cầu'),404
        if row['status']!='pending':return jsonify(error='Yêu cầu đã xử lý'),409
        driver=conn.execute('SELECT * FROM drivers WHERE id=%s FOR UPDATE',(row['driver_id'],)).fetchone()
        if status=='approved':
            if driver['status']=='busy' or driver['archived']:return jsonify(error='Tài xế đang bận hoặc hồ sơ lưu trữ'),409
            conn.execute('''INSERT INTO vehicles(driver_id,plate,model,seats) VALUES (%s,%s,%s,%s)
                ON CONFLICT(driver_id) DO UPDATE SET plate=excluded.plate,model=excluded.model,seats=excluded.seats,active=true''',
                (driver['id'],row['plate'],row['model'],row['seats']))
            conn.execute('UPDATE drivers SET plate=%s,license=%s WHERE id=%s',(row['plate'],row['license'],driver['id']))
        conn.execute('UPDATE driver_requests SET status=%s,note=%s WHERE id=%s',(status,note,request_id))
        audit(conn,status,'request',request_id)
    return jsonify(status='ok')

@app.route('/api/admin/vehicles',methods=['GET','POST'])
@roles('admin')
def vehicles():
    with db() as conn:
        if request.method=='GET':
            return jsonify(conn.execute('SELECT v.*,d.name driver_name FROM vehicles v LEFT JOIN drivers d ON d.id=v.driver_id ORDER BY v.id DESC').fetchall())
        data=body();seats=int(data.get('seats',0));driver_id=int(data['driver_id']) if data.get('driver_id') else None
        if seats not in {1,4,7}:raise ValueError('seats')
        conn.execute('SELECT pg_advisory_xact_lock(220023)')
        if driver_id:
            driver=conn.execute('SELECT * FROM drivers WHERE id=%s FOR UPDATE',(driver_id,)).fetchone()
            if not driver or driver['archived'] or driver['status']=='busy':return jsonify(error='Tài xế không hợp lệ/đang bận'),409
            if conn.execute('SELECT id FROM vehicles WHERE driver_id=%s',(driver_id,)).fetchone():return jsonify(error='Tài xế đã có phương tiện; hãy sửa xe hiện có'),409
        row=conn.execute('INSERT INTO vehicles(driver_id,plate,model,seats) VALUES (%s,%s,%s,%s) RETURNING *',
            (driver_id,field(data,'plate',20),field(data,'model',100),seats)).fetchone()
        if driver_id:conn.execute('UPDATE drivers SET plate=%s WHERE id=%s',(row['plate'],driver_id))
        audit(conn,'create','vehicle',row['id'])
    return jsonify(row),201

@app.route('/api/admin/vehicles/<int:vehicle_id>',methods=['PATCH','DELETE'])
@roles('admin')
def edit_vehicle(vehicle_id):
    data=body() if request.method=='PATCH' else {'active':False}
    if not data or set(data)-{'plate','model','seats','active','driver_id'}:raise ValueError('fields')
    with db() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(220023)')
        row=conn.execute('SELECT * FROM vehicles WHERE id=%s FOR UPDATE',(vehicle_id,)).fetchone()
        if not row:return jsonify(error='Không tìm thấy phương tiện'),404
        new_id=int(data['driver_id']) if data.get('driver_id') else None
        if 'driver_id' not in data:new_id=row['driver_id']
        ids=sorted(set(i for i in [row['driver_id'],new_id] if i))
        drivers=conn.execute('SELECT * FROM drivers WHERE id=ANY(%s) ORDER BY id FOR UPDATE',(ids,)).fetchall()
        if any(d['status']=='busy' for d in drivers) or (new_id and not any(d['id']==new_id and not d['archived'] for d in drivers)):
            return jsonify(error='Tài xế đang bận hoặc không hợp lệ'),409
        updates={'driver_id':new_id}
        for key in ['plate','model']:
            if key in data:updates[key]=field(data,key,20 if key=='plate' else 100)
        if 'seats' in data:
            updates['seats']=int(data['seats'])
            if updates['seats'] not in {1,4,7}:raise ValueError('seats')
        if 'active' in data:
            if not isinstance(data['active'],bool):raise ValueError('active')
            updates['active']=data['active']
        if new_id!=row['driver_id'] and row['driver_id']:
            conn.execute("UPDATE drivers SET status='offline' WHERE id=%s",(row['driver_id'],))
        if new_id and conn.execute('SELECT id FROM vehicles WHERE driver_id=%s AND id!=%s',(new_id,vehicle_id)).fetchone():
            return jsonify(error='Tài xế đã có phương tiện khác'),409
        row=conn.execute('UPDATE vehicles SET '+','.join(k+'=%s' for k in updates)+' WHERE id=%s RETURNING *',tuple(updates.values())+(vehicle_id,)).fetchone()
        if new_id:conn.execute('UPDATE drivers SET plate=%s WHERE id=%s',(row['plate'],new_id))
        audit(conn,'update','vehicle',vehicle_id)
    return jsonify(row)

@app.get('/api/admin/overview')
@roles('admin')
def overview():
    with db() as conn:
        states=conn.execute('''SELECT d.status,count(*) count FROM drivers d LEFT JOIN users u ON u.driver_id=d.id
            WHERE NOT d.archived AND coalesce(u.active,true) GROUP BY d.status''').fetchall()
        week=conn.execute('''SELECT days.day::date AS "day",count(t.id) trips FROM
            generate_series((now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date-6,(now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date,interval '1 day') days(day)
            LEFT JOIN trips t ON (t.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date=days.day::date GROUP BY 1 ORDER BY 1''').fetchall()
    return jsonify(states=states,week=week)

@app.post('/api/auth/forgot')
def forgot_password():
    import smtplib
    from email.message import EmailMessage
    data=body();username=field(data,'username',50).lower();email=field(data,'email',254)
    if not os.getenv('SMTP_HOST'):
        return jsonify(error='Chưa cấu hình gửi email. Liên hệ admin để đặt lại mật khẩu.'),503
    with db() as conn:
        user=conn.execute('''SELECT u.id,u.active,coalesce(c.email,d.email) email,u.role FROM users u
            LEFT JOIN customers c ON c.id=u.customer_id LEFT JOIN drivers d ON d.id=u.driver_id
            WHERE u.username=%s FOR UPDATE OF u''',(username,)).fetchone()
        stored_email=(os.getenv('ADMIN_RESET_EMAIL') if user and user['role']=='admin' else user['email'] if user else None)
        if user and user['active'] and stored_email and hmac.compare_digest(stored_email.lower(),email.lower()):
            token=secrets.token_hex(32)
            conn.execute('DELETE FROM password_resets WHERE user_id=%s OR expires_at<=now()',(user['id'],))
            conn.execute('INSERT INTO password_resets(token_hash,user_id) VALUES (%s,%s)',(hashlib.sha256(token.encode()).hexdigest(),user['id']))
            link=os.environ.get('PUBLIC_URL','http://127.0.0.1:8080').rstrip('/')+'/#reset='+token
            message=EmailMessage();message['Subject']='Taxi Booking - Đặt lại mật khẩu'
            message['From']=os.environ.get('SMTP_FROM',os.environ.get('SMTP_USER','taxi@localhost'))
            message['To']=stored_email;message.set_content('Liên kết có hiệu lực 30 phút, chỉ dùng một lần:\n'+link)
            try:
                with smtplib.SMTP(os.environ['SMTP_HOST'],int(os.getenv('SMTP_PORT','587')),timeout=10) as server:
                    if os.getenv('SMTP_TLS','true').lower()=='true':server.starttls()
                    if os.getenv('SMTP_USER'):server.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD'])
                    server.send_message(message)
            except (OSError,smtplib.SMTPException):
                conn.rollback()
                return jsonify(error='Dịch vụ email tạm thời không khả dụng'),503
    return jsonify(message='Nếu tài khoản/email phù hợp, bạn sẽ nhận được liên kết đặt lại mật khẩu.')

@app.post('/api/auth/reset')
def reset_password():
    data=body();token=field(data,'token',64);password=data.get('password')
    if not isinstance(password,str) or not 8<=len(password)<=128:raise ValueError('password')
    with db() as conn:
        row=conn.execute('''SELECT p.user_id FROM password_resets p JOIN users u ON u.id=p.user_id
            WHERE p.token_hash=%s AND p.expires_at>now() AND u.active FOR UPDATE OF p,u''',
            (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if not row:return jsonify(error='Liên kết không hợp lệ hoặc đã hết hạn'),400
        conn.execute('UPDATE users SET password_hash=%s WHERE id=%s',(generate_password_hash(password),row['user_id']))
        conn.execute('DELETE FROM sessions WHERE user_id=%s',(row['user_id'],))
        conn.execute('DELETE FROM password_resets WHERE user_id=%s',(row['user_id'],))
    return jsonify(status='ok')

from media_payments import register
register(app, db, roles, scope, body, field, audit)

from maps import register_maps, consume_quote
register_maps(app, db, roles, scope, body, field, audit)

from promotions import register_promotions, discount
register_promotions(app,db,roles,body,audit)
