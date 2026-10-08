import os,uuid,io
from PIL import Image
from app import app,db
suffix=uuid.uuid4().hex[:12]
created=[]
def customer(index):
    c=app.test_client();username='saved'+suffix+str(index);password='Test-Saved-12345'
    r=c.post('/api/auth/register',json={'name':'Saved promotion test','phone':'09'+str(index)+suffix[:7],'username':username,'password':password})
    assert r.status_code==201,r.json
    r=c.post('/api/auth/login',json={'username':username,'password':password});assert r.status_code==200
    created.append(r.json['user']['id'])
    return c,{'X-CSRF-Token':r.json['csrf_token']}
try:
    c,headers=customer(1);other,other_headers=customer(2)
    p=c.get('/api/promotions').json[0]
    assert c.post('/api/promotions/'+str(p['id'])+'/save',json={}).status_code==403
    for _ in range(2):assert c.post('/api/promotions/'+str(p['id'])+'/save',json={},headers=headers).status_code==200
    rows=c.get('/api/promotions/saved').json
    assert len(rows)==1 and rows[0]['id']==p['id']
    assert other.get('/api/promotions/saved').json==[]
    assert c.post('/api/promotions/999999999/save',json={},headers=headers).status_code==404
    driver=app.test_client();r=driver.post('/api/auth/login',json={'username':'taixe','password':os.environ['DRIVER_PASSWORD']})
    assert r.status_code==200
    assert driver.get('/api/promotions/saved').status_code==403
    assert app.test_client().get('/api/promotions/saved').status_code==401
    admin=app.test_client();r=admin.post('/api/auth/login',json={'username':os.getenv('ADMIN_USERNAME','admin'),'password':os.environ['ADMIN_PASSWORD']});assert r.status_code==200
    h={'X-CSRF-Token':r.json['csrf_token']}
    r=admin.post('/api/admin/promotions',json={'code':'IMG'+suffix.upper(),'title':'Test image','kind':'fixed','value':1000,'max_discount':1000,'min_fare':0,'usage_limit':10,'per_customer_limit':1,'days':1},headers=h);assert r.status_code==201
    promo_id=r.json['id']
    try:
        assert admin.post('/api/admin/promotions/'+str(promo_id)+'/image',data={'image':(io.BytesIO(b'invalid'),'x.png')},headers=h).status_code==400
        image=io.BytesIO();Image.new('RGB',(20,20),'blue').save(image,format='PNG');image.seek(0)
        assert admin.post('/api/admin/promotions/'+str(promo_id)+'/image',data={'image':(image,'x.png')},headers=h).status_code==200
        row=next(p for p in c.get('/api/promotions').json if p['id']==promo_id)
        assert row['image_data'].startswith('data:image/jpeg;base64,')
        assert row['image_url'].startswith('/api/promotions/'+str(promo_id)+'/image?v=')
        photo=c.get(row['image_url'])
        assert photo.status_code==200 and photo.mimetype=='image/jpeg'
        assert Image.open(io.BytesIO(photo.data)).getpixel((0,0))[2]>240
        fresh_admin=app.test_client()
        assert fresh_admin.post('/api/auth/login',json={'username':os.getenv('ADMIN_USERNAME','admin'),'password':os.environ['ADMIN_PASSWORD']}).status_code==200
        reloaded=next(p for p in fresh_admin.get('/api/promotions').json if p['id']==promo_id)
        assert reloaded['image_url']==row['image_url']
        assert fresh_admin.get(reloaded['image_url']).data==photo.data
        image=io.BytesIO();Image.new('RGBA',(20,20),(0,0,0,0)).save(image,format='PNG');image.seek(0)
        assert admin.post('/api/admin/promotions/'+str(promo_id)+'/image',data={'image':(image,'transparent.png')},headers=h).status_code==200
        updated=next(p for p in c.get('/api/promotions').json if p['id']==promo_id)
        assert updated['image_url']!=row['image_url']
        assert Image.open(io.BytesIO(c.get(updated['image_url']).data)).getpixel((0,0))==(255,255,255)
        assert c.post('/api/admin/promotions/'+str(promo_id)+'/image',headers=headers).status_code==403
    finally:
        with db() as conn:conn.execute('DELETE FROM promotions WHERE id=%s',(promo_id,))
    print('PASS: saved promotions persistence, idempotency, account isolation, CSRF, roles and validated advertisement images')
finally:
    with db() as conn:
        for user_id in created:
            row=conn.execute('SELECT customer_id FROM users WHERE id=%s',(user_id,)).fetchone()
            conn.execute('DELETE FROM users WHERE id=%s',(user_id,))
            if row:conn.execute('DELETE FROM customers WHERE id=%s',(row['customer_id'],))
