-- DDL for demo tables. When passed as ddl_file to /api/execute-sql/files,
-- the backend uses these definitions (overrides config.tables[].ddl).
CREATE TABLE IF NOT EXISTS orders (
  id INT,
  user_id INT,
  amount DECIMAL(10,2),
  created_at VARCHAR(20)
);
CREATE TABLE IF NOT EXISTS users (
  id INT,
  name VARCHAR(100)
);
