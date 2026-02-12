-- 建表 DDL：建议从数据库直接导出，作为唯一来源。
-- run-analysis：传 ddl_file 时在临时库中先执行本文件建表。
-- execute-sql/files：传 ddl_file 时用本文件解析出的表定义覆盖 config 中的 ddl。
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
