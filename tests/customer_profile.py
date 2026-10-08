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
        import io
        from PIL import Image
        customer=app.test_client();other=app.test_client()
        login(customer,'khach',os.environ['CUSTOMER_PASSWORD'])
        login(other,'taixe',os.environ['DRIVER_PASSWORD'])
        old=call(customer,'GET','/api/profile')
        data={'name':'Test customer name','phone':old['phone'],'email':old['email'] or '', 'age':'25','gender':'female'}
        updated=call(customer,'PATCH','/api/profile',data)
        assert updated['name']==data['name'] and updated['age']==25 and updated['gender']=='female'
        for change in [{'age':'0'},{'age':'121'},{'age':'25.5'},{'gender':'invalid'},{'customer_id':999}]:
            call(customer,'PATCH','/api/profile',{**data,**change},400)
        image=io.BytesIO();Image.new('RGB',(50,50),'red').save(image,format='PNG');image.seek(0)
        uploaded=customer.put('/api/profile/avatar',data={'image':(image,'avatar.png')})
        assert uploaded.status_code==200,uploaded.json
        profile=call(customer,'GET','/api/profile');assert profile['avatar_url']==uploaded.json['avatar_url']
        photo=customer.get(profile['avatar_url']);assert photo.status_code==200 and photo.mimetype=='image/jpeg'
        assert Image.open(io.BytesIO(photo.data)).size==(512,512)
        own_driver=call(other,'GET','/api/profile')
        assert own_driver.get('avatar_url')!=profile['avatar_url']
        call(customer,'DELETE','/api/profile/avatar')
        assert call(customer,'GET','/api/profile')['avatar_url'] is None
        assert customer.get('/api/profile/avatar').status_code==404
        print('PASS: customer name, age/gender validation, avatar upload/read/delete and role isolation; rolled back')
finally:
    conn.rollback()
    conn.close()
