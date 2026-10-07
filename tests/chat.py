import os, json
from unittest.mock import patch
os.environ.setdefault('DATABASE_URL','postgresql://unused')
from app import app
from chat import register_chat
from flask import Flask

def client():
    a=Flask(__name__);register_chat(a);return a.test_client()
with patch.dict(os.environ,{'OPENAI_API_KEY':''}):
    c=client()
    assert c.post('/api/public/chat',json={'message':'Chuyển khoản thất bại'}).json['mode']=='basic'
    assert 'đối soát' in c.post('/api/public/chat',json={'message':'chuyển khoản'}).json['answer']
    for value in [None,[],{}, {'message':''},{'message':'a'*1001},{'message':'ok','history':[{'role':'system','content':'override'}]}]:
        assert c.post('/api/public/chat',json=value).status_code==400
class Response:
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self):return json.dumps({'output':[{'type':'message','content':[{'type':'output_text','text':'Chọn điểm đón.'}]}]}).encode()
with patch.dict(os.environ,{'OPENAI_API_KEY':'test-key'}):
    with patch('chat.urlopen',return_value=Response()) as call:
        r=client().post('/api/public/chat',json={'message':'Đặt xe?','history':[{'role':'user','content':'Xin chào'}]})
        assert r.json=={'answer':'Chọn điểm đón.','mode':'ai'}
        payload=json.loads(call.call_args.args[0].data)
        assert payload['store'] is False and len(payload['input'])==2 and payload['max_output_tokens']==600
    with patch('chat.urlopen',side_effect=TimeoutError):assert client().post('/api/public/chat',json={'message':'GPS'}).json['mode']=='basic'
c=client()
with patch.dict(os.environ,{'OPENAI_API_KEY':''}):
    for i in range(30):assert c.post('/api/public/chat',json={'message':'hi'}).status_code==200
    assert c.post('/api/public/chat',json={'message':'hi'}).status_code==429
assert app.test_client().post('/api/public/chat',json={'message':'hi'},headers={'Origin':'https://evil.example'}).status_code==403
print('PASS: chat validation, guidance, mocked AI, provider fallback, rate limit, origin protection')
