"""Verify locally running monitoring stack; reads secrets without printing them."""
import base64
import json
from pathlib import Path
import urllib.request
import urllib.parse
import urllib.error

config = dict(line.split('=', 1) for line in Path('.env').read_text().splitlines()
              if '=' in line and not line.startswith('#'))
credential = base64.b64encode(('admin:' + config['GRAFANA_PASSWORD']).encode()).decode()

def get(url, grafana=False):
    req = urllib.request.Request(url, headers={'Authorization':'Basic '+credential} if grafana else {})
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read())

query = urllib.parse.urlencode({'query':'up'})
result = get('http://127.0.0.1:9090/api/v1/query?'+query)
assert all(r['value'][1]=='1' for r in result['data']['result']),result
assert {'taxi-api','nginx','postgres','containers','prometheus'} <= {r['metric']['job'] for r in result['data']['result']}
for expression in ['nginx_up','pg_up','container_exporter_up','container_memory_working_set_bytes{service="app"}']:
    r=get('http://127.0.0.1:9090/api/v1/query?'+urllib.parse.urlencode({'query':expression}))
    assert r['data']['result'] and float(r['data']['result'][0]['value'][1])>0,(expression,r)
assert get('http://127.0.0.1:3000/api/health')['database'] == 'ok'
dashboard = get('http://127.0.0.1:3000/api/dashboards/uid/taxi-overview', True)
assert len(dashboard['dashboard']['panels']) >= 11
for uid in ['prometheus','loki']:
    result = get('http://127.0.0.1:3000/api/datasources/uid/'+uid+'/health', True)
    assert result['status'] == 'OK', result
query = urllib.parse.urlencode({'query':'{job="taxi-nginx"}', 'limit':10})
logs = get('http://127.0.0.1:3000/api/datasources/proxy/uid/loki/loki/api/v1/query_range?'+query, True)
assert logs['data']['result'], 'No Nginx logs received by Loki'
for path in ['http://127.0.0.1:8080/','http://127.0.0.1:8080/app.js','http://127.0.0.1:8080/base.css','http://127.0.0.1:5050/login']:
    with urllib.request.urlopen(path, timeout=10) as response:
        assert response.status == 200
try:
    urllib.request.urlopen('http://127.0.0.1:8080/metrics', timeout=10)
except urllib.error.HTTPError as error:
    assert error.code == 404
else:
    raise AssertionError('Metrics must be private')
print('PASS: Prometheus scrape, Grafana dashboard/datasources, Loki logs, UI assets, pgAdmin and private metrics')

from datetime import datetime,timezone
queries=['{job="taxi-nginx",collector="promtail"}', '{job="taxi-nginx",collector="promtail"} |= "GET"', 'sum(count_over_time({job="taxi-nginx",collector="promtail"}[5m]))']
evidence={'checked_at':datetime.now(timezone.utc).isoformat(),'targets':get('http://127.0.0.1:9090/api/v1/targets')['data']['activeTargets'],'logql':[]}
for q in queries:
    response=get('http://127.0.0.1:3000/api/datasources/proxy/uid/loki/loki/api/v1/query_range?'+urllib.parse.urlencode({'query':q,'limit':5}),True)
    assert response['status']=='success' and response['data']['result'],(q,response)
    evidence['logql'].append({'query':q,'result':response['data']['result']})
with urllib.request.urlopen('http://127.0.0.1:8080/') as r:
    evidence['security_headers']={k:r.headers[k] for k in ['X-Content-Type-Options','X-Frame-Options','Referrer-Policy','Permissions-Policy','Content-Security-Policy']}
    assert all(evidence['security_headers'].values())
Path('docs/evidence').mkdir(exist_ok=True)
Path('docs/evidence/monitoring.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS: five scrape targets, web/DB/container metrics, three LogQL queries and security headers; evidence saved')
