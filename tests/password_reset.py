"""Real DB + Flask integration; SMTP is mocked so no email is sent."""
import os
import re
import uuid
import hashlib
from unittest.mock import patch
from app import app,db

client=app.test_client()
suffix=uuid.uuid4().hex[:10]
username='reset'+suffix
password='Reset-test-'+suffix
assert client.post('/api/auth/register',json={'username':username,'password':password,'name':'Reset test','phone':username}).status_code==201
login=client.post('/api/auth/login',json={'username':username,'password':password}).get_json()
csrf=login['csrf_token']
assert client.patch('/api/profile',json={'name':'Reset test','phone':username,'email':'test@example.com'},headers={'X-CSRF-Token':csrf}).status_code==200
with patch.dict(os.environ,{'SMTP_HOST':'smtp.test','SMTP_TLS':'false'}),patch('smtplib.SMTP') as smtp:
    assert client.post('/api/auth/forgot',json={'username':username,'email':'wrong@example.com'}).status_code==200
    smtp.return_value.__enter__.return_value.send_message.assert_not_called()
    assert client.post('/api/auth/forgot',json={'username':username,'email':'test@example.com'}).status_code==200
    message=smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    token=re.search(r'#reset=([a-f0-9]{64})',message.get_content()).group(1)
    with db() as conn:
        assert conn.execute('SELECT user_id FROM password_resets WHERE token_hash=%s',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    new_password='New-reset-'+suffix
    assert client.post('/api/auth/reset',json={'token':token,'password':new_password}).status_code==200
    assert client.get('/api/auth/me').status_code==401
    assert client.post('/api/auth/reset',json={'token':token,'password':password}).status_code==400
    assert client.post('/api/auth/login',json={'username':username,'password':password}).status_code==401
    assert client.post('/api/auth/login',json={'username':username,'password':new_password}).status_code==200
    assert client.post('/api/auth/forgot',json={'username':username,'email':'test@example.com'}).status_code==200
    next_message=smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
    expired=re.search(r'#reset=([a-f0-9]{64})',next_message.get_content()).group(1)
    with db() as conn:
        conn.execute("UPDATE password_resets SET expires_at=now()-interval '1 second' WHERE token_hash=%s",(hashlib.sha256(expired.encode()).hexdigest(),))
    assert client.post('/api/auth/reset',json={'token':expired,'password':password}).status_code==400
print('PASS: reset email generation (mock SMTP), hashed/expiring/single-use token, password replacement and session revocation')
