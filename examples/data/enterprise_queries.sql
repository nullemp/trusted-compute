-- 企业数据分析示例：聚合、多表关联、分组统计
-- 1) 按部门统计员工人数与平均薪资
SELECT d.name AS dept_name, COUNT(e.id) AS emp_count, ROUND(AVG(e.salary), 2) AS avg_salary
FROM departments d
LEFT JOIN employees e ON d.id = e.dept_id
GROUP BY d.id, d.name
ORDER BY emp_count DESC
LIMIT 15;

-- 2) 按区域统计部门预算总和
SELECT region, COUNT(*) AS dept_count, ROUND(SUM(budget), 2) AS total_budget
FROM departments
GROUP BY region
ORDER BY total_budget DESC;

-- 3) 销售订单：按员工统计订单笔数与销售总额
SELECT e.name AS employee_name, e.job_title,
  COUNT(o.id) AS order_count, ROUND(SUM(o.amount), 2) AS total_sales
FROM employees e
LEFT JOIN sales_orders o ON e.id = o.employee_id
GROUP BY e.id, e.name, e.job_title
HAVING order_count > 0
ORDER BY total_sales DESC
LIMIT 15;

-- 4) 按产品类别统计销售额与订单量
SELECT p.category, COUNT(DISTINCT o.id) AS order_count,
  ROUND(SUM(o.amount), 2) AS total_amount, ROUND(AVG(o.amount), 2) AS avg_order_amount
FROM products p
JOIN sales_orders o ON p.id = o.product_id
GROUP BY p.category
ORDER BY total_amount DESC;

-- 5) 项目状态分布与预算汇总
SELECT status, COUNT(*) AS project_count, ROUND(SUM(budget), 2) AS total_budget
FROM projects
GROUP BY status
ORDER BY total_budget DESC;
