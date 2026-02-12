# python examples/demo.py 一整个流程

## 前提

- 服务已启动（如 `scripts\start-for-client.ps1`），backend 在 `http://localhost:8000`。
- 本机已安装依赖：`pip install -r examples/requirements.txt`（或使用 `examples/offline_wheels/` 离线安装）。

---

## 1. 入口

- 在**项目根目录**执行：`python examples/demo.py`。
- `demo.py` 只做一件事：`from run_sql_examples import main` 并调用 `main()`，实际逻辑都在 `run_sql_examples.py`。

---

## 2. 本机脚本（run_sql_examples.main）

| 步骤 | 动作 |
|------|------|
| 2.1 | 读环境变量 `TRUSTED_COMPUTE_API`（默认 `http://localhost:8000`），打印 API 地址。 |
| 2.2 | **健康检查**：`GET {BASE}/`，失败则提示“服务未就绪”并退出。 |
| 2.3 | **读文件**（路径均为 `examples/data/`）： |
|     | - **dbprofile.sql** → 整段内容作为 `ddl`（建表 DDL）； |
|     | - **users.csv**、**orders.csv** → 用 `csv.DictReader` 读成「字典列表」； |
|     | - **query.sql** → 读入后按 `;` 拆成多条 SQL，得到 `sql_list`。 |
| 2.4 | 组装请求体：`tables_payload = [ { "table_name": "users", "data": users_data }, { "table_name": "orders", "data": orders_data } ]`。 |
| 2.5 | **对 query.sql 里每一条 SQL**：发一次 `POST {BASE}/api/execute-sql`，body 为 `{"sql": 当前这条 SQL, "ddl": ddl, "tables": tables_payload}`。 |
| 2.6 | 解析响应 JSON，打印：SQL 内容、结果列、每行数据、行数、耗时(ms)。 |

也就是说：**每条 query 发一次请求**，每次请求都带**同一份 ddl + 同一份 tables 数据**。

---

## 3. Backend（FastAPI）

| 步骤 | 动作 |
|------|------|
| 3.1 | 接收 `POST /api/execute-sql`，解析为 `ExecuteSqlRequest`（含 `sql`、`ddl`、`tables`）。 |
| 3.2 | 调用 `sandbox_service.execute_sql(sql=..., ddl=..., tables=...)`。 |
| 3.3 | 构造传给沙箱的 payload：`{ "model_type": "sql", "model_code": sql, "input_params": { "ddl": ddl, "tables": tables } }`，用 UTF-8 序列化为 JSON。 |
| 3.4 | 调用宿主上的容器运行时（如 `podman`）：`podman run --rm --network none -i trusted-compute-sandbox`，把上述 JSON 从**标准输入**传入容器。 |
| 3.5 | 等待容器退出，从**标准输出**读 JSON，解析后加上 `execution_time_ms`，返回给客户端。 |

---

## 4. 沙箱容器内（runner.py）

容器内进程是：`python runner.py`，从 stdin 读一整段 JSON。

| 步骤 | 动作 |
|------|------|
| 4.1 | 解析 JSON，得到 `model_type`、`model_code`（即本次要执行的 SQL）、`input_params`（含 `ddl`、`tables`）。 |
| 4.2 | 因为 `model_type == "sql"`，进入 `run_sql(model_code, input_params)`。 |
| 4.3 | 打开**内存 SQLite**：`conn = sqlite3.connect(":memory:")`（不落盘）。 |
| 4.4 | **有 ddl**：先 `conn.executescript(ddl)`，按 dbprofile.sql 建表（如 `users`、`orders`，列类型 INTEGER/REAL/TEXT）；再按 `tables` 顺序对每张表只做 **INSERT**（`_insert_data_into_table`），不再次建表。 |
| 4.5 | 执行用户 SQL：`cur.execute(sql)`，若是 SELECT 则 `fetchall()`，得到结果列名和行数据。 |
| 4.6 | 组装结果：`{"status": "success", "type": "sql", "result": {"columns": [...], "data": [...], "row_count": N}}`，若有异常则 `{"status": "error", "error": "..."}`。 |
| 4.7 | 将结果 JSON 打印到 **stdout**，进程退出。容器 `--rm`，退出后容器被删除，内存 SQLite 随之消失。 |

---

## 5. 数据与请求对应关系

- **建表依据**：仅来自请求里的 `ddl`（即 dbprofile.sql 内容），与 CSV 列名一致即可。
- **数据来源**：仅来自请求里的 `tables[].data`（即 users.csv / orders.csv 读入后的字典列表）。
- **执行的 SQL**：来自请求里的 `sql`（即 query.sql 中按 `;` 拆出的每一条）。

---

## 6. 流程简图

```
[ 本机 ]  python examples/demo.py
    → run_sql_examples.main()
    → 读 dbprofile.sql、users.csv、orders.csv、query.sql
    → 对 query.sql 中每条 SQL：
        → POST /api/execute-sql  { sql, ddl, tables }

[ Backend 容器 ]  FastAPI 收到 POST
    → sandbox_service.execute_sql()
    → podman run --rm -i trusted-compute-sandbox  < stdin(JSON)

[ 沙箱容器 ]  runner.py 从 stdin 读 JSON
    → executescript(ddl)  建表
    → INSERT  users / orders  插入 CSV 数据
    → execute(sql)  执行当前这条 query
    → 结果 JSON 写 stdout → 容器退出并删除
```

---

## 7. 小结

- **demo.py**：入口，只调 `run_sql_examples.main()`。
- **run_sql_examples**：读 3 类文件（dbprofile.sql、CSV、query.sql），按「每条 query 一次请求」调用 `/api/execute-sql`，并打印结果。
- **Backend**：转发请求到沙箱容器（stdin JSON → 容器内 runner.py）。
- **沙箱**：内存 SQLite，先 DDL 建表、再按 tables 插入、再执行 sql，结果从 stdout 返回；容器退出后无持久化。
