CREATE TABLE customers (
 id SERIAL PRIMARY KEY, name VARCHAR(100) NOT NULL, phone VARCHAR(20) NOT NULL UNIQUE
);
CREATE TABLE drivers (
 id SERIAL PRIMARY KEY, name VARCHAR(100) NOT NULL, phone VARCHAR(20) NOT NULL UNIQUE,
 plate VARCHAR(20) NOT NULL UNIQUE, status VARCHAR(20) NOT NULL DEFAULT 'available'
 CHECK (status IN ('available','busy'))
);
CREATE TABLE trips (
 id SERIAL PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
 driver_id INTEGER REFERENCES drivers(id), pickup VARCHAR(200) NOT NULL,
 destination VARCHAR(200) NOT NULL, distance NUMERIC(8,2) NOT NULL CHECK(distance>0 AND distance<=1000),
 fare NUMERIC(12,0) NOT NULL CHECK(fare>=0),
 status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','assigned','ongoing','completed','cancelled')),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 CHECK(status NOT IN ('assigned','ongoing','completed') OR driver_id IS NOT NULL)
);
CREATE UNIQUE INDEX one_active_trip_per_driver ON trips(driver_id) WHERE status IN ('assigned','ongoing');
CREATE INDEX trips_customer ON trips(customer_id);
INSERT INTO customers(name,phone) VALUES ('Nguyễn Minh Anh','0901234567'),('Trần Quốc Bảo','0912345678');
INSERT INTO drivers(name,phone,plate) VALUES ('Lê Hoàng Nam','0987654321','51A-123.45'),('Phạm Tuấn Anh','0976543210','51B-678.90');
INSERT INTO trips(customer_id,pickup,destination,distance,fare) VALUES (1,'Chợ Bến Thành','Sân bay Tân Sơn Nhất',8,111000);
