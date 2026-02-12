# SQL 使用说明

本项目中 SQL 在**沙箱内 SQLite** 执行，结果直接返回，不落盘。

## 接口

**POST /api/execute-sql**

- **可选 ddl**：传 `ddl`（建表 DDL 文本，如 dbprofile.sql 内容）时，沙箱先执行 DDL 建表，再按 `tables` 仅插入数据（不自动建表），列类型由 DDL 决定。
- **单表**：body 传 `data`（行数据数组）、`sql`，可选 `table_name`、`columns`；不传 ddl 时自动按 data 建表（全列 TEXT）。
- **多表**：body 传 `tables`（`[{ "table_name": "xxx", "data": [...], "columns": [...]? }, ...]`）、`sql`；可同时传 `ddl` 做建表依据。

服务将请求转发给沙箱容器，沙箱在内存 SQLite 中建表、插入数据、执行 SQL，返回 `{"status": "success", "result": {"columns", "data", "row_count"}, "execution_time_ms"?}`。

## 示例：dbprofile.sql + CSV + query.sql

`examples/run_sql_examples.py` 使用三类文件调用本接口：

- **dbprofile.sql**：建表 DDL，作为建表依据（类型明确，如 INTEGER/REAL/TEXT）。
- **users.csv / orders.csv**：要插入的表数据。
- **query.sql**：要执行的 SQL，多条语句用分号分隔。

脚本读取上述文件后发送 `ddl` + `tables` + 每条 `sql` 的请求。
