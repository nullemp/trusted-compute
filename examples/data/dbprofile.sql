-- 建表 DDL：与 users.csv / orders.csv 对应，作为建表依据（类型明确）。
CREATE TABLE IF NOT EXISTS users (
  id INTEGER,
  name TEXT
);
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER,
  user_id INTEGER,
  amount REAL,
  created_at TEXT
);
