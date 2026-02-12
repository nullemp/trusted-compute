SELECT u.name, SUM(o.amount) AS total
FROM orders o JOIN users u ON o.user_id = u.id
GROUP BY u.name;

SELECT COUNT(*) AS order_count, SUM(amount) AS total_amount
FROM orders;
