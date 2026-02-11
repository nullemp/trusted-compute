# SQL 使用说明

本项目中 SQL 在**沙箱内 SQLite** 执行，结果直接返回，不落盘。

## 接口

**POST /api/execute-sql**

- **单表**：body 传 `data`（行数据数组，每行 list 或 dict）、`sql`，可选 `table_name`（默认 `input_data`）、`columns`。
- **多表**：body 传 `tables`（`[{ "table_name": "xxx", "data": [...], "columns": [...]? }, ...]`）、`sql`。

服务将请求转发给沙箱容器，沙箱在内存 SQLite 中建表、插入数据、执行 SQL，返回 `{"status": "success", "result": {"columns", "data", "row_count"}, "execution_time_ms"?}`。

示例脚本：`examples/run_sql_examples.py`（多表 + 多条 SQL，本地读 CSV 后调用本接口）。
