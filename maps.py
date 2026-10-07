"""Real maps, provider cache, server route quotes and scoped driver GPS."""
import hashlib
import json
import math
import os
import secrets
import threading
import time
import urllib.error
import urllib.request
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode
from flask import jsonify, g
from psycopg.types.json import Jsonb


class MapError(Exception):
    def __init__(self,message,status=503):
        self.message,self.status=message,status


def point(data):
    if not isinstance(data,dict) or isinstance(data.get('lat'),bool) or isinstance(data.get('lng'),bool):
        raise ValueError('coordinates')
    lat,lng=float(data.get('lat')),float(data.get('lng'))
    if not math.isfinite(lat) or not math.isfinite(lng) or not -85<=lat<=85 or not -180<=lng<=180:
        raise ValueError('coordinates')
    return {'lat':round(lat,6),'lng':round(lng,6)}


def consume_quote(conn,quote_id,user_id):
    if not isinstance(quote_id,str) or len(quote_id)!=32:
        raise ValueError('quote')
    row=conn.execute('SELECT * FROM route_quotes WHERE id=%s AND user_id=%s AND expires_at>now() FOR UPDATE',
                     (quote_id,user_id)).fetchone()
    if not row or row['used']:
        raise MapError('Tuyến đường hết hạn hoặc đã đặt chuyến. Bấm Tính tuyến đường để tính lại.',409)
    conn.execute('UPDATE route_quotes SET used=true WHERE id=%s',(quote_id,))
    return row['payload']


_locks={kind:threading.Lock() for kind in ['search','route']}
_last={kind:0 for kind in _locks}


def provider_json(db,kind,url):
    key=hashlib.sha256(url.encode()).hexdigest()
    with db() as conn:
        cached=conn.execute('SELECT payload FROM map_cache WHERE key=%s AND expires_at>now()',(key,)).fetchone()
    if cached:return cached['payload']
    if not _locks[kind].acquire(timeout=.1):
        raise MapError('Dịch vụ bản đồ đang xử lý yêu cầu khác. Thử lại sau vài giây.',429)
    try:
        # Demo providers: globally no more than one request/second per provider.
        time.sleep(max(0,1.05-(time.monotonic()-_last[kind])))
        _last[kind]=time.monotonic()
        headers={'User-Agent':os.getenv('MAP_USER_AGENT','TaxiBookingStudentProject/1.0 (+http://127.0.0.1:8080)'),
                 'Accept':'application/json'}
        req=urllib.request.Request(url,headers=headers)
        try:
            with urllib.request.urlopen(req,timeout=12) as response:
                raw=response.read(2*1024*1024+1)
            if len(raw)>2*1024*1024:raise ValueError('response')
            payload=json.loads(raw)
            if not isinstance(payload,dict):raise ValueError('response')
        except (urllib.error.URLError,TimeoutError,OSError,ValueError):
            raise MapError('Không kết nối được dịch vụ bản đồ. Kiểm tra Internet và thử lại; chưa tính giá theo tuyến đường.') from None
        with db() as conn:
            conn.execute('DELETE FROM map_cache WHERE expires_at<now()')
            conn.execute('''INSERT INTO map_cache(key,payload,expires_at) VALUES (%s,%s,now()+interval '24 hours')
                ON CONFLICT(key) DO UPDATE SET payload=excluded.payload,expires_at=excluded.expires_at''',(key,Jsonb(payload)))
        return payload
    finally:_locks[kind].release()


def register_maps(app,db,roles,scope,body,field,audit):
    @app.errorhandler(MapError)
    def map_error(error):return jsonify(error=error.message),error.status

    @app.get('/api/maps/config')
    def config():
        return jsonify(tile_url=os.getenv('MAP_TILE_URL') or 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                       attribution='© OpenStreetMap contributors',gps_max_age_seconds=120)

    @app.post('/api/maps/search')
    def search():
        data=body();query=field(data,'query',200)
        if len(query)<3:raise ValueError('query')
        bias=point(data.get('near',{'lat':21.0285,'lng':105.8542}))
        base=os.getenv('MAP_SEARCH_URL','https://photon.komoot.io/api/').rstrip('/')+'/'
        result=provider_json(db,'search',base+'?'+urlencode({'q':query,'limit':5,'lat':bias['lat'],'lon':bias['lng']}))
        places=[]
        for feature in result.get('features',[])[:5]:
            try:
                lon,lat=feature['geometry']['coordinates'][:2];p=point({'lat':lat,'lng':lon})
                props=feature['properties'];parts=[props.get(k) for k in ['name','housenumber','street','district','city','state','country']]
                label=', '.join(dict.fromkeys(str(part) for part in parts if part))[:200]
                if label:places.append(dict(p,label=label))
            except (KeyError,TypeError,ValueError,IndexError):continue
        return jsonify(places=places)

    @app.post('/api/maps/route')
    def route():
        data=body();pickup,destination=point(data.get('pickup')),point(data.get('destination'))
        if pickup==destination:raise MapError('Điểm đón và điểm đến phải khác nhau.',422)
        pair=f"{pickup['lng']},{pickup['lat']};{destination['lng']},{destination['lat']}"
        base=os.getenv('MAP_ROUTING_URL','https://router.project-osrm.org/route/v1/driving').rstrip('/')
        result=provider_json(db,'route',base+'/'+pair+'?overview=full&geometries=geojson&steps=false')
        if result.get('code')!='Ok' or not result.get('routes'):
            raise MapError('Không tìm được tuyến ô tô giữa hai điểm. Chọn vị trí khác.',422)
        row=result['routes'][0]
        try:
            metres,seconds=float(row['distance']),float(row['duration'])
            geometry=row['geometry'];coords=geometry['coordinates']
            if not math.isfinite(metres) or not 0<metres<=1_000_000 or not math.isfinite(seconds) or seconds<0 or geometry['type']!='LineString' or not 2<=len(coords)<=50000:
                raise ValueError('route')
            for coord in coords:point({'lng':coord[0],'lat':coord[1]})
        except (KeyError,TypeError,ValueError,IndexError):
            raise MapError('Tuyến đường không hợp lệ hoặc dài quá 1.000 km.',422) from None
        km=max(Decimal('.01'),(Decimal(str(metres))/1000).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
        payload={'pickup':pickup,'destination':destination,'distance_km':str(km),'duration_seconds':round(seconds),'geometry':geometry}
        quote_id=secrets.token_hex(16)
        with db() as conn:
            conn.execute('DELETE FROM route_quotes WHERE expires_at<now()')
            conn.execute('INSERT INTO route_quotes(id,user_id,payload) VALUES (%s,%s,%s)',(quote_id,g.user['id'],Jsonb(payload)))
        return jsonify(dict(payload,quote_id=quote_id,expires_in_seconds=900))

    @app.route('/api/driver/location',methods=['PUT','DELETE'])
    @roles('driver')
    def own_location():
        from flask import request
        driver_id=g.user['driver_id']
        with db() as conn:
            if request.method=='DELETE':
                conn.execute('DELETE FROM driver_locations WHERE driver_id=%s',(driver_id,))
                return jsonify(status='stopped')
            data=body();p=point(data)
            accuracy=float(data.get('accuracy',0))
            if not math.isfinite(accuracy) or not 0<=accuracy<=100000:raise ValueError('accuracy')
            driver=conn.execute('SELECT status FROM drivers WHERE id=%s FOR UPDATE',(driver_id,)).fetchone()
            if not conn.execute('''SELECT 1 FROM sessions s JOIN users u ON u.id=s.user_id
                WHERE s.user_id=%s AND s.csrf_token=%s AND s.expires_at>now() AND u.active''',(g.user['id'],g.user['csrf_token'])).fetchone():
                return jsonify(error='Phiên đăng nhập đã kết thúc'),401
            if not driver or driver['status']=='offline':
                raise MapError('Bật trạng thái nhận chuyến trước khi chia sẻ vị trí.',409)
            conn.execute('''INSERT INTO driver_locations(driver_id,lat,lng,accuracy) VALUES (%s,%s,%s,%s)
                ON CONFLICT(driver_id) DO UPDATE SET lat=excluded.lat,lng=excluded.lng,accuracy=excluded.accuracy,updated_at=now()''',
                         (driver_id,p['lat'],p['lng'],accuracy))
        return jsonify(status='updated')

    @app.get('/api/trips/<int:trip_id>/map')
    def trip_map(trip_id):
        with db() as conn:
            row=conn.execute('''SELECT t.id,t.customer_id,t.driver_id,t.status,t.pickup,t.destination,t.pickup_lat,t.pickup_lng,
                t.destination_lat,t.destination_lng,t.route_geometry,t.route_duration_seconds,t.distance,t.location_source
                FROM trips t WHERE t.id=%s''',(trip_id,)).fetchone()
            if not row:return jsonify(error='Không tìm thấy chuyến'),404
            role=g.user['role'];allowed=role=='admin' or (role=='customer' and row['customer_id']==g.user['customer_id']) or (role=='driver' and row['driver_id']==g.user['driver_id'])
            if not allowed and role=='driver' and row['status']=='pending':
                allowed=conn.execute('''SELECT 1 FROM drivers d JOIN vehicles v ON v.driver_id=d.id
                    JOIN trips t ON t.seats=v.seats WHERE d.id=%s AND t.id=%s AND NOT d.archived AND v.active''',
                                     (g.user['driver_id'],trip_id)).fetchone() is not None
            if not allowed:return jsonify(error='Không có quyền xem bản đồ chuyến này'),403
            row['driver_location']=None
            if row['driver_id'] and row['status'] in {'assigned','ongoing'}:
                row['driver_location']=conn.execute('''SELECT lat,lng,accuracy,updated_at FROM driver_locations
                    WHERE driver_id=%s AND updated_at>now()-interval '120 seconds' ''',(row['driver_id'],)).fetchone()
            row.pop('customer_id');row.pop('driver_id')
        return jsonify(row)
