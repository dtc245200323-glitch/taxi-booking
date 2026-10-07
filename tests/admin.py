"""Administrative CRUD, account revocation, filters, reporting and dispatch checks."""
import csv
import io
import os
import uuid
import urllib.request
from client import Client, config, PASSWORD, BASE

admin=Client()
actor=admin.login(os.getenv('ADMIN_USERNAME',config.get('ADMIN_USERNAME','admin')),PASSWORD)
suffix=uuid.uuid4().hex[:10]
password='Admin-test-'+suffix
def profile(kind,prefix):
    data={'name':prefix+' '+suffix,'phone':prefix+suffix,'username':prefix+suffix,'password':password}
    if kind=='drivers':
        data['plate']=prefix+suffix
    return admin.call('/api/'+kind,'POST',data,201)
c=profile('customers','c')
d=profile('drivers','d')
second=profile('drivers','e')
customer,driver=Client(),Client()
cu=customer.login('c'+suffix,password)
du=driver.login('d'+suffix,password)
accounts=admin.call('/api/admin/users')
assert all('password_hash' not in u for u in accounts)
for client in [customer,driver]:
    for path in ['/api/admin/users','/api/admin/reports','/api/admin/audit','/api/admin/export']:
        client.call(path,expected=403)
    for path in ['/api/customers/'+str(c['id']),'/api/drivers/'+str(d['id']),'/api/admin/users/'+str(du['id']),'/api/admin/trips/1']:
        client.call(path,'PATCH',{},403)
    client.call('/api/admin/users','POST',{},403)
admin.call('/api/admin/users/'+str(actor['id']),'PATCH',{'active':False},409)
admin.call('/api/admin/users/'+str(du['id']),'PATCH',{'role':'admin'},400)
admin.call('/api/customers/'+str(c['id']),'PATCH',{'name':'Edited '+suffix,'phone':'new'+suffix})
admin.call('/api/drivers/'+str(d['id']),'PATCH',{'plate':'NEW-'+suffix})
admin.call('/api/drivers/'+str(d['id']),'PATCH',{'status':'offline'})
trip=customer.call('/api/trips','POST',{'pickup':'A','destination':'B','distance':5},201)
path='/api/trips/'+str(trip['id'])
admin.call(path,'PATCH',{'status':'assigned','driver_id':d['id']},409)
admin.call('/api/drivers/'+str(d['id']),'PATCH',{'status':'available'})
edited=admin.call('/api/admin/trips/'+str(trip['id']),'PATCH',{'pickup':'=1+1','destination':'New destination','distance':8})
assert int(edited['fare'])==111000
admin.call(path,'PATCH',{'status':'assigned','driver_id':d['id']})
admin.call('/api/admin/users/'+str(du['id']),'PATCH',{'active':False},409)
admin.call('/api/admin/users/'+str(du['id']),'PATCH',{'password':'Changed-test-password'},409)
admin.call('/api/drivers/'+str(d['id']),'PATCH',{'status':'offline'},409)
admin.call('/api/drivers/'+str(d['id']),'DELETE',expected=409)
admin.call('/api/customers/'+str(c['id']),'DELETE',expected=409)
admin.call('/api/admin/trips/'+str(trip['id']),'PATCH',{'pickup':'C','destination':'D','distance':2},409)
admin.call(path,'PATCH',{'status':'assigned','driver_id':second['id']})
assert driver.call('/api/trips')==[]
newdriver=Client()
newdriver.login('e'+suffix,password)
assert newdriver.call(path)['driver_id']==second['id']
driver.call(path,expected=404)
newdriver.call(path,'PATCH',{'status':'ongoing'})
newdriver.call(path,'PATCH',{'status':'completed'})
rows=admin.call('/api/trips?status=completed&customer_id='+str(c['id'])+'&limit=1&page=1')
assert len(rows)==1 and rows[0]['id']==trip['id']
assert admin.call('/api/trips?customer_id='+str(c['id'])+'&limit=1&page=2')==[]
admin.call('/api/trips?status=wrong',expected=400)
admin.call('/api/trips?from=not-a-date',expected=400)
admin.call('/api/trips?page=0',expected=400)
admin.call('/api/trips?limit=0',expected=400)
assert admin.call('/api/trips?q=New%20destination&customer_id='+str(c['id']))[0]['id']==trip['id']
report=admin.call('/api/admin/reports?customer_id='+str(c['id']))
assert sum(int(r['revenue']) for r in report['daily'])==111000
assert report['drivers'][0]['id']==second['id']
stats=admin.call('/api/stats?customer_id='+str(c['id']))
assert stats['total']==1 and int(stats['revenue'])==111000
with admin.opener.open(BASE+'/api/admin/export?customer_id='+str(c['id'])) as response:
    export=list(csv.reader(io.StringIO(response.read().decode('utf-8-sig'))))
assert len(export)==2 and export[1][4]=="'=1+1"
assert export[1][0]==str(trip['id'])
# Reset password revokes previously authenticated cookies; old password stops working.
changed='Changed-'+suffix
admin.call('/api/admin/users/'+str(du['id']),'PATCH',{'password':changed})
driver.call('/api/auth/me',expected=401)
driver.call('/api/auth/login','POST',{'username':'d'+suffix,'password':password},401)
driver.login('d'+suffix,changed)
admin.call('/api/admin/users/'+str(du['id']),'PATCH',{'active':False})
driver.call('/api/auth/me',expected=401)
driver.call('/api/auth/login','POST',{'username':'d'+suffix,'password':changed},401)
admin.call('/api/admin/users/'+str(du['id']),'PATCH',{'active':True})
driver.login('d'+suffix,changed)
admin.call('/api/customers/'+str(c['id']),'DELETE')
customer.call('/api/auth/me',expected=401)
admin.call('/api/admin/users/'+str(cu['id']),'PATCH',{'active':True},409)
admin.call('/api/trips','POST',{'customer_id':c['id'],'pickup':'A','destination':'B','distance':1},409)
assert admin.call(path)['id']==trip['id']  # History survives archive.
admin.call('/api/customers/'+str(c['id']),'PATCH',{'archived':False})
admin.call('/api/admin/users/'+str(cu['id']),'PATCH',{'active':True})
customer.login('c'+suffix,password)
admin.call('/api/drivers/'+str(d['id']),'DELETE')
driver.call('/api/auth/me',expected=401)
admin.call('/api/drivers/'+str(d['id']),'PATCH',{'archived':False})
admin.call('/api/admin/users/'+str(du['id']),'PATCH',{'active':True})
driver.login('d'+suffix,changed)
extra=admin.call('/api/admin/users','POST',{'username':'a'+suffix,'password':password,'role':'admin'},201)
newadmin=Client()
assert newadmin.login('a'+suffix,password)['role']=='admin'
admin.call('/api/admin/users/'+str(extra['id']),'PATCH',{'active':False})
newadmin.call('/api/admin/users',expected=401)
admin.call('/api/admin/users','POST',{'username':'x'+suffix,'password':password,'role':'driver','profile_id':d['id']},409)
logs=admin.call('/api/admin/audit')
assert any(l['entity']=='user' and l['action']=='reset_password' and l['entity_id']==du['id'] for l in logs)
assert any(l['entity']=='trip' and l['action']=='reassign' and l['entity_id']==trip['id'] for l in logs)
print('PASS: admin CRUD/archive/restore, account locks and resets, reassign, history, filters/paging, reports, CSV and audit')
