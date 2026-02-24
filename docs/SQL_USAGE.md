# SQL 使用说明

本项目中 SQL 在**沙箱内 MariaDB** 执行，采用**实例隔离**：每个沙箱由独立 MariaDB 容器 + 数据卷组成，创建/销毁见下文。

## 接口

**POST /api/sandboxes** — 创建沙箱（启动独立 DB 容器并绑定数据卷），返回 `sandbox_id`。  
**DELETE /api/sandboxes/{sandbox_id}** — 销毁沙箱（停止并删除 DB 容器与数据卷）。

**POST /api/execute-sql**

- **sandbox_id**（必填）：由 `POST /api/sandboxes` 返回的沙箱 ID。
- **可选 ddl**：传 `ddl`（建表 DDL，MariaDB 语法）时，先执行 DDL 建表，再按 `tables` 插入数据。
- **单表**：传 `data`、`sql`，可选 `table_name`、`columns`；不传 ddl 时自动按 data 建表（VARCHAR(2000)）。
- **多表**：传 `tables`、`sql`，可同时传 `ddl`。

服务将请求转发给 runner 容器，runner 连接该沙箱的 MariaDB、创建临时 database、建表/插入/执行 SQL、返回结果后删除该 database，返回 `{"status": "success", "result": {"columns", "data", "row_count"}, "execution_time_ms"?}`。

## 示例：dbprofile.sql + CSV + query.sql

`examples/run_sql_examples.py` 使用三类文件调用本接口：

- **dbprofile.sql**：建表 DDL（MariaDB 语法），作为建表依据（如 INT/VARCHAR/DOUBLE）。
- **users.csv / orders.csv**：要插入的表数据。
- **query.sql**：要执行的 SQL，多条语句用分号分隔。

脚本读取上述文件后发送 `ddl` + `tables` + 每条 `sql` 的请求。
