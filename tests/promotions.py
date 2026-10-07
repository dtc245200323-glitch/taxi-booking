import os
import uuid
from unittest.mock import patch
from app import app, db

class Client:
    def __init__(self): self.http=app.test_client(); self.csrf=''
    def call(self,path,method='GET',data=None,status=200):
        r=self.http.open('/api/'+path,method=method,json=data,headers={'X-CSRF-Token':self.csrf})
        assert r.status_code==status,(path,r.status_code,r.get_json())
        return r.get_json()
    def login(self,name,password): self.csrf=self.call('auth/login','POST',{'username':name,'password':password})['csrf_token']

admin=Client();admin.login(os.getenv('ADMIN_USERNAME','admin'),os.environ['ADMIN_PASSWORD'])
suffix=uuid.uuid4().hex[:10];password='Test-'+suffix
customer=Client();other=Client();bike=Client();car=Client()
for i,c in enumerate([customer,other]):
    name=f'pc{i}{suffix}'
    admin.call('customers','POST',{'name':'Promotion test','phone':name,'username':name,'password':password},201);c.login(name,password)
for seats,c in [(1,bike),(4,car)]:
    name=f'pd{seats}{suffix}'
    admin.call('drivers','POST',{'name':'Vehicle test','phone':name,'plate':name,'username':name,'password':password,'model':'Honda' if seats==1 else 'Vios','seats':seats,'license':suffix},201);c.login(name,password)
code='P'+suffix.upper()
config={'code':code,'title':'Test discount','kind':'percent','value':20,'max_discount':30000,'min_fare':20000,'usage_limit':1,'per_customer_limit':1,'days':30}
promo=admin.call('admin/promotions','POST',config,201)
customer.call('admin/promotions','POST',config,403)
fixture={'code':'Ok','routes':[{'distance':5000,'duration':400,'geometry':{'type':'LineString','coordinates':[[105.84,21.01],[105.85,21.02]]}}]}
with patch('maps.provider_json',return_value=fixture):
    quote=customer.call('maps/route','POST',{'pickup':{'lat':21.01,'lng':105.84},'destination':{'lat':21.02,'lng':105.85}})
result=customer.call('promotions/preview','POST',{'code':code,'seats':1,'route_quote_id':quote['quote_id']})
assert float(result['total'])==28000 and float(result['discount'])==7000
payload={'pickup':'A','destination':'B','distance':5,'seats':1,'promo_code':code,'route_quote_id':quote['quote_id'],'fare':1,'discount_amount':999999}
trip=customer.call('trips','POST',payload,201)
assert float(trip['fare'])==28000 and float(trip['discount_amount'])==7000 and trip['seats']==1
other.call('trips','POST',dict(payload,route_quote_id=None),400)
admin.call('admin/trips/'+str(trip['id']),'PATCH',{'pickup':'C','destination':'D','distance':9},409)
car.call('driver/trips/'+str(trip['id'])+'/accept','POST',{},409)
bike.call('driver/trips/'+str(trip['id'])+'/accept','POST',{})
admin.call('admin/promotions/'+str(promo['id']),'PATCH',{'active':False})
other.call('trips','POST',dict(payload,route_quote_id=None),400)
assert float(customer.call('trips/'+str(trip['id']))['fare'])==28000
admin.call('admin/promotions/'+str(promo['id']),'PATCH',{'active':True})
admin.call('trips/'+str(trip['id']),'PATCH',{'status':'cancelled'})
retry=other.call('trips','POST',dict(payload,route_quote_id=None),201)
assert float(retry['fare'])==28000
with db() as conn: conn.execute("UPDATE promotions SET expires_at=now()-interval '1 day' WHERE id=%s",(promo['id'],))
customer.call('trips','POST',dict(payload,route_quote_id=None),400)
admin.call('admin/promotions','POST',dict(config,code='BAD'+suffix,value=101),400)
from concurrent.futures import ThreadPoolExecutor
racecode='R'+suffix.upper()
admin.call('admin/promotions','POST',dict(config,code=racecode),201)
def reserve(c):
    return c.http.post('/api/trips',json=dict(payload,route_quote_id=None,promo_code=racecode),headers={'X-CSRF-Token':c.csrf}).status_code
with ThreadPoolExecutor(max_workers=2) as pool:
    results=list(pool.map(reserve,[customer,other]))
assert sorted(results)==[201,400],results
admin.call('admin/promotions/'+str(promo['id']),'PATCH',{'active':False})
with db() as conn:conn.execute('UPDATE promotions SET active=false WHERE code=%s',(racecode,))
print('PASS: concurrent usage limit, motorbike fare/assignment, promotion preview, server price, usage limits, cancellation, expired/disabled codes, ownership and retained price')
