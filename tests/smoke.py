import json
import os
import time
import urllib.request
import urllib.error
import uuid
from concurrent.futures import ThreadPoolExecutor
from client import Client, config, PASSWORD, BASE

anonymous = Client()
for attempt in range(60):
    try:
        anonymous.call('/api/health')
        break
    except Exception:
        if attempt == 59:
            raise
        time.sleep(2)
anonymous.call('/api/trips', expected=401)
anonymous.call('/api/trips', expected=401, extra_headers={'Authorization':'Bearer old-admin-token'})
anonymous.call('/api/auth/login','POST',{'username':'admin','password':'wrong'},401)
anonymous.call('/api/auth/login','POST',{'username':'admin','password':PASSWORD},403,
               extra_headers={'Origin':'https://attacker.example'})
admin = Client()
assert admin.login(os.getenv('ADMIN_USERNAME', config.get('ADMIN_USERNAME','admin')), PASSWORD)['role']=='admin'
assert all(c.has_nonstandard_attr('HttpOnly') for c in admin.jar)
admin.call('/api/customers','POST',{},403,csrf=False)
suffix = uuid.uuid4().hex[:10]
password = 'Test-pass-' + suffix
customer_data = {'name':'Smoke customer','phone':'c'+suffix,'username':'c'+suffix,'password':password}
customer = admin.call('/api/customers','POST',customer_data,201)
other_data = {**customer_data,'phone':'o'+suffix,'username':'o'+suffix}
anonymous.call('/api/auth/register','POST',{**other_data,'role':'admin'},403)
anonymous.call('/api/auth/register','POST',other_data,201)
anonymous.call('/api/auth/register','POST',other_data,409)
driver_data = {'name':'Smoke driver','phone':'d'+suffix,'plate':'d'+suffix,'username':'d'+suffix,'password':password}
driver = admin.call('/api/drivers','POST',driver_data,201)
other_driver = admin.call('/api/drivers','POST',{**driver_data,'phone':'e'+suffix,'plate':'e'+suffix,'username':'e'+suffix},201)
client, outsider, driver_client, driver_outsider = Client(), Client(), Client(), Client()
assert client.login(customer_data['username'],password)['role']=='customer'
assert outsider.login(other_data['username'],password)['role']=='customer'
assert driver_client.login(driver_data['username'],password)['role']=='driver'
driver_outsider.login('e'+suffix,password)
for person in [client,driver_client]:
    person.call('/api/customers',expected=403)
    person.call('/api/drivers',expected=403)
    person.call('/api/drivers','POST',driver_data,403)
    person.call('/api/customers','POST',customer_data,403)
trip_data = {'pickup':'A','destination':'B','distance':5}
driver_client.call('/api/trips','POST',trip_data,403)
client.call('/api/trips','POST',{**trip_data,'customer_id':customer['id']+10000},403)
for bad in [-1,'NaN',1.234]:
    client.call('/api/trips','POST',{**trip_data,'distance':bad},400)
trip = client.call('/api/trips','POST',trip_data,201)
assert trip['customer_id']==customer['id'] and int(trip['fare'])==75000
other = client.call('/api/trips','POST',trip_data,201)
path = '/api/trips/'+str(trip['id'])
outsider.call(path,'PATCH',{'status':'cancelled'},404)
driver_outsider.call(path,'PATCH',{'status':'ongoing'},404)
assert not any(t['id']==trip['id'] for t in outsider.call('/api/trips'))
assert outsider.call('/api/stats')['total']==0
assert driver_client.call('/api/stats')['total']==0
client.call(path,'PATCH',{'status':'assigned','driver_id':driver['id']},403)
client.call(path,'PATCH',{'status':'ongoing'},403)
admin.call(path,'PATCH',{'status':'completed'},409)
admin.call(path,'PATCH',{'status':'assigned','driver_id':driver['id']})
assert [t['id'] for t in driver_client.call('/api/trips')]==[trip['id']]
driver_client.call(path,'PATCH',{'status':'cancelled'},403)
driver_client.call(path,'PATCH',{'status':'ongoing','driver_id':other_driver['id']},403)
admin.call('/api/trips/'+str(other['id']),'PATCH',{'status':'assigned','driver_id':driver['id']},409)
driver_client.call(path,'PATCH',{'status':'ongoing'})
client.call(path,'PATCH',{'status':'cancelled'},409)
driver_client.call(path,'PATCH',{'status':'completed'})
assert driver_client.call('/api/stats')['revenue']=='75000'
assert client.call('/api/stats')['revenue']=='75000'
admin.call('/api/trips/'+str(other['id']),'PATCH',{'status':'assigned','driver_id':driver['id']})
client.call('/api/trips/'+str(other['id']),'PATCH',{'status':'cancelled'},409)
admin.call('/api/trips/'+str(other['id']),'PATCH',{'status':'cancelled'})
assert next(d for d in admin.call('/api/drivers') if d['id']==driver['id'])['status']=='available'
race_trips = [client.call('/api/trips','POST',trip_data,201) for _ in range(2)]
def assign(t):
    req = urllib.request.Request(BASE+'/api/trips/'+str(t['id']), method='PATCH',
        data=json.dumps({'status':'assigned','driver_id':driver['id']}).encode(),
        headers={'Content-Type':'application/json','X-CSRF-Token':admin.csrf,'Origin':BASE})
    try:
        with admin.opener.open(req,timeout=10) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
with ThreadPoolExecutor(max_workers=2) as pool:
    outcomes = list(pool.map(assign,race_trips))
assert sorted(outcomes)==[200,409], outcomes
for t in race_trips:
    admin.call('/api/trips/'+str(t['id']),'PATCH',{'status':'cancelled'})
assert client.call('/api/stats')['total']==4
old_cookie = '; '.join(c.name+'='+c.value for c in client.jar)
old_csrf = client.csrf
client.call('/api/auth/logout','POST',{})
client.call('/api/auth/me',expected=401)
anonymous.call('/api/auth/me',expected=401,extra_headers={'Cookie':old_cookie,'X-CSRF-Token':old_csrf})
print('PASS: admin/driver/customer permissions, ownership, registration, CSRF, logout revocation, fare and concurrent assignment')
