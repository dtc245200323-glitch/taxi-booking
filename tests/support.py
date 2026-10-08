"""Run inside app container; all test data and settings are rolled back."""
import os
import uuid
from unittest.mock import patch
import psycopg
from psycopg.rows import dict_row
from app import app, DATABASE_URL

conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)

class BorrowedConnection:
    def __enter__(self):
        return conn
    def __exit__(self, *args):
        return False

def login(client, username, password):
    response = client.post('/api/auth/login', json={'username':username,'password':password})
    assert response.status_code == 200, response.json
    client.environ_base['HTTP_X_CSRF_TOKEN'] = response.json['csrf_token']

def call(client, method, path, data=None, expected=200):
    response = client.open(path, method=method, json=data)
    assert response.status_code == expected, (path,response.status_code,response.json)
    return response.json

try:
    with patch('psycopg.connect', return_value=BorrowedConnection()):
        admin=app.test_client();driver=app.test_client();guest=app.test_client()
        login(admin,os.getenv('ADMIN_USERNAME','admin'),os.environ['ADMIN_PASSWORD'])
        login(driver,'taixe',os.environ['DRIVER_PASSWORD'])
        clients=[]
        for i in range(2):
            client=app.test_client();username='support'+uuid.uuid4().hex[:12]
            call(client,'POST','/api/auth/register',{'username':username,'password':'Support-Test-123','name':'Support test','phone':username},201)
            login(client,username,'Support-Test-123');clients.append(client)
        customer,other=clients
        assert call(customer,'GET','/api/support/conversations')==[]
        call(driver,'GET','/api/support/conversations',expected=403)
        call(driver,'POST','/api/support/messages',{'content':'Forbidden'},403)
        call(guest,'GET','/api/support/conversations',expected=401)
        call(customer,'POST','/api/support/messages',{'content':''},400)
        call(customer,'POST','/api/support/messages',{'content':'a'*2001},400)
        assert customer.post('/api/support/messages',json={'content':'No CSRF'},headers={'X-CSRF-Token':''}).status_code==403
        first=call(customer,'POST','/api/support/messages',{'content':'Help with my trip'},201)
        thread=first['conversation_id'];path=f'/api/support/conversations/{thread}'
        call(other,'GET',path+'/messages',expected=404)
        call(other,'POST',path+'/read',{'last_id':first['id']},404)
        assert call(other,'GET','/api/support/conversations')==[]
        row=next(row for row in call(admin,'GET','/api/support/conversations') if row['id']==thread)
        assert row['unread']==1
        messages=call(admin,'GET',path+'/messages');assert messages[-1]['content']=='Help with my trip'
        call(admin,'POST',path+'/read',{'last_id':first['id']})
        assert next(row for row in call(admin,'GET','/api/support/conversations') if row['id']==thread)['unread']==0
        reply=call(admin,'POST','/api/support/messages',{'conversation_id':thread,'content':'Admin reply'},201)
        assert call(customer,'GET','/api/support/conversations')[0]['unread']==1
        messages=call(customer,'GET',path+'/messages');assert messages[-1]['sender_role']=='admin' and messages[-1]['content']=='Admin reply'
        call(customer,'POST',path+'/read',{'last_id':reply['id']})
        assert call(customer,'GET','/api/support/conversations')[0]['unread']==0
        forged=call(other,'POST','/api/support/messages',{'conversation_id':thread,'content':'Other customer'},201)
        assert forged['conversation_id']!=thread
        assert len(call(customer,'GET',path+'/messages'))==2
        call(admin,'POST','/api/support/messages',{'conversation_id':2147483647,'content':'Unknown'},404)
        call(customer,'POST',path+'/rating',{'rating':5},409)
        call(other,'POST',path+'/close',expected=404)
        call(customer,'POST',path+'/close')
        call(customer,'POST','/api/support/messages',{'content':'Closed'},409)
        call(admin,'POST','/api/support/messages',{'conversation_id':thread,'content':'Closed'},409)
        call(customer,'POST',path+'/rating',{'rating':6},400)
        call(customer,'POST',path+'/rating',{'rating':True},400)
        call(other,'POST',path+'/rating',{'rating':5},404)
        call(customer,'POST',path+'/rating',{'rating':5})
        assert call(customer,'GET','/api/support/conversations')[0]['rating']==5
        new=call(customer,'POST','/api/support/conversations/new',expected=201)
        assert new['id']!=thread
        assert call(customer,'POST','/api/support/conversations/new',expected=201)['id']==new['id']
        fresh=call(customer,'POST','/api/support/messages',{'content':'New conversation'},201)
        assert fresh['conversation_id']==new['id']
        assert len(call(customer,'GET',path+'/messages'))==2
        print('PASS: end conversation, closed message protection, 1-5 ratings, ownership, new conversation and old history')
        call(customer,'GET','/api/driver-support/conversations',expected=403)
        call(guest,'GET','/api/driver-support/conversations',expected=401)
        first=call(driver,'POST','/api/driver-support/messages',{'content':'Driver needs help'},201)
        thread=first['conversation_id'];path=f'/api/driver-support/conversations/{thread}'
        call(customer,'GET',path+'/messages',expected=403)
        assert call(admin,'GET',path+'/messages')[-1]['sender_role']=='driver'
        row=next(row for row in call(admin,'GET','/api/driver-support/conversations') if row['id']==thread)
        assert row['unread']>=1
        call(admin,'POST',path+'/read',{'last_id':first['id']})
        reply=call(admin,'POST','/api/driver-support/messages',{'conversation_id':thread,'content':'Driver reply'},201)
        assert call(driver,'GET',path+'/messages')[-1]['content']=='Driver reply'
        assert call(driver,'GET','/api/driver-support/conversations')[0]['unread']>=1
        call(driver,'POST',path+'/read',{'last_id':reply['id']})
        assert call(driver,'GET','/api/driver-support/conversations')[0]['unread']==0
        print('PASS: driver support messages, admin replies and read receipts; customer channel remains isolated')
        print('PASS: two-way messages, unread/read, persistence, CSRF, validation and customer isolation; rolled back')
finally:
    conn.rollback()
    conn.close()
