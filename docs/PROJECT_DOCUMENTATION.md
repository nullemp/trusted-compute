# Trusted Compute Sandbox 项目文档

本文档面向开发、运维与测试人员，描述项目结构、核心逻辑、部署与验证方式。

---

## 1. 项目概述

### 1.1 功能与用途

**Trusted Compute Sandbox** 是一个**沙箱计算服务**，在隔离容器内执行 SQL（MariaDB）与 Python 代码，结果直接返回。采用**实例隔离**：每个沙箱对应一个独立 MariaDB 容器与数据卷，创建/销毁由 API 控制，数据与计算逻辑在沙箱销毁时一并清除。

主要能力：

- **创建沙箱**：为数据流通/协作任务分配独立 DB 容器与数据卷，返回唯一 `sandbox_id`。
- **数据导入与 SQL 执行**：在指定沙箱的 MariaDB 中执行 DDL、插入数据、执行查询；支持单表/多表、CSV/JSON 等数据形态。
- **数据聚合**：通过 Python 沙箱执行脚本（pandas/numpy），支持按维度汇总统计。
- **销毁沙箱**：停止并删除 DB 容器及关联数据卷，实现数据与计算逻辑的彻底清理。

### 1.2 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.11+ |
| Web 框架 | FastAPI |
| 运行时 | Uvicorn |
| 数据库 | MariaDB（每沙箱独立容器，无共享常驻实例） |
| 容器 | Podman（推荐）/ Docker，Compose 编排 |
| 沙箱内 SQL | PyMySQL（连接 MariaDB） |
| 沙箱内计算 | pandas、numpy |

### 1.3 项目定位与目标用户

- **定位**：轻量级可信计算沙箱，便于理解多方安全计算与隔离执行；生产环境可考虑 FATE、SecretFlow 等方案。
- **目标用户**：需要“临时沙箱 + 独立 DB + 按任务销毁”的接入方；内网/离线部署场景；开发与演示 SQL/Python 沙箱执行流程的团队。

---

## 2. 系统架构

### 2.1 目录结构（模块列表）

```
trusted-compute/
├── backend/                    # 后端服务
│   ├── main.py                 # FastAPI 应用入口、路由
│   ├── schemas.py              # 请求/响应 Pydantic 模型
│   ├── requirements.txt        # Python 依赖
│   ├── Dockerfile              # 后端镜像构建
│   ├── services/
│   │   ├── __init__.py
│   │   ├── sandbox_service.py      # 沙箱执行：调用容器运行 runner
│   │   └── sandbox_db_lifecycle.py # 沙箱 DB 生命周期：创建/销毁/IP 查询
│   └── sandbox/                # 沙箱镜像（runner 所在）
│       ├── Dockerfile         # 多阶段构建，pandas+numpy+pymysql
│       └── runner.py           # 容器入口：stdin JSON → 执行 SQL/Python → stdout JSON
├── examples/                   # 示例与演示
│   ├── demo.py                 # 入口，调用 run_sql_examples
│   ├── run_sql_examples.py     # 完整 SQL 示例：创建沙箱→执行 SQL→销毁沙箱
│   ├── wait_for_api.py         # 等待 API 就绪
│   ├── requirements.txt        # 示例依赖（如 requests）
│   └── data/
│       ├── dbprofile.sql       # 建表 DDL（MariaDB 语法）
│       ├── query.sql           # 示例查询 SQL
│       ├── users.csv / orders.csv
├── scripts/                    # 启动/停止/导出脚本
│   ├── start-for-client.ps1/.cmd   # Windows 启动
│   ├── start-for-client.sh     # Linux/macOS 启动
│   ├── stop-for-client.*       # 停止
│   ├── export-images-for-offline.*  # 导出镜像与 wheels 供内网
│   └── download-examples-wheels.*  # 下载示例 Python 依赖
├── runtime/                    # 运行时与离线资源
│   ├── images/                 # 离线镜像 tar（backend/sandbox/mariadb）
│   └── docker/                 # 可选：docker-compose.exe（与 Podman 配合）
├── docs/                       # 文档
│   ├── SQL_USAGE.md
│   ├── OFFLINE_DEPLOY.md
│   └── PROJECT_DOCUMENTATION.md（本文档）
├── docker-compose.yml          # 服务与网络定义
├── README.md
├── WSL_SETUP_WINDOWS.md
└── ENV_VARS_WINDOWS.md
```

### 2.2 模块功能与关系

| 模块 | 功能 | 输入 | 输出 | 依赖 |
|------|------|------|------|------|
| **main** | HTTP 路由、参数校验、调用服务层 | HTTP 请求 | JSON 响应 | schemas, sandbox_service, sandbox_db_lifecycle |
| **schemas** | 请求体/响应体模型定义 | - | Pydantic 模型 | pydantic |
| **sandbox_service** | 构造 payload、调用容器运行时执行 runner | sql/ddl/tables 或 code/input_params | 容器 stdout 解析后的 JSON | sandbox_db_lifecycle（host/ip/exists） |
| **sandbox_db_lifecycle** | 沙箱 DB 容器与卷的创建/销毁/IP 查询 | sandbox_id 或无（创建） | sandbox_id、成功/失败、IP 等 | 主机上的 podman/docker CLI |
| **runner** | 容器内执行：读 stdin JSON，跑 SQL 或 Python，写 stdout JSON | stdin JSON（model_type, model_code, input_params） | stdout JSON（status, result/error） | pymysql, pandas, numpy |

### 2.3 架构图（ASCII）

```
                    +------------------+
                    |   Client / 示例   |
                    | (run_sql_examples)|
                    +--------+---------+
                             | HTTP
                             v
+------------------------------------------------------------------+
|                     Backend (FastAPI, 端口 8000)                  |
|  +----------+  +------------------+  +------------------------+  |
|  | main.py  |  | sandbox_service  |  | sandbox_db_lifecycle    |  |
|  | 路由/校验 |->| 组 payload、调容器 |  | 创建/销毁 DB 容器与卷   |  |
|  +----------+  +--------+---------+  +------------+-----------+  |
+------------------------------------------------------------------+
                             | subprocess (podman/docker run)
                             v
              +------------------------------+
              | Runner 容器 (trusted-compute- |
              | sandbox)，--network 与 DB 同网 |
              | stdin: JSON → runner.py       |
              | stdout: JSON ← 执行结果        |
              +--------------+----------------+
                             | TCP (PyMySQL)
                             v
              +------------------------------+
              | 沙箱 DB 容器 (tc-sandbox-db-  |
              | <id>)，独立数据卷，按需创建   |
              | MariaDB                       |
              +------------------------------+
```

**依赖关系简述**：main 依赖 schemas 与 services；sandbox_service 依赖 sandbox_db_lifecycle 解析 DB 连接（IP/主机名）并检查沙箱存在；runner 在容器内依赖 payload 中的 `_mariadb` 或环境变量连接对应沙箱的 MariaDB。

---

## 3. 核心实现逻辑

### 3.1 模块：main（FastAPI 应用）

- **输入**：HTTP 请求（GET /；POST /api/sandboxes、/api/execute-sql、/api/execute-python；DELETE /api/sandboxes/{sandbox_id}）。
- **处理**：  
  - 路由到对应 handler；  
  - 请求体验 Pydantic 校验（ExecuteSqlRequest / ExecutePythonRequest）；  
  - 调用 `create_sandbox()` / `destroy_sandbox()` / `sandbox_service.execute_sql()` / `sandbox_service.execute_python()`。
- **输出**：JSON 响应（如 `{sandbox_id}`、`{status, result}`、`{status, error}`）或 HTTPException。

**主要调用顺序**（以执行 SQL 为例）：  
`POST /api/execute-sql` → `execute_sql(req)` → `req.sandbox_id, req.sql, req.ddl, req.tables` 等 → `sandbox_service.execute_sql(...)` → 返回 runner 输出并带 `execution_time_ms`。

### 3.2 模块：schemas

- **输入**：无（模型定义）。
- **处理**：定义 `TableSpec`、`ExecuteSqlRequest`（含 sandbox_id、sql、ddl、data/table_name/columns 或 tables）、`ExecutePythonRequest`（code、input_params）。
- **输出**：供 FastAPI 做请求体校验与序列化。

### 3.3 模块：sandbox_service

- **输入**：  
  - **execute_sql**：sandbox_id, sql, ddl, data/table_name/columns 或 tables。  
  - **execute_python**：code, input_params。
- **处理**：  
  1. **execute_sql**：  
     - `sandbox_exists(sandbox_id)` 校验；  
     - 组装 `input_params`（含 ddl/tables 或 data/table_name/columns）；  
     - 取 DB 连接：`_host = sandbox_db_ip(sandbox_id) or sandbox_db_host(sandbox_id)`，写入 `input_params["_mariadb"]`；  
     - 构造 payload：`model_type=sql`，`model_code=sql`，`input_params`；  
     - `_run_payload(payload, use_network=True, container_env=mariadb_env)` → 内部 `_run_docker(stdin_bytes, use_network=True, container_env=...)`，即 `podman/docker run --rm -i --network trusted-compute_default -e MARIADB_* <sandbox_image>`，stdin 为 JSON；  
     - 解析容器 stdout JSON，附加 `execution_time_ms`。  
  2. **execute_python**：  
     - 构造 payload（model_type=python），`_run_payload(..., use_network=False)`（无网络）。
- **输出**：`{ "status": "success"|"error", "result"|"error", "execution_time_ms"? }`。

**关键依赖**：主机上的 podman 或 docker、镜像 `trusted-compute-sandbox`、环境变量 `SANDBOX_NETWORK`/`MARIADB_ROOT_PASSWORD` 等；与 `sandbox_db_lifecycle` 的 `sandbox_db_ip`/`sandbox_db_host`/`sandbox_exists` 配合。

### 3.4 模块：sandbox_db_lifecycle

- **输入**：  
  - **create_sandbox**：无。  
  - **destroy_sandbox**：sandbox_id。  
  - **sandbox_db_ip** / **sandbox_db_host** / **sandbox_exists**：sandbox_id。
- **处理**：  
  - **create_sandbox**：生成 sandbox_id；创建卷 `tc-sandbox-data-<id>`；`podman/docker run -d --name tc-sandbox-db-<id> -v <volume>:/var/lib/mysql --network trusted-compute_default -e MARIADB_ROOT_PASSWORD <mariadb_image>`；`_wait_mariadb_ready(container, ...)` 轮询直至可连接；失败则 stop/rm 容器并删卷。  
  - **destroy_sandbox**：stop 容器 → rm 容器 → rm 卷。  
  - **sandbox_db_ip**：`inspect` 容器，取 `NetworkSettings.Networks["trusted-compute_default"].IPAddress`。  
  - **sandbox_db_host**：返回 `tc-sandbox-db-<sandbox_id>`。  
  - **sandbox_exists**：`ps -q --filter name=^tc-sandbox-db-<id>$` 判断是否在运行。
- **输出**：create 返回 (sandbox_id, None) 或 (None, error)；destroy 返回 (ok, error_message)；ip/host/exists 返回 IP 字符串、主机名字符串、布尔。

**调用顺序（创建沙箱后执行 SQL）**：  
`create_sandbox()` → volume create → run MariaDB 容器 → _wait_mariadb_ready → 返回 sandbox_id；  
后续 `execute_sql(sandbox_id, ...)` 中 `sandbox_db_ip(sandbox_id)` → `_run_payload` 启动 runner 并传入 `_mariadb.host=IP`。

### 3.5 模块：runner（容器内）

- **输入**：stdin 一行 JSON：`{ "model_type": "sql"|"python", "model_code": "<sql 或 code>", "input_params": { ... } }`。  
  - SQL 时 input_params 含 `ddl`、`tables` 或 `data`/`table_name`/`columns`，以及 `_mariadb`（host/port/user/password）。
- **处理**：  
  - **SQL 分支**：  
    - 从 `input_params["_mariadb"]` 或环境变量取连接参数；  
    - 创建临时 database `sandbox_<uuid>`；  
    - 若有 ddl 先执行 DDL（_normalize_ddl_for_mariadb），再按 tables 插入；若无 ddl 则按 data/tables 自动建表并插入；  
    - 执行用户 SQL（多条时取第一条有结果集的）；  
    - 关闭连接后 DROP DATABASE；  
    - 返回 `{ status, type: "sql", result: { columns, data, row_count } }` 或 error。  
  - **Python 分支**：exec(model_code)，从局部命名空间取 `result`，按 DataFrame/dict/list 等序列化为统一结构并返回。
- **输出**：stdout 一行 JSON（success 含 result，error 含 error 字符串）。

**关键依赖**：容器内 pymysql、pandas、numpy；与 backend 约定 payload 格式及 `_mariadb` 传递方式；网络需能访问沙箱 DB 容器（同网或使用 IP）。

---

## 4. 部署说明

### 4.1 依赖与环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows（需 WSL + Podman Machine）/ Linux / macOS |
| 容器运行时 | Podman（推荐）或 Docker；需可挂载 socket 供 backend 调起容器 |
| Python（仅运行示例） | 3.x，pip 安装 examples/requirements.txt（如 requests） |
| 网络 | 首次构建/拉取需可访问镜像仓库；内网见 4.3 |

**后端依赖（backend/requirements.txt）**：  
fastapi==0.104.1, uvicorn[standard]==0.24.0, pydantic==2.5.0, python-multipart==0.0.6, pymysql==1.1.0

**示例依赖（examples/requirements.txt）**：  
requests>=2.28.0

### 4.2 配置说明

- **配置文件**：无独立配置文件；行为由**环境变量**与 **docker-compose.yml** 决定。
- **关键环境变量**（backend 容器或启动前导出）：
  - `SANDBOX_IMAGE`：runner 镜像名，默认 `trusted-compute-sandbox`。
  - `CONTAINER_RUNTIME`：`podman` 或 `docker`。
  - `SANDBOX_NETWORK`：沙箱 DB 与 runner 所在网络，默认 `trusted-compute_default`。
  - `MARIADB_ROOT_PASSWORD`：沙箱 MariaDB root 密码。
  - `MARIADB_IMAGE`：MariaDB 镜像，用于创建沙箱 DB 容器。
  - `SANDBOX_RUN_TIMEOUT`：单次 runner 容器执行超时（秒），默认 120。
- **docker-compose.yml**：定义 backend、sandbox（仅构建镜像）；网络 `trusted-compute_default`；backend 挂载 `./backend` 与 Docker/Podman socket。

### 4.3 启动命令与脚本

- **推荐（项目根目录）**：  
  - Windows：`scripts\start-for-client.cmd` 或 `scripts\start-for-client.ps1`  
  - Linux/macOS：`scripts/start-for-client.sh`  
  脚本会：检测/启动 Podman Machine（Windows）、加载 runtime/images 下 tar（若有）、**重建 sandbox 镜像**（若有离线镜像）、执行 compose up。
- **直接 Compose**：  
  `podman compose up -d --build`（或 `docker compose` / `docker-compose`）。
- **停止**：  
  `scripts\stop-for-client.cmd`（或 .ps1 / .sh）；或 `podman compose down`。

**内网/离线**：  
在联网环境执行 `scripts\export-images-for-offline.cmd`（或 .sh），将 backend、sandbox、mariadb 镜像及可选 examples 依赖打包；拷贝整份项目到内网后，同一启动脚本会 load 镜像并 `--no-build` 启动，且会重建 sandbox 镜像以保证 runner 代码最新。详见 docs/OFFLINE_DEPLOY.md、runtime/images/README.md。

### 4.4 注意事项

- **端口**：backend 暴露 8000，确保无冲突；MariaDB 仅容器间访问，不暴露宿主机端口。
- **防火墙**：若从本机外访问 API，需放行 8000。
- **日志**：backend 为 uvicorn 标准输出；runner 容器 stdout/stderr 由 backend 捕获并解析，错误通过 API 返回。
- **权限**：backend 需能执行 podman/docker 并挂载其 socket（如 /var/run/docker.sock 或 Windows npipe）。
- **Windows**：需 WSL 与 Podman Machine；若使用 runtime\docker\docker-compose.exe，脚本会将 runtime\docker 加入 PATH 以便 `podman compose` 找到 compose 提供程序。

---

## 5. 测试和验证

### 5.1 单元测试与接口测试

- 项目**未内置** pytest/unittest 用例；可通过 API 与示例脚本做**接口级与端到端验证**。
- **接口测试**：  
  - 使用 Swagger：打开 http://localhost:8000/docs，对 GET /、POST /api/sandboxes、POST /api/execute-sql、DELETE /api/sandboxes/{id}、POST /api/execute-python 进行手测。  
  - 或使用 curl/Postman 按上述路由与请求体格式调用。

### 5.2 测试命令与示例

1. **健康检查**：  
   `curl -s http://localhost:8000/`  
   预期：`{"message":"Trusted Compute Sandbox API","version":"1.0.0"}`。

2. **等待 API 就绪**（可选）：  
   `python examples/wait_for_api.py`

3. **完整 SQL 示例（创建沙箱 → 执行 SQL → 销毁沙箱）**：  
   `pip install -r examples/requirements.txt`  
   `python examples/run_sql_examples.py`  
   脚本会：GET / 健康检查 → POST /api/sandboxes 创建沙箱 → 多次 POST /api/execute-sql（ddl + tables + sql）→ finally DELETE /api/sandboxes/{sandbox_id}。

4. **单接口示例**：  
   - 创建沙箱：`curl -X POST http://localhost:8000/api/sandboxes`  
   - 执行 SQL：`curl -X POST http://localhost:8000/api/execute-sql -H "Content-Type: application/json" -d '{"sandbox_id":"<上一步返回的 id>","sql":"SELECT 1","tables":[]}'`  
   - 销毁沙箱：`curl -X DELETE http://localhost:8000/api/sandboxes/<sandbox_id>`

### 5.3 核心功能验证点

- 创建沙箱返回 200 且含 `sandbox_id`；同一 sandbox_id 可多次 execute-sql。
- execute-sql 在传入合法 ddl/tables 或 data 时返回 `status: "success"` 及 `result.columns`/`result.data`/`result.row_count`；错误时返回 `status: "error"` 及 `error`。
- execute-python 在代码中设置 `result` 后返回对应序列化结果。
- 销毁沙箱后，再对该 sandbox_id 执行 execute-sql 应返回“沙箱不存在或已销毁”类错误。
- 内网/离线：启动脚本能完成 load 与 sandbox 重建，且 run_sql_examples 全程无外网请求。

---

## 6. 附录

### 6.1 配置示例

**docker-compose 片段（环境变量）**：

```yaml
environment:
  SANDBOX_IMAGE: trusted-compute-sandbox
  CONTAINER_RUNTIME: podman
  SANDBOX_NETWORK: trusted-compute_default
  MARIADB_ROOT_PASSWORD: your_secure_password
  MARIADB_IMAGE: docker.io/library/mariadb:11.2
```

**示例脚本指定 API 地址**：  
`set TRUSTED_COMPUTE_API=http://192.168.1.100:8000` 后运行 `python examples/run_sql_examples.py`。

### 6.2 日志说明

- **Backend**：uvicorn 访问日志与应用 print（如 “Sandbox: starting container …”）输出到容器 stdout，无单独日志文件。
- **Runner**：容器内无持久化日志；错误通过 stdout JSON 的 `status: "error", error: "..."` 返回给 backend，再返回给客户端。
- **Podman/Docker**：容器/镜像操作依赖主机上的运行时日志（如 `podman logs`、journal 等），本项目不单独配置。

### 6.3 参考资料

- 项目根目录 **README.md**：快速开始、API 列表、示例与内网部署概要。
- **docs/SQL_USAGE.md**：SQL 接口与 ddl/tables/data 使用说明。
- **docs/OFFLINE_DEPLOY.md**：内网/离线部署完整流程。
- **runtime/images/README.md**：离线镜像目录与 load 说明。
- **WSL_SETUP_WINDOWS.md**：Windows 下 WSL 与 Podman 准备。
- **ENV_VARS_WINDOWS.md**：Windows 环境变量与路径说明。
- **examples/DEMO_FLOW.md**：demo.py / run_sql_examples 的端到端流程说明。
