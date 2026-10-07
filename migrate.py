"""Add authentication without deleting existing booking data. Runs before Gunicorn."""
import os
from pathlib import Path
import psycopg
from werkzeug.security import generate_password_hash

with psycopg.connect(os.getenv('MIGRATION_DATABASE_URL') or os.environ['DATABASE_URL']) as conn:
    conn.execute('SELECT pg_advisory_xact_lock(220022)')
    conn.execute(Path('db/auth.sql').read_text(encoding='utf-8'))
    from psycopg import sql
    for name,key in [('taxi_app','APP_DB_PASSWORD'),('taxi_monitor','MONITOR_DB_PASSWORD')]:
        if not os.getenv(key):
            continue
        if not conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(name,)).fetchone():
            conn.execute(sql.SQL('CREATE ROLE {} LOGIN').format(sql.Identifier(name)))
        conn.execute(sql.SQL('ALTER ROLE {} PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION').format(sql.Identifier(name),sql.Literal(os.environ[key])))
        conn.execute(sql.SQL('GRANT CONNECT ON DATABASE taxi TO {}').format(sql.Identifier(name)))
    if os.getenv('APP_DB_PASSWORD'):
        conn.execute('GRANT USAGE ON SCHEMA public TO taxi_app')
        conn.execute('GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO taxi_app')
        conn.execute('GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO taxi_app')
    if os.getenv('MONITOR_DB_PASSWORD'):
        conn.execute('GRANT pg_monitor TO taxi_monitor')
    accounts = [('admin', 'ADMIN_PASSWORD', None), ('driver', 'DRIVER_PASSWORD', '0987654321'),
                ('customer', 'CUSTOMER_PASSWORD', '0901234567')]
    for role, key, phone in accounts:
        username = {'admin':os.getenv('ADMIN_USERNAME', 'admin'), 'driver':'taixe', 'customer':'khach'}[role]
        if conn.execute('SELECT 1 FROM users WHERE username=%s', (username,)).fetchone():
            continue
        password = os.environ[key]
        if not 8 <= len(password) <= 128:
            raise RuntimeError(key + ' must contain 8–128 characters')
        customer_id = driver_id = None
        if role == 'driver':
            profile = conn.execute('SELECT id FROM drivers WHERE phone=%s', (phone,)).fetchone()
            if not profile:
                raise RuntimeError('Seed driver missing; create the demo profile first')
            driver_id = profile[0]
        elif role == 'customer':
            profile = conn.execute('SELECT id FROM customers WHERE phone=%s', (phone,)).fetchone()
            if not profile:
                raise RuntimeError('Seed customer missing; create the demo profile first')
            customer_id = profile[0]
        conn.execute('''INSERT INTO users(username,password_hash,role,customer_id,driver_id)
            VALUES (%s,%s,%s,%s,%s)''',
            (username, generate_password_hash(password), role, customer_id, driver_id))
print('Authentication migration complete; existing trips preserved')
