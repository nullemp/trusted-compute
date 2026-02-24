-- 企业示例 DDL（MariaDB）：部门、员工、项目、产品、销售订单
CREATE TABLE IF NOT EXISTS departments (
  id INT,
  name VARCHAR(255),
  parent_id INT,
  budget DOUBLE,
  region VARCHAR(64)
);
CREATE TABLE IF NOT EXISTS employees (
  id INT,
  name VARCHAR(255),
  dept_id INT,
  job_title VARCHAR(128),
  salary DOUBLE,
  hire_date VARCHAR(32)
);
CREATE TABLE IF NOT EXISTS projects (
  id INT,
  name VARCHAR(255),
  dept_id INT,
  manager_id INT,
  budget DOUBLE,
  start_date VARCHAR(32),
  end_date VARCHAR(32),
  status VARCHAR(64)
);
CREATE TABLE IF NOT EXISTS products (
  id INT,
  name VARCHAR(255),
  category VARCHAR(128),
  unit_price DOUBLE
);
CREATE TABLE IF NOT EXISTS sales_orders (
  id INT,
  customer_name VARCHAR(255),
  employee_id INT,
  product_id INT,
  quantity INT,
  order_date VARCHAR(32),
  amount DOUBLE
);
