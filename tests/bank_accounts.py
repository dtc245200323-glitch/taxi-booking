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
        admin=app.test_client();customer=app.test_client()
        login(admin,os.getenv('ADMIN_USERNAME','admin'),os.environ['ADMIN_PASSWORD'])
        login(customer,'khach',os.environ['CUSTOMER_PASSWORD'])
        fields=('bank_bin','bank_name','account_no','account_name')
        old=call(admin,'GET','/api/payment/settings')
        accounts=call(admin,'GET','/api/admin/bank-accounts')
        assert sum(account['selected'] for account in accounts)==1
        call(customer,'GET','/api/admin/bank-accounts',expected=403)
        call(customer,'POST','/api/admin/bank-accounts',{},403)
        call(customer,'POST',f"/api/admin/bank-accounts/{old['bank_account_id']}/select",{},403)
        data={'bank_bin':'970422','bank_name':'Test bank','account_no':str(uuid.uuid4().int)[:16],'account_name':'TEST ACCOUNT'}
        call(admin,'POST','/api/admin/bank-accounts',{**data,'bank_bin':'bad'},400)
        missing_csrf=admin.post('/api/admin/bank-accounts',json=data,headers={'X-CSRF-Token':''})
        assert missing_csrf.status_code==403
        new=call(admin,'POST','/api/admin/bank-accounts',data,201)
        call(admin,'POST','/api/admin/bank-accounts',data,409)
        assert call(admin,'GET','/api/payment/settings')['bank_account_id']==old['bank_account_id']
        trip=call(customer,'POST','/api/trips',{'pickup':'Bank test','destination':'Test destination','distance':5,'seats':4,'payment':'transfer'},201)
        path=f"/api/trips/{trip['id']}/payment"
        payment=call(customer,'POST',path,{})['payment']
        call(admin,'POST',f"/api/admin/bank-accounts/{new['id']}/select",{})
        selected=call(admin,'GET','/api/payment/settings')
        assert all(selected[key]==data[key] for key in fields)
        preserved=call(customer,'GET',path)['payment']
        assert all(preserved[key]==payment[key] for key in fields)
        second=call(customer,'POST','/api/trips',{'pickup':'New bank test','destination':'Test destination','distance':6,'seats':4,'payment':'transfer'},201)
        second_payment=call(customer,'POST',f"/api/trips/{second['id']}/payment",{})['payment']
        assert all(second_payment[key]==data[key] for key in fields)
        call(admin,'PATCH','/api/payment/settings',{key:old[key] for key in fields},409)
        edited={**data,'bank_name':'Updated test bank'}
        call(admin,'PATCH','/api/payment/settings',edited)
        listed=call(admin,'GET','/api/admin/bank-accounts')
        assert next(account for account in listed if account['id']==new['id'])['bank_name']==edited['bank_name']
        call(admin,'POST','/api/admin/bank-accounts/2147483647/select',{},404)
        print('PASS: add, duplicates, validation, roles, CSRF, select, edit and payment snapshots; rolled back')
finally:
    conn.rollback()
    conn.close()
