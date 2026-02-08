# 脚本方式调用：数据 + SQL

无需创建项目、任务。调用方只需：**提交数据 + SQL**，服务端将数据插入 **MariaDB 临时表**后执行 SQL 并返回结果（支持大数据量）。

---

## 怎么启动并以脚本方式调用

### 1. 启动服务（MariaDB + 后端，默认不启前端）

在项目根目录执行：

```bash
docker-compose up -d --build
```

首次会拉镜像、构建，约 1～2 分钟。等 MariaDB 健康检查通过后，后端会在 8000 端口监听。

### 2. 确认后端就绪（可选）

```bash
curl -s http://localhost:8000/
# 应返回 {"message":"可信模型计算平台 API","version":"1.0.0"}
```

### 3. 用脚本调用

**方式 A：Python 示例脚本（推荐）**

```bash
# 依赖：pip install requests
python examples/run_analysis.py
```

使用内置示例数据与 SQL，会请求 `http://localhost:8000/api/execute-sql` 并打印 JSON 结果。

**自定义 SQL：**

```bash
python examples/run_analysis.py --sql "SELECT category, SUM(value) as total FROM input_data GROUP BY category"
```

**数据从 JSON 文件读：**

```bash
echo '[{"id":1,"x":10},{"id":2,"x":20}]' > /tmp/data.json
python examples/run_analysis.py --data-json /tmp/data.json --sql "SELECT * FROM input_data"
```

**方式 B：curl**

```bash
curl -s -X POST http://localhost:8000/api/execute-sql \
  -H "Content-Type: application/json" \
  -d '{"data":[{"id":1,"value":100},{"id":2,"value":200}],"sql":"SELECT * FROM input_data"}'
```

### 4. 停止服务

```bash
docker-compose down
```

---

## 接口

**POST /api/execute-sql**

请求体（JSON）：

| 字段 | 必填 | 说明 |
|------|------|------|
| `data` | 是 | 表数据。每行可为 `[v1, v2, ...]` 或 `{"col1": v1, "col2": v2}` |
| `sql` | 是 | 要执行的 SQL，可查询插入后的表（默认表名 `input_data`） |
| `table_name` | 否 | 临时表名，默认 `input_data`（仅字母数字下划线） |
| `columns` | 条件 | 当 `data` 为「每行 list」时必填；为「每行 dict」时可从首行推断 |

返回：执行结果，含 `status`（`success` / `error`）、成功时 `result.columns` / `result.data` / `result.row_count`，失败时 `error`。数据在 MariaDB 临时表中执行，请求结束后临时表自动销毁。

---

## 亿行级：上传 CSV 文件 + SQL（推荐）

**POST /api/execute-sql/file**（`multipart/form-data`）

| 字段 | 必填 | 说明 |
|------|------|------|
| `file` | 是 | CSV 文件（由 MariaDB LOAD DATA LOCAL INFILE 入库，不占应用内存） |
| `sql` | 是 | 导入后要执行的 SQL（可查询表 `input_data`） |
| `table_name` | 否 | 临时表名，默认 `input_data` |
| `has_header` | 否 | 首行是否为列名，默认 `true` |
| `delimiter` | 否 | 列分隔符（单字符），默认 `,`；可传 `tab` 表示制表符 |
| `columns` | 否 | 列名逗号分隔；**不传 ddl 时**从首行推断用 |
| `ddl` | 否 | **表结构**：CREATE TABLE 括号内部分，如 `id INT, value DECIMAL(10,2), name VARCHAR(100)`。CSV 列顺序须与 DDL 列顺序一致。不传则从首行推断列名且类型均为 TEXT |

返回格式与上面相同。适合亿行级数据。提供 **ddl** 可指定列类型（INT/DECIMAL/VARCHAR/DATE 等），便于后续 SQL 按类型比较与聚合。

**curl 示例：**

```bash
# 不传 DDL：从 CSV 首行推断列名，类型均为 TEXT
curl -s -X POST http://localhost:8000/api/execute-sql/file \
  -F "file=@/path/to/data.csv" \
  -F "sql=SELECT * FROM input_data LIMIT 10"

# 传 DDL：指定表结构，CSV 列顺序须与 DDL 一致
curl -s -X POST http://localhost:8000/api/execute-sql/file \
  -F "file=@/path/to/data.csv" \
  -F "sql=SELECT * FROM input_data WHERE value > 100" \
  -F "ddl=id INT, value DECIMAL(10,2), category VARCHAR(50)"
```

**Python 示例：** 见 `examples/run_analysis_file.py`。

---

## 多表 + 连表 SQL（POST /api/execute-sql/files）

多个 CSV 分别对应多张临时表，再执行一条 SQL（可 JOIN 多表）。

**请求**：`multipart/form-data`

| 字段 | 说明 |
|------|------|
| `config` | JSON 字符串。`tables`: 数组，每项为 `{ "table_name", "ddl"? , "has_header"? , "delimiter"? , "columns"? }`；`sql`: 执行语句（可连表） |
| `files` | 多个文件，顺序与 `config.tables` 一致 |

**config 示例：**

```json
{
  "tables": [
    { "table_name": "orders", "ddl": "id INT, user_id INT, amount DECIMAL(10,2)", "has_header": true, "delimiter": "," },
    { "table_name": "users", "ddl": "id INT, name VARCHAR(100)", "has_header": true }
  ],
  "sql": "SELECT u.name, SUM(o.amount) FROM orders o JOIN users u ON o.user_id = u.id GROUP BY u.name"
}
```

**curl 示例：**

```bash
# config 为 JSON 字符串，tables 与 files 顺序一致
curl -s -X POST http://localhost:8000/api/execute-sql/files \
  -F 'config={"tables":[{"table_name":"orders","ddl":"id INT, user_id INT, amount DECIMAL(10,2)","has_header":true},{"table_name":"users","ddl":"id INT, name VARCHAR(100)","has_header":true}],"sql":"SELECT * FROM orders o JOIN users u ON o.user_id = u.id LIMIT 10"}' \
  -F "files=@orders.csv" \
  -F "files=@users.csv"
```

**Python 示例：** 见 `examples/run_analysis_files.py`。

### 多表 demo（可直接跑）

示例数据与配置已放在 `examples/` 下，服务起来后可直接执行：

```bash
# 方式一：Python（推荐）
pip install requests
python examples/run_demo_multi_table.py

# 方式二：Shell
bash examples/run_demo_multi_table.sh
```

用到的文件：
- `demo_orders.csv`：订单表（id, user_id, amount, created_at）
- `demo_users.csv`：用户表（id, name）
- `demo_multi_table_config.json`：多表 config，SQL 为按用户汇总订单金额的 JOIN 查询

预期返回中 `result.data` 示例：`[["Alice", 150.75], ["Bob", 288.80], ["Carol", 320.00]]`。

---

## 示例脚本

```bash
# 使用内置示例数据与 SQL
python examples/run_analysis.py

# 指定 API 地址
export TRUSTED_COMPUTE_API=http://localhost:8000
python examples/run_analysis.py

# 自定义 SQL
python examples/run_analysis.py --sql "SELECT category, SUM(value) as total FROM input_data GROUP BY category"

# 数据来自 JSON 文件（文件内容为 data 数组）
python examples/run_analysis.py --data-json /path/to/rows.json --sql "SELECT * FROM input_data LIMIT 10"
```

## 数据格式示例

**每行为 list（需传 columns）：**

```json
{
  "data": [[1, 100, "A"], [2, 200, "B"]],
  "columns": ["id", "value", "category"],
  "sql": "SELECT * FROM input_data WHERE value > 100"
}
```

**每行为 dict（可不传 columns）：**

```json
{
  "data": [
    {"id": 1, "value": 100, "category": "A"},
    {"id": 2, "value": 200, "category": "B"}
  ],
  "sql": "SELECT * FROM input_data"
}
```

## 启动服务（仅后端）

默认不启动前端，只起 MariaDB + 后端：

```bash
docker-compose up -d --build
```

需要前端时：`docker-compose --profile frontend up -d --build`。
