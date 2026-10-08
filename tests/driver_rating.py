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
        customer=app.test_client();admin=app.test_client()
        login(customer,'khach',os.environ['CUSTOMER_PASSWORD'])
        login(admin,os.getenv('ADMIN_USERNAME','admin'),os.environ['ADMIN_PASSWORD'])
        owner=conn.execute("SELECT customer_id FROM users WHERE username='khach'").fetchone()['customer_id']
        trip=conn.execute("SELECT id FROM trips WHERE driver_id IS NOT NULL LIMIT 1").fetchone()['id']
        conn.execute('DELETE FROM reviews WHERE trip_id=%s',(trip,))
        conn.execute('DELETE FROM payment_attempts WHERE trip_id=%s',(trip,))
        conn.execute("UPDATE trips SET customer_id=%s,status='completed',payment='transfer' WHERE id=%s",(owner,trip))
        path=f'/api/trips/{trip}/review'
        call(customer,'POST',path,{'stars':5},409)
        conn.execute("UPDATE trips SET payment='cash' WHERE id=%s",(trip,))
        assert any(row['id']==trip for row in call(customer,'GET','/api/trips/reviewable'))
        call(admin,'POST',path,{'stars':5},403)
        call(customer,'POST',path,{'stars':6},400)
        call(customer,'POST',path,{'stars':5,'comment':'Good driver'},201)
        assert next(row for row in call(customer,'GET','/api/trips/reviewable') if row['id']==trip)['stars']==5
        print('PASS: payment eligibility, role checks, maximum 5 stars and persisted driver review; rolled back')
finally:
    conn.rollback()
    conn.close()
