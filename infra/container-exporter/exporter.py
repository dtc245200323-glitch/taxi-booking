"""Expose Compose CPU/memory counters using GET-only Docker Engine requests.

No Docker API is forwarded to clients. Socket access remains a privileged
monitoring exception: never publish this service or mount the socket into app.
"""
import http.client
import json
import os
import socket
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class DockerConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.sock.settimeout(3)
        self.sock.connect('/var/run/docker.sock')


def get(path):
    conn=DockerConnection('localhost',timeout=3)
    try:
        conn.request('GET',path)
        response=conn.getresponse()
        if response.status!=200: raise RuntimeError('Docker returned '+str(response.status))
        return json.loads(response.read())
    finally: conn.close()


def label(value):
    return str(value).replace('\\','\\\\').replace('"','\\"').replace('\n','\\n')


payload=b'container_exporter_up 0\n'
def collect():
    global payload
    while True:
        try:
            version=get('/version')['ApiVersion']
            project=os.getenv('COMPOSE_PROJECT_NAME','baikiemtra')
            filters=urllib.parse.urlencode({'filters':json.dumps({'label':['com.docker.compose.project='+project]})})
            rows=get('/v'+version+'/containers/json?'+filters)
            lines=['# TYPE container_exporter_up gauge','container_exporter_up 1',
                   '# TYPE container_cpu_usage_seconds_total counter',
                   '# TYPE container_memory_working_set_bytes gauge',
                   '# TYPE container_memory_limit_bytes gauge',
                   '# TYPE container_network_receive_bytes_total counter',
                   '# TYPE container_network_transmit_bytes_total counter']
            for row in rows:
                stats=get('/v'+version+'/containers/'+row['Id']+'/stats?stream=false&one-shot=true')
                labels='service="'+label(row['Labels'].get('com.docker.compose.service','unknown'))+'",name="'+label(row['Names'][0].lstrip('/'))+'",id="'+row['Id'][:12]+'"'
                mem=stats.get('memory_stats',{}); cache=mem.get('stats',{}).get('inactive_file',mem.get('stats',{}).get('cache',0))
                values={'container_cpu_usage_seconds_total':stats.get('cpu_stats',{}).get('cpu_usage',{}).get('total_usage',0)/1e9,
                        'container_memory_working_set_bytes':max(0,mem.get('usage',0)-cache),
                        'container_memory_limit_bytes':mem.get('limit',0),
                        'container_network_receive_bytes_total':sum(n.get('rx_bytes',0) for n in stats.get('networks',{}).values()),
                        'container_network_transmit_bytes_total':sum(n.get('tx_bytes',0) for n in stats.get('networks',{}).values())}
                lines.extend(k+'{'+labels+'} '+str(v) for k,v in values.items())
            payload=('\n'.join(lines)+'\n').encode()
        except Exception as exc:
            print('Collection failed:',type(exc).__name__,flush=True)
            payload=b'container_exporter_up 0\n'
        time.sleep(15)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path!='/metrics': self.send_error(404); return
        self.send_response(200);self.send_header('Content-Type','text/plain; version=0.0.4');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
    def log_message(self,*args): pass


if __name__=='__main__':
    threading.Thread(target=collect,daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0',9108),Handler).serve_forever()
