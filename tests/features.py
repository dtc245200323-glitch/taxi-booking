"""Document acceptance tests for driver self-dispatch and new role features."""
import uuid
import os
import json
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from client import Client,config,PASSWORD,BASE

a=Client();a.login(os.getenv('ADMIN_USERNAME',config.get('ADMIN_USERNAME','admin')),PASSWORD)
suffix=uuid.uuid4().hex[:10];password='Feature-'+suffix
c=a.call('/api/customers','POST',{'name':'Document customer','phone':'fc'+suffix,'username':'fc'+suffix,'password':password},201)
profiles=[];drivers=[]
for i in range(2):
    p=a.call('/api/drivers','POST',{'name':'Document driver '+str(i),'phone':'fd'+str(i)+suffix,'plate':'FD'+str(i)+suffix,
        'username':'fd'+str(i)+suffix,'password':password,'model':'Toyota Vios','seats':4,'license':'L'+suffix},201)
    d=Client();d.login('fd'+str(i)+suffix,password);profiles.append(p);drivers.append(d)
customer=Client();customer.login('fc'+suffix,password)
customer.call('/api/profile','PATCH',{'name':'Updated document customer','phone':'fc'+suffix,'email':'demo@example.com'})
assert customer.call('/api/profile')['email']=='demo@example.com'
trip=customer.call('/api/trips','POST',{'pickup':'Bach Khoa','destination':'Ho Hoan Kiem','distance':5,'seats':4,'payment':'cash'},201)
assert int(trip['fare'])==75000
path='/api/trips/'+str(trip['id'])
assert any(t['id']==trip['id'] for t in drivers[0].call('/api/driver/queue'))
drivers[0].call('/api/driver/status','PATCH',{'status':'offline'})
drivers[0].call('/api/driver/trips/'+str(trip['id'])+'/accept','POST',{},409)
drivers[0].call('/api/driver/status','PATCH',{'status':'available'})
def accept(d):
    req=urllib.request.Request(BASE+'/api/driver/trips/'+str(trip['id'])+'/accept',method='POST',data=b'{}',
        headers={'Content-Type':'application/json','Origin':BASE,'X-CSRF-Token':d.csrf})
    try:
        with d.opener.open(req,timeout=10) as response:return response.status
    except urllib.error.HTTPError as e:return e.code
with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(accept,drivers))
assert sorted(results)==[200,409],results
winner=drivers[results.index(200)];loser=drivers[results.index(409)];winner_profile=profiles[results.index(200)]
accepted=customer.call(path)
assert accepted['accepted_at'] and accepted['vehicle_plate']
loser.call(path,expected=404)
loser.call(path+'/history',expected=404)
customer.call(path,'PATCH',{'status':'cancelled'},409)
winner.call('/api/driver/status','PATCH',{'status':'offline'},409)
other=customer.call('/api/trips','POST',{'pickup':'A','destination':'B','distance':1},201)
winner.call('/api/driver/trips/'+str(other['id'])+'/accept','POST',{},409)
customer.call('/api/trips/'+str(other['id']),'PATCH',{'status':'cancelled'})
winner.call(path,'PATCH',{'status':'completed'},409)
winner.call('/api/driver/trips/'+str(trip['id'])+'/arrive','POST',{})
assert customer.call(path)['arrived_at']
winner.call(path,'PATCH',{'status':'ongoing'})
winner.call(path,'PATCH',{'status':'completed'})
history=customer.call(path+'/history')
assert [h['new_status'] for h in history]==['pending','assigned','ongoing','completed']
assert customer.call(path)['completed_at']
assert int(winner.call('/api/driver/income')['today']['revenue'])==75000
customer.call(path+'/review','POST',{'stars':5,'comment':'Good trip'},201)
customer.call(path+'/review','POST',{'stars':4},409)
assert customer.call(path)['review']['stars']==5
complaint=customer.call('/api/complaints','POST',{'trip_id':trip['id'],'content':'Please check route'},201)
a.call('/api/admin/complaints/'+str(complaint['id']),'PATCH',{'status':'resolved','resolution':'Checked and replied'})
assert next(p for p in customer.call('/api/complaints') if p['id']==complaint['id'])['status']=='resolved'
assert any(r['trip_id']==trip['id'] for r in a.call('/api/admin/reviews'))
# Price changes affect only new bookings, not saved prices or pending route edits.
prices=a.call('/api/fares');old=next(f for f in prices if f['seats']==7)
seven=customer.call('/api/trips','POST',{'pickup':'A','destination':'B','distance':5,'seats':7},201)
try:
    a.call('/api/admin/fares/7','PATCH',{'base':int(old['base'])+1000,'per_km':old['per_km']})
    assert customer.call('/api/trips/'+str(seven['id']))['fare']==seven['fare']
    newer=customer.call('/api/trips','POST',{'pickup':'C','destination':'D','distance':5,'seats':7},201)
    assert int(newer['fare'])==int(seven['fare'])+1000
finally:
    a.call('/api/admin/fares/7','PATCH',{'base':old['base'],'per_km':old['per_km']})
winner.call('/api/driver/trips/'+str(seven['id'])+'/accept','POST',{},409)
request=winner.call('/api/driver/requests','POST',{'license':'NEW-LICENSE','plate':'SUV'+suffix,'model':'Toyota Innova','seats':7},201)
winner.call('/api/driver/requests','POST',{'license':'NEW','plate':'SUV'+suffix,'model':'SUV','seats':7},409)
a.call('/api/admin/requests/'+str(request['id']),'PATCH',{'status':'approved','note':'Validated'})
assert winner.call('/api/profile')['vehicle']['seats']==7
winner.call('/api/driver/trips/'+str(seven['id'])+'/accept','POST',{})
vehicle=next(v for v in a.call('/api/admin/vehicles') if v['driver_id']==winner_profile['id'])
a.call('/api/admin/vehicles/'+str(vehicle['id']),'PATCH',{'active':False},409)
winner.call('/api/trips/'+str(seven['id']),'PATCH',{'status':'ongoing'})
winner.call('/api/trips/'+str(seven['id']),'PATCH',{'status':'completed'})
customer.call('/api/trips/'+str(newer['id']),'PATCH',{'status':'cancelled'})
a.call('/api/admin/vehicles/'+str(vehicle['id']),'PATCH',{'active':False})
assert winner.call('/api/driver/queue')==[]
a.call('/api/admin/vehicles/'+str(vehicle['id']),'PATCH',{'active':True})
spare=a.call('/api/admin/vehicles','POST',{'plate':'SPARE'+suffix,'model':'Spare sedan','seats':4},201)
a.call('/api/admin/vehicles/'+str(spare['id']),'DELETE')
customer.call('/api/admin/vehicles',expected=403)
customer.call('/api/admin/fares/4','PATCH',{'base':1,'per_km':1},403)
customer.call('/api/driver/queue',expected=403)
winner.call('/api/admin/requests',expected=403)
customer.call('/api/auth/password','POST',{'old_password':'wrong','password':'New-password-123'},400)
customer.call('/api/auth/password','POST',{'old_password':password,'password':'New-password-123'})
customer.call('/api/auth/me',expected=401)
customer.login('fc'+suffix,'New-password-123')
assert a.call('/api/admin/overview')['week']
print('PASS: driver readiness, two-driver acceptance race, ownership, timestamps/history, profiles/password, vehicles, pricing snapshots, review/complaint and approval')
