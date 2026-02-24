-- 建表 DDL（MariaDB）：与 users.csv / orders.csv 对应，作为建表依据。
CREATE TABLE IF NOT EXISTS users (
  id INT,
  name VARCHAR(255)
);
CREATE TABLE IF NOT EXISTS orders (
  id INT,
  user_id INT,
  amount DOUBLE,
  created_at VARCHAR(255)
);
