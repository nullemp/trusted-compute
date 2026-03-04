-- SQL 沙箱示例脚本（在沙箱内解密并加载数据后执行）
-- 解密后的 JSON 需含 ddl 和/或 tables（或 data + table_name），会先建表并插入数据，再执行本脚本。
-- 单表时默认表名为 input_data；多表时按 tables[].table_name 建表。

-- 示例 1：统计行数（表名为 input_data 时）
SELECT COUNT(*) AS row_count FROM employees;