# 客户端调用 API 说明（无需前端）

客户端进程通过 HTTP 调用本服务：提供 **DDL 文件**（建库/建表）、**数据文件**，由服务端执行 DDL、导入数据，再执行 **SQL 或 Python** 进行分析并返回结果。

---

## 一、推荐入口：`POST /api/run-analysis`

一条请求完成：**执行 DDL → 导入数据文件 → 执行分析（SQL 或 Python）**。

### 请求方式

- **Content-Type**: `multipart/form-data`
- **参数**:
  - `config`（必填）：JSON 字符串，见下表。
  - `files`（必填）：多个数据文件（如 CSV），顺序与 `config.tables` 一致。
  - `ddl`（可选）：DDL 文本（建库、建表等 SQL）。
  - `ddl_file`（可选）：上传的 DDL 文件，与 `ddl` 二选一即可。

### config JSON 结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `tables` | 数组 | 与 `files` 一一对应，每项：`table_name`、`has_header`、`delimiter`、`ddl`（可选）、`columns`（可选） |
| `analysis_type` | 字符串 | `"sql"` 或 `"python"` |
| `sql` | 字符串 | 分析用 SQL（`analysis_type=sql` 时必填；`python` 时也可用作取数 SQL） |
| `python` | 字符串 | 分析用 Python 代码（`analysis_type=python` 时必填），代码中需定义 `result` |
| `data_sql` | 字符串 | 可选；仅当 `analysis_type=python` 时有效，用该 SQL 取数并传入 `input_params["data"]`；不填则用 `sql` 或 `SELECT * FROM 第一张表` |

### 示例 1：仅数据文件 + SQL 分析（无 DDL）

- 两个 CSV 分别对应表 `orders`、`users`，建表由服务端根据文件首行推断，再执行一条联合查询。

```bash
# config 示例（JSON 字符串）
{
  "tables": [
    { "table_name": "orders", "has_header": true, "delimiter": "," },
    { "table_name": "users", "has_header": true, "delimiter": "," }
  ],
  "analysis_type": "sql",
  "sql": "SELECT u.region, COUNT(*) AS cnt FROM orders o JOIN users u ON o.user_id = u.id GROUP BY u.region"
}
```

- 使用 curl（将 `config` 作为表单字段，`file1.csv`、`file2.csv` 顺序对应 `tables`）：

```bash
curl -X POST "http://localhost:8000/api/run-analysis" \
  -F 'config={"tables":[{"table_name":"orders","has_header":true,"delimiter":","},{"table_name":"users","has_header":true,"delimiter":","}],"analysis_type":"sql","sql":"SELECT u.region, COUNT(*) AS cnt FROM orders o JOIN users u ON o.user_id = u.id GROUP BY u.region"}' \
  -F "files=@orders.csv" \
  -F "files=@users.csv"
```

### 示例 2：DDL 文件 + 数据文件 + SQL 分析

- 客户端上传一个 DDL 文件（内容如 `CREATE TABLE t1 (...); CREATE TABLE t2 (...);`）和两个数据文件，表名与 `tables` 中一致，再执行分析 SQL。

```bash
curl -X POST "http://localhost:8000/api/run-analysis" \
  -F "ddl_file=@schema.sql" \
  -F 'config={"tables":[{"table_name":"t1","has_header":true},{"table_name":"t2","has_header":true}],"analysis_type":"sql","sql":"SELECT * FROM t1 JOIN t2 ON t1.id = t2.id"}' \
  -F "files=@t1.csv" \
  -F "files=@t2.csv"
```

### 示例 3：数据文件 + Python 分析

- 单表导入，用 SQL 取数，再交给 Python 做分析，结果放在 `result` 中。

```bash
# config 中 python 代码需定义 result
{
  "tables": [ { "table_name": "data", "has_header": true } ],
  "analysis_type": "python",
  "sql": "SELECT * FROM data",
  "python": "import pandas as pd\ncols = input_params.get('columns', [])\ndata = pd.DataFrame(input_params['data'], columns=cols)\nresult = data.describe().to_dict()"
}
```

### 响应格式

- 成功（SQL）：`{"status": "success", "analysis_type": "sql", "result": {"columns": [...], "data": [[...]], "row_count": N}}`
- 成功（Python）：`{"status": "success", "analysis_type": "python", "result": {...}}`
- 失败：`{"status": "error", "error": "错误信息"}`

---

## 二、其他可用接口（无需项目/任务）

- **POST /api/execute-sql**：请求体 JSON，传 `data`（二维数组）+ `sql`，在临时表中执行 SQL，返回查询结果。
- **POST /api/execute-sql/file**：单 CSV 文件 + 表单参数（`sql`、`table_name`、`has_header`、`delimiter` 等），导入临时表后执行 SQL。
- **POST /api/execute-sql/files**：多 CSV + 一个 config JSON（`tables` + `sql`），多表导入后执行一条 SQL。

以上接口均不创建项目/任务，适合脚本或客户端直接调用。接口详情见 **http://localhost:8000/docs**。

---

## 三、运行服务（无前端）

**客户环境没有 Docker 时**：只需在客户机安装 MariaDB + Python，设置 `DATABASE_URL` 和 **`SANDBOX_MODE=local`**，只启动后端即可，详见 **[DEPLOY_CLIENT_NO_DOCKER.md](DEPLOY_CLIENT_NO_DOCKER.md)**。

```bash
# 客户环境无 Docker：安装 MariaDB 后，在本机执行
cd backend
# Windows: set DATABASE_URL=... & set SANDBOX_MODE=local
# Linux/macOS: export DATABASE_URL=... SANDBOX_MODE=local
uvicorn main:app --host 0.0.0.0 --port 8000
```

**有 Docker 时**：可只起后端与数据库，不启动前端：

```bash
docker-compose up -d --build
```

API 文档与调试：**http://localhost:8000/docs**。
