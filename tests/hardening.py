"""Run on host; persist only selected non-secret Docker fields."""
import json
import os
import subprocess
from pathlib import Path

code='''import json
from app import db
with db() as c:
 r=c.execute("SELECT current_user name,rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=current_user").fetchone()
 assert r['name']=='taxi_app' and not any(r[k] for k in ('rolsuper','rolcreatedb','rolcreaterole'))
 try:c.execute('CREATE TABLE public.hardening_probe(id int)')
 except Exception as e:
  assert e.sqlstate=='42501',e
 else:raise AssertionError('Runtime role must not create tables')
 print(json.dumps(dict(r,ddl_denied=True)))
'''
r=subprocess.run(['docker-compose','exec','-T','app','python','-'],input=code,text=True,capture_output=True,check=True)
role=json.loads(r.stdout)
ids=subprocess.check_output(['docker-compose','ps','-q'],text=True).split()
containers=json.loads(subprocess.check_output(['docker','inspect',*ids],text=True))
evidence={'runtime_database_role':role,'containers':[]}
for c in containers:
    host=c['HostConfig'];service=c['Config']['Labels']['com.docker.compose.service']
    ports=host.get('PortBindings') or {}
    row={'service':service,'user':c['Config']['User'],'read_only':host['ReadonlyRootfs'],'cap_drop':host.get('CapDrop'),'security_opt':host.get('SecurityOpt'),'privileged':host['Privileged'],'ports':ports,'networks':list(c['NetworkSettings']['Networks'])}
    assert not host['Privileged'],service
    assert all(p['HostIp']=='127.0.0.1' for bindings in ports.values() for p in (bindings or [])),service
    if service=='app':
        assert row['user'] and row['user'] not in ('0','root') and row['read_only'] and 'ALL' in row['cap_drop']
        assert 'MIGRATION_DATABASE_URL=' not in '\n'.join(c['Config']['Env'])
    if service=='db':assert not ports
    evidence['containers'].append(row)
net=json.loads(subprocess.check_output(['docker','network','inspect',os.getenv('COMPOSE_PROJECT_NAME','baikiemtra')+'_backend',os.getenv('COMPOSE_PROJECT_NAME','baikiemtra')+'_monitoring'],text=True))
assert all(n['Internal'] for n in net)
evidence['internal_networks']=[n['Name'] for n in net]
Path('docs/evidence').mkdir(exist_ok=True)
Path('docs/evidence/hardening.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS: runtime DB cannot perform DDL; non-root/read-only app, dropped capabilities, localhost ports and internal networks')
