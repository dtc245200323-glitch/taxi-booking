"""Integration: image validation, scoped transfers, retries and immutable reconciliation."""
import json
import os
import struct
import time
import urllib.error
import urllib.request
import uuid
import zlib
from concurrent.futures import ThreadPoolExecutor
from client import Client, BASE, PASSWORD, config


def png():
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',2,2,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\x00'+b'\x22\x88\xdd'*2)*2))+chunk(b'IEND',b'')


def upload(client,content,expected):
    boundary='TaxiPhotoBoundary'
    payload=(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="photo.png"\r\nContent-Type: image/png\r\n\r\n'.encode()+content+f'\r\n--{boundary}--\r\n'.encode())
    req=urllib.request.Request(BASE+'/api/profile/avatar',data=payload,method='PUT',headers={
        'Content-Type':'multipart/form-data; boundary='+boundary,'Origin':BASE,'X-CSRF-Token':client.csrf})
    time.sleep(.15)
    try:response=client.opener.open(req,timeout=15)
    except urllib.error.HTTPError as error:response=error
    with response:
        raw=response.read();assert response.status==expected,(response.status,raw)
        return json.loads(raw)


a=Client();a.login(config.get('ADMIN_USERNAME','admin'),PASSWORD)
suffix=uuid.uuid4().hex[:10];password='Payment-'+suffix
c=a.call('/api/customers','POST',{'name':'Payment test customer','phone':'pc'+suffix,'username':'pc'+suffix,'password':password},201)
customer=Client();customer.login('pc'+suffix,password)
other=Client();other.login('khach',config['CUSTOMER_PASSWORD'])
d=a.call('/api/drivers','POST',{'name':'Photo test driver','phone':'pd'+suffix,'plate':'PD'+suffix,'username':'pd'+suffix,'password':password,'model':'Toyota Vios','seats':4,'license':'L'+suffix},201)
driver=Client();driver.login('pd'+suffix,password)
photo=upload(driver,png(),200)
assert photo['avatar_url']==driver.call('/api/profile')['avatar_url']
with driver.opener.open(BASE+photo['avatar_url']) as response:
    assert response.headers['Content-Type'].startswith('image/jpeg') and response.read().startswith(b'\xff\xd8')
other.call(photo['avatar_url'],expected=403)
upload(customer,png(),403);upload(driver,b'not an image',400)
upload(driver,b'x'*(2*1024*1024+1),413)
driver.call('/api/profile/avatar','DELETE')
assert driver.call('/api/profile')['avatar_url'] is None
customer.call('/api/payment/settings','PATCH',{},403)
bank=a.call('/api/payment/settings')
trip=customer.call('/api/trips','POST',{'pickup':'Payment pickup','destination':'Payment destination','distance':5,'seats':4,'payment':'transfer'},201)
assert trip['payment']=='transfer'
path='/api/trips/'+str(trip['id'])+'/payment'
assert customer.call(path)['payment'] is None
first=customer.call(path,'POST',{})['payment']
assert first['status']=='awaiting_transfer' and float(first['amount'])==float(trip['fare'])
assert first['account_no']==bank['account_no'] and first['qr_url'].startswith(path+'/')
with customer.opener.open(BASE+first['qr_url']) as response:
    assert response.headers['Content-Type'].startswith('image/png') and response.read().startswith(b'\x89PNG')
other.call(first['qr_url'],expected=404)
assert customer.call(path,'POST',{})['payment']['id']==first['id']
other.call(path,expected=404);other.call(path,'POST',{},404);driver.call(path,'POST',{},403)
customer.call('/api/admin/payments',expected=403)
customer.call(path+'/submit','POST',{'payment_id':first['id']+1000},409)
a.call('/api/admin/trips/'+str(trip['id']),'PATCH',{'pickup':'Changed','destination':'Changed','distance':7},409)
customer.call(path+'/submit','POST',{'payment_id':first['id']})
customer.call(first['qr_url'],expected=409)
assert customer.call(path+'/submit','POST',{'payment_id':first['id']})['payment']['status']=='pending'
customer.call('/api/trips/'+str(trip['id']),'PATCH',{'status':'cancelled'},409)
a.call('/api/admin/payments/'+str(first['id']),'PATCH',{'status':'failed','note':''},400)
failed=a.call('/api/admin/payments/'+str(first['id']),'PATCH',{'status':'failed','note':'No matching bank transaction'})['payment']
assert failed['status']=='failed'
assert customer.call(path)['payment']['note']=='No matching bank transaction'
retry=customer.call(path,'POST',{})['payment']
assert retry['id']!=first['id'] and retry['reference']!=first['reference']
customer.call(path+'/submit','POST',{'payment_id':retry['id']})
second_admin=Client();second_admin.login(config.get('ADMIN_USERNAME','admin'),PASSWORD)


def decide(client):
    req=urllib.request.Request(BASE+'/api/admin/payments/'+str(retry['id']),method='PATCH',
        data=json.dumps({'status':'success','note':'Verified bank transaction test'}).encode(),
        headers={'Content-Type':'application/json','Origin':BASE,'X-CSRF-Token':client.csrf})
    try:
        with client.opener.open(req,timeout=15) as response:return response.status
    except urllib.error.HTTPError as error:return error.code


with ThreadPoolExecutor(max_workers=2) as pool:
    assert sorted(pool.map(decide,[a,second_admin]))==[200,409]
paid=customer.call(path)
assert paid['payment']['status']=='success' and len(paid['history'])==2
assert customer.call(path,'POST',{})['payment']['id']==retry['id']
a.call('/api/admin/payments/'+str(retry['id']),'PATCH',{'status':'failed','note':'cannot overwrite'},409)
customer.call('/api/trips/'+str(trip['id']),'PATCH',{'status':'cancelled'},409)
assert any(p['id']==retry['id'] and p['status']=='success' for p in customer.call('/api/payments'))
cancelled=customer.call('/api/trips','POST',{'pickup':'Cancel pickup','destination':'Cancel destination','distance':1,'seats':4},201)
cancel_path='/api/trips/'+str(cancelled['id'])+'/payment'
cancel_payment=customer.call(cancel_path,'POST',{})['payment']
customer.call('/api/trips/'+str(cancelled['id']),'PATCH',{'status':'cancelled'})
assert customer.call(cancel_path)['payment']['status']=='failed'
customer.call(cancel_payment['qr_url'],expected=409)
customer.call(cancel_path,'POST',{},409)
print('PASS: photo upload/removal/validation/access; transfer amount, scope, failed retry, success, duplicate/race reconciliation and cancellation guard')
