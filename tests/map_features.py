"""Map endpoints with deterministic provider fixtures; no external searches/routes."""
import os
import uuid
from unittest.mock import patch
from app import app,db
from maps import MapError


class Client:
    def __init__(self):self.http=app.test_client();self.csrf=''
    def call(self,path,method='GET',data=None,status=200):
        response=self.http.open(path,method=method,json=data,headers={'X-CSRF-Token':self.csrf})
        assert response.status_code==status,(path,response.status_code,response.get_json())
        return response.get_json()
    def login(self,username,password):
        result=self.call('/api/auth/login','POST',{'username':username,'password':password});self.csrf=result['csrf_token'];return result['user']


admin=Client();admin.login(os.getenv('ADMIN_USERNAME','admin'),os.environ['ADMIN_PASSWORD'])
suffix=uuid.uuid4().hex[:10];password='Map-'+suffix
customer=Client();customer2=Client();driver=Client();driver2=Client()
customers=[];drivers=[]
for i,c in enumerate([customer,customer2]):
    username=f'mc{i}{suffix}';row=admin.call('/api/customers','POST',{'name':'Map test customer','phone':username,'username':username,'password':password},201)
    customers.append(row);c.login(username,password)
for i,d in enumerate([driver,driver2]):
    username=f'md{i}{suffix}';row=admin.call('/api/drivers','POST',{'name':'Map test driver','phone':username,'plate':username,'username':username,'password':password,'model':'Toyota Vios','seats':4,'license':'L'+suffix},201)
    drivers.append(row);d.login(username,password)
pickup={'lat':21.0067,'lng':105.84314};destination={'lat':21.0286,'lng':105.852}
fixture={'code':'Ok','routes':[{'distance':6432.4,'duration':600,'geometry':{'type':'LineString','coordinates':[[105.84314,21.0067],[105.845,21.013],[105.852,21.0286]]}}]}
with patch('maps.provider_json',return_value={'features':[{'geometry':{'coordinates':[105.84314,21.0067]},'properties':{'name':'University','city':'Hanoi'}}]}):
    places=customer.call('/api/maps/search','POST',{'query':'University Hanoi'})['places'];assert places[0]['lat']==pickup['lat']
with patch('maps.provider_json',return_value=fixture):
    quote=customer.call('/api/maps/route','POST',{'pickup':pickup,'destination':destination});assert quote['distance_km']=='6.43'
    expired=customer.call('/api/maps/route','POST',{'pickup':pickup,'destination':destination})
    retry=customer.call('/api/maps/route','POST',{'pickup':pickup,'destination':destination})
payload={'pickup':'University Hanoi','destination':'Hoan Kiem','seats':4,'distance':.01,'route_quote_id':quote['quote_id']}
customer2.call('/api/trips','POST',payload,409)
trip=customer.call('/api/trips','POST',payload,201);trip_id=trip['id'];path=f'/api/trips/{trip_id}'
assert float(trip['distance'])==6.43 and float(trip['fare'])==92160
assert trip['location_source']=='map' and trip['pickup_lat']==pickup['lat'] and trip['route_geometry']==fixture['routes'][0]['geometry']
customer.call('/api/trips','POST',payload,409)
with db() as conn:conn.execute("UPDATE route_quotes SET expires_at=now()-interval '1 second' WHERE id=%s",(expired['quote_id'],))
customer.call('/api/trips','POST',dict(payload,route_quote_id=expired['quote_id']),409)
customer.call('/api/trips','POST',dict(payload,route_quote_id=retry['quote_id'],pickup=''),400)
with db() as conn:assert not conn.execute('SELECT used FROM route_quotes WHERE id=%s',(retry['quote_id'],)).fetchone()['used']
customer.call(path+'/map');customer2.call(path+'/map',status=403);driver2.call(path+'/map')  # allowed queue preview
admin.call('/api/admin/trips/'+str(trip_id),'PATCH',{'pickup':'Other','destination':'Other','distance':9},409)
customer.call('/api/driver/location','PUT',pickup,403)
driver.call('/api/driver/location','PUT',{'lat':91,'lng':105},400)
driver.call('/api/driver/location','PUT',{'lat':True,'lng':105},400)
driver.call('/api/driver/status','PATCH',{'status':'offline'})
driver.call('/api/driver/location','PUT',pickup,409)
driver.call('/api/driver/status','PATCH',{'status':'available'})
driver.call('/api/driver/location','PUT',dict(pickup,accuracy=12))
assert customer.call(path+'/map')['driver_location'] is None
driver.call(f'/api/driver/trips/{trip_id}/accept','POST',{})
assert customer.call(path+'/map')['driver_location']['lat']==pickup['lat']
driver2.call(path+'/map',status=403);customer2.call(path+'/map',status=403)
with db() as conn:conn.execute("UPDATE driver_locations SET updated_at=now()-interval '3 minutes' WHERE driver_id=%s",(drivers[0]['id'],))
assert customer.call(path+'/map')['driver_location'] is None
driver.call('/api/driver/location','PUT',dict(destination,accuracy=8))
assert customer.call(path+'/map')['driver_location']['lng']==destination['lng']
driver.call('/api/driver/location','DELETE');assert customer.call(path+'/map')['driver_location'] is None
driver.call('/api/driver/location','PUT',dict(destination,accuracy=8))
driver.call('/api/auth/logout','POST',{});assert customer.call(path+'/map')['driver_location'] is None
driver.login('md0'+suffix,password);driver.call('/api/driver/location','PUT',dict(destination,accuracy=8))
driver.call(path,'PATCH',{'status':'ongoing'});driver.call(path,'PATCH',{'status':'completed'})
assert customer.call(path+'/map')['driver_location'] is None
with patch('maps.provider_json',side_effect=MapError('Provider unavailable')):
    customer.call('/api/maps/route','POST',{'pickup':pickup,'destination':destination},503)
customer.call('/api/maps/route','POST',{'pickup':pickup,'destination':pickup},422)
print('PASS: map search/route, server distance/fare, quote ownership/expiry/reuse/rollback, GPS access/staleness/stop/logout/completion and provider failure')
