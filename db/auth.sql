CREATE TABLE IF NOT EXISTS users (
 id SERIAL PRIMARY KEY,
 username VARCHAR(50) NOT NULL UNIQUE,
 password_hash TEXT NOT NULL,
 role VARCHAR(20) NOT NULL CHECK(role IN ('admin','driver','customer')),
 customer_id INTEGER UNIQUE REFERENCES customers(id),
 driver_id INTEGER UNIQUE REFERENCES drivers(id),
 CHECK ((role='admin' AND customer_id IS NULL AND driver_id IS NULL)
     OR (role='customer' AND customer_id IS NOT NULL AND driver_id IS NULL)
     OR (role='driver' AND driver_id IS NOT NULL AND customer_id IS NULL))
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash CHAR(64) PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 csrf_token VARCHAR(64) NOT NULL,
 expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '24 hours')
);
CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
ALTER TABLE users ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE drivers ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE drivers DROP CONSTRAINT IF EXISTS drivers_status_check;
ALTER TABLE drivers ADD CONSTRAINT drivers_status_check CHECK(status IN ('available','busy','offline'));
CREATE TABLE IF NOT EXISTS audit_logs (
 id BIGSERIAL PRIMARY KEY,
 actor_id INTEGER NOT NULL REFERENCES users(id),
 action VARCHAR(60) NOT NULL,
 entity VARCHAR(30) NOT NULL,
 entity_id INTEGER NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audit_created ON audit_logs(created_at DESC);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS email VARCHAR(254);
ALTER TABLE drivers ADD COLUMN IF NOT EXISTS email VARCHAR(254);
ALTER TABLE drivers ADD COLUMN IF NOT EXISTS license VARCHAR(50) NOT NULL DEFAULT '';
ALTER TABLE drivers DROP CONSTRAINT IF EXISTS drivers_plate_key;
CREATE TABLE IF NOT EXISTS vehicles (
 id SERIAL PRIMARY KEY,
 driver_id INTEGER UNIQUE REFERENCES drivers(id),
 plate VARCHAR(20) UNIQUE NOT NULL,
 model VARCHAR(100) NOT NULL,
 seats INTEGER NOT NULL CHECK(seats IN (4,7)),
 active BOOLEAN NOT NULL DEFAULT TRUE
);
INSERT INTO vehicles(driver_id,plate,model,seats)
 SELECT id,plate,'Toyota Vios',4 FROM drivers
 WHERE NOT EXISTS (SELECT 1 FROM vehicles v WHERE v.driver_id=drivers.id OR v.plate=drivers.plate);
CREATE TABLE IF NOT EXISTS fares (
 seats INTEGER PRIMARY KEY CHECK(seats IN (4,7)),
 base NUMERIC(12,0) NOT NULL CHECK(base>=0 AND base<=1000000),
 per_km NUMERIC(12,0) NOT NULL CHECK(per_km>=0 AND per_km<=1000000)
);
INSERT INTO fares VALUES (4,15000,12000),(7,20000,15000) ON CONFLICT DO NOTHING;
ALTER TABLE trips ADD COLUMN IF NOT EXISTS seats INTEGER NOT NULL DEFAULT 4 CHECK(seats IN (4,7));
ALTER TABLE trips ADD COLUMN IF NOT EXISTS payment VARCHAR(20) NOT NULL DEFAULT 'cash' CHECK(payment='cash');
ALTER TABLE trips ADD COLUMN IF NOT EXISTS base_fare NUMERIC(12,0) NOT NULL DEFAULT 15000;
ALTER TABLE trips ADD COLUMN IF NOT EXISTS per_km NUMERIC(12,0) NOT NULL DEFAULT 12000;
ALTER TABLE trips ADD COLUMN IF NOT EXISTS accepted_at TIMESTAMPTZ;
ALTER TABLE trips ADD COLUMN IF NOT EXISTS arrived_at TIMESTAMPTZ;
ALTER TABLE trips ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;
ALTER TABLE trips ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;
ALTER TABLE trips ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ;
ALTER TABLE trips ADD COLUMN IF NOT EXISTS vehicle_plate VARCHAR(20);
ALTER TABLE trips ADD COLUMN IF NOT EXISTS vehicle_model VARCHAR(100);
CREATE TABLE IF NOT EXISTS trip_status_history (
 id BIGSERIAL PRIMARY KEY,
 trip_id INTEGER NOT NULL REFERENCES trips(id),
 old_status VARCHAR(20),new_status VARCHAR(20) NOT NULL,
 actor_id INTEGER REFERENCES users(id),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS trip_history_trip ON trip_status_history(trip_id,id);
INSERT INTO trip_status_history(trip_id,new_status,created_at)
 SELECT id,status,created_at FROM trips WHERE NOT EXISTS
 (SELECT 1 FROM trip_status_history h WHERE h.trip_id=trips.id);
CREATE TABLE IF NOT EXISTS reviews (
 trip_id INTEGER PRIMARY KEY REFERENCES trips(id),
 customer_id INTEGER NOT NULL REFERENCES customers(id),
 stars INTEGER NOT NULL CHECK(stars BETWEEN 1 AND 5),
 comment VARCHAR(1000) NOT NULL DEFAULT '',
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS complaints (
 id SERIAL PRIMARY KEY,trip_id INTEGER NOT NULL REFERENCES trips(id),
 customer_id INTEGER NOT NULL REFERENCES customers(id),
 content VARCHAR(2000) NOT NULL,status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK(status IN ('open','processing','resolved')),
 resolution VARCHAR(2000) NOT NULL DEFAULT '',created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS driver_requests (
 id SERIAL PRIMARY KEY,driver_id INTEGER NOT NULL REFERENCES drivers(id),
 model VARCHAR(100) NOT NULL,plate VARCHAR(20) NOT NULL,seats INTEGER NOT NULL CHECK(seats IN (4,7)),
 license VARCHAR(50) NOT NULL,status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
 note VARCHAR(500) NOT NULL DEFAULT '',created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS one_pending_driver_request ON driver_requests(driver_id) WHERE status='pending';
CREATE TABLE IF NOT EXISTS password_resets (
 token_hash CHAR(64) PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 expires_at TIMESTAMPTZ NOT NULL DEFAULT (now()+interval '30 minutes')
);
CREATE TABLE IF NOT EXISTS driver_avatars (
 driver_id INTEGER PRIMARY KEY REFERENCES drivers(id) ON DELETE CASCADE,
 content BYTEA NOT NULL,version VARCHAR(32) NOT NULL,updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE trips DROP CONSTRAINT IF EXISTS trips_payment_check;
ALTER TABLE trips ADD CONSTRAINT trips_payment_check CHECK(payment IN ('cash','transfer'));
CREATE TABLE IF NOT EXISTS payment_settings (
 id INTEGER PRIMARY KEY CHECK(id=1),bank_bin CHAR(6) NOT NULL,
 bank_name VARCHAR(100) NOT NULL,account_no VARCHAR(19) NOT NULL,account_name VARCHAR(100) NOT NULL
);
INSERT INTO payment_settings (id,bank_bin,bank_name,account_no,account_name) VALUES (1,'970436','Vietcombank','9398142181','LY MINH PHUONG') ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS bank_accounts (
 id SERIAL PRIMARY KEY,bank_bin CHAR(6) NOT NULL,bank_name VARCHAR(100) NOT NULL,
 account_no VARCHAR(19) NOT NULL,account_name VARCHAR(100) NOT NULL,
 UNIQUE(bank_bin,account_no)
);
ALTER TABLE payment_settings ADD COLUMN IF NOT EXISTS bank_account_id INTEGER REFERENCES bank_accounts(id);
INSERT INTO bank_accounts (bank_bin,bank_name,account_no,account_name)
 SELECT bank_bin,bank_name,account_no,account_name FROM payment_settings WHERE bank_account_id IS NULL
 ON CONFLICT (bank_bin,account_no) DO NOTHING;
UPDATE payment_settings s SET bank_account_id=b.id FROM bank_accounts b
 WHERE s.bank_account_id IS NULL AND s.bank_bin=b.bank_bin AND s.account_no=b.account_no;
CREATE TABLE IF NOT EXISTS payment_attempts (
 id SERIAL PRIMARY KEY,trip_id INTEGER NOT NULL REFERENCES trips(id),
 amount NUMERIC(12,2) NOT NULL CHECK(amount>0),reference VARCHAR(25) UNIQUE NOT NULL,
 bank_bin CHAR(6) NOT NULL,bank_name VARCHAR(100) NOT NULL,account_no VARCHAR(19) NOT NULL,account_name VARCHAR(100) NOT NULL,
 status VARCHAR(30) NOT NULL DEFAULT 'awaiting_transfer' CHECK(status IN ('awaiting_transfer','pending','success','failed')),
 note VARCHAR(500) NOT NULL DEFAULT '',created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 submitted_at TIMESTAMPTZ,reviewed_at TIMESTAMPTZ,reviewed_by INTEGER REFERENCES users(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_live_payment ON payment_attempts(trip_id) WHERE status IN ('awaiting_transfer','pending','success');
ALTER TABLE trips ADD COLUMN IF NOT EXISTS pickup_lat DOUBLE PRECISION;
ALTER TABLE trips ADD COLUMN IF NOT EXISTS pickup_lng DOUBLE PRECISION;
ALTER TABLE trips ADD COLUMN IF NOT EXISTS destination_lat DOUBLE PRECISION;
ALTER TABLE trips ADD COLUMN IF NOT EXISTS destination_lng DOUBLE PRECISION;
ALTER TABLE trips ADD COLUMN IF NOT EXISTS route_geometry JSONB;
ALTER TABLE trips ADD COLUMN IF NOT EXISTS route_duration_seconds INTEGER;
ALTER TABLE trips ADD COLUMN IF NOT EXISTS location_source VARCHAR(20) NOT NULL DEFAULT 'manual';
CREATE TABLE IF NOT EXISTS route_quotes (
 id CHAR(32) PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),payload JSONB NOT NULL,
 used BOOLEAN NOT NULL DEFAULT false,expires_at TIMESTAMPTZ NOT NULL DEFAULT (now()+interval '15 minutes')
);
CREATE TABLE IF NOT EXISTS map_cache (
 key CHAR(64) PRIMARY KEY,payload JSONB NOT NULL,expires_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS driver_locations (
 driver_id INTEGER PRIMARY KEY REFERENCES drivers(id) ON DELETE CASCADE,
 lat DOUBLE PRECISION NOT NULL CHECK(lat BETWEEN -85 AND 85),lng DOUBLE PRECISION NOT NULL CHECK(lng BETWEEN -180 AND 180),
 accuracy DOUBLE PRECISION NOT NULL CHECK(accuracy>=0),updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE vehicles DROP CONSTRAINT IF EXISTS vehicles_seats_check;
ALTER TABLE vehicles ADD CONSTRAINT vehicles_seats_check CHECK(seats IN (1,4,7));
ALTER TABLE fares DROP CONSTRAINT IF EXISTS fares_seats_check;
ALTER TABLE fares ADD CONSTRAINT fares_seats_check CHECK(seats IN (1,4,7));
ALTER TABLE trips DROP CONSTRAINT IF EXISTS trips_seats_check;
ALTER TABLE trips ADD CONSTRAINT trips_seats_check CHECK(seats IN (1,4,7));
ALTER TABLE driver_requests DROP CONSTRAINT IF EXISTS driver_requests_seats_check;
ALTER TABLE driver_requests ADD CONSTRAINT driver_requests_seats_check CHECK(seats IN (1,4,7));
INSERT INTO fares VALUES (1,10000,5000) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS promotions (
 id SERIAL PRIMARY KEY, code VARCHAR(30) UNIQUE NOT NULL, title VARCHAR(150) NOT NULL,
 kind VARCHAR(10) NOT NULL CHECK(kind IN ('percent','fixed')), value NUMERIC(12,2) NOT NULL CHECK(value>0),
 max_discount NUMERIC(12,0) NOT NULL CHECK(max_discount>0), min_fare NUMERIC(12,0) NOT NULL DEFAULT 0,
 usage_limit INTEGER NOT NULL CHECK(usage_limit>0), per_customer_limit INTEGER NOT NULL CHECK(per_customer_limit>0),
 expires_at TIMESTAMPTZ NOT NULL, active BOOLEAN NOT NULL DEFAULT TRUE
);
ALTER TABLE trips ADD COLUMN IF NOT EXISTS promo_code VARCHAR(30);
ALTER TABLE trips ADD COLUMN IF NOT EXISTS discount_amount NUMERIC(12,0) NOT NULL DEFAULT 0;
INSERT INTO promotions(code,title,kind,value,max_discount,min_fare,usage_limit,per_customer_limit,expires_at)
 VALUES ('WELCOME20','Chào bạn mới! Giảm 20% chuyến đi','percent',20,30000,20000,1000,1,now()+interval '30 days') ON CONFLICT DO NOTHING;

ALTER TABLE drivers ADD COLUMN IF NOT EXISTS age INTEGER CHECK(age BETWEEN 18 AND 100);
ALTER TABLE drivers ADD COLUMN IF NOT EXISTS gender VARCHAR(10) CHECK(gender IN ('male','female','other'));
ALTER TABLE drivers ADD COLUMN IF NOT EXISTS hometown VARCHAR(150);
ALTER TABLE drivers ADD COLUMN IF NOT EXISTS experience_years INTEGER CHECK(experience_years BETWEEN 0 AND 82);

CREATE TABLE IF NOT EXISTS saved_promotions (
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 promotion_id INTEGER NOT NULL REFERENCES promotions(id) ON DELETE CASCADE,
 saved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 PRIMARY KEY(user_id,promotion_id)
);

ALTER TABLE promotions ADD COLUMN IF NOT EXISTS image_data TEXT;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS age INTEGER CHECK(age BETWEEN 1 AND 120);
ALTER TABLE customers ADD COLUMN IF NOT EXISTS gender VARCHAR(10) CHECK(gender IN ('male','female','other'));
CREATE TABLE IF NOT EXISTS customer_avatars (
 customer_id INTEGER PRIMARY KEY REFERENCES customers(id) ON DELETE CASCADE,
 content BYTEA NOT NULL,version VARCHAR(32) NOT NULL,updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS admin_profiles (
 user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 name VARCHAR(100) NOT NULL,phone VARCHAR(20) NOT NULL DEFAULT '',email VARCHAR(254),
 age INTEGER CHECK(age BETWEEN 1 AND 120),gender VARCHAR(10) CHECK(gender IN ('male','female','other'))
);
INSERT INTO admin_profiles(user_id,name) SELECT id,username FROM users WHERE role='admin' ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS admin_avatars (
 admin_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 content BYTEA NOT NULL,version VARCHAR(32) NOT NULL,updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS support_conversations (
 id SERIAL PRIMARY KEY,customer_user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
 admin_read_id INTEGER NOT NULL DEFAULT 0,customer_read_id INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS support_messages (
 id SERIAL PRIMARY KEY,conversation_id INTEGER NOT NULL REFERENCES support_conversations(id) ON DELETE CASCADE,
 sender_id INTEGER NOT NULL REFERENCES users(id),content VARCHAR(2000) NOT NULL CHECK(length(content)>0),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS support_messages_thread ON support_messages(conversation_id,id);

CREATE TABLE IF NOT EXISTS driver_support_conversations (
 id SERIAL PRIMARY KEY,driver_user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
 admin_read_id INTEGER NOT NULL DEFAULT 0,driver_read_id INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS driver_support_messages (
 id SERIAL PRIMARY KEY,conversation_id INTEGER NOT NULL REFERENCES driver_support_conversations(id) ON DELETE CASCADE,
 sender_id INTEGER NOT NULL REFERENCES users(id),content VARCHAR(2000) NOT NULL CHECK(length(content)>0),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS driver_support_messages_thread ON driver_support_messages(conversation_id,id);

ALTER TABLE support_conversations ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ;
ALTER TABLE support_conversations ADD COLUMN IF NOT EXISTS rating INTEGER CHECK(rating BETWEEN 1 AND 5);
ALTER TABLE support_conversations DROP CONSTRAINT IF EXISTS support_conversations_customer_user_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS support_one_open_conversation ON support_conversations(customer_user_id) WHERE closed_at IS NULL;
