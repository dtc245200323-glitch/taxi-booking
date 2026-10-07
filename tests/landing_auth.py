"""Authentication aliases and public promotion data for the landing page."""
import os
import uuid
from app import app,db

admin=app.test_client()
r=admin.post('/api/auth/login',json={'username':os.getenv('ADMIN_USERNAME','admin'),'password':os.environ['ADMIN_PASSWORD']})
assert r.status_code==200
headers={'X-CSRF-Token':r.json['csrf_token']}
suffix=uuid.uuid4().hex[:12];name='landing'+suffix;password='Test-'+suffix;phone='lp'+suffix;email=name+'@example.com'
r=admin.post('/api/customers',json={'name':'Landing test','phone':phone,'username':name,'password':password},headers=headers);assert r.status_code==201
client=app.test_client()
r=client.post('/api/auth/login',json={'username':name,'password':password});assert r.status_code==200
user_id=r.json['user']['id']
r=client.patch('/api/profile',json={'name':'Landing test','phone':phone,'email':email},headers={'X-CSRF-Token':r.json['csrf_token']});assert r.status_code==200
for identity in [name,phone,email.upper()]:
    c=app.test_client();r=c.post('/api/auth/login',json={'username':identity,'password':password});assert r.status_code==200,(identity,r.status_code)
    assert r.json['user']['id']==user_id
    assert 'Max-Age' not in r.headers['Set-Cookie'] and 'HttpOnly' in r.headers['Set-Cookie']
c=app.test_client();r=c.post('/api/auth/login',json={'username':email,'password':password,'remember':'on'});assert r.status_code==200
assert 'Max-Age=2592000' in r.headers['Set-Cookie']
with db() as conn:
    days=conn.execute('SELECT extract(epoch from max(expires_at)-now())/86400 days FROM sessions WHERE user_id=%s',(user_id,)).fetchone()['days']
    assert days>29
for identity in [email,'not-present@example.com']:
    assert app.test_client().post('/api/auth/login',json={'username':identity,'password':'incorrect-password'}).status_code==401
# Duplicate email is not allowed to select an arbitrary user's account.
name2='other'+suffix
r=admin.post('/api/customers',json={'name':'Duplicate alias test','phone':name2,'username':name2,'password':password},headers=headers);assert r.status_code==201
c=app.test_client();r=c.post('/api/auth/login',json={'username':name2,'password':password});assert r.status_code==200
r=c.patch('/api/profile',json={'name':'Duplicate alias test','phone':name2,'email':email},headers={'X-CSRF-Token':r.json['csrf_token']});assert r.status_code==200
assert app.test_client().post('/api/auth/login',json={'username':email,'password':password}).status_code==401
assert app.test_client().post('/api/auth/login',json={'username':name,'password':password}).status_code==200
r=app.test_client().get('/api/public/promotions');assert r.status_code==200
assert all('usage_limit' not in p and 'id' not in p and 'active' not in p for p in r.json)
print('PASS: username/phone/email login, remembered/session cookies, duplicate alias rejection and public promotion fields')
