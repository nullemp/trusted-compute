# 客户端行为模拟（测试用）

本目录用于**模拟客户端**：先拉起本项目的后端与数据库，再调用 API（如 `POST /api/run-analysis`）做联调与测试。

---

## 一、前置：把项目跑起来

在**项目根目录**（与 `docker-compose.yml` 同级）任选一种方式启动服务（无需前端）：

**方式 A：Docker / Podman**

```bash
# 项目根目录执行
docker-compose up -d --build
# 或使用 Podman
# CONTAINER_RUNTIME=podman podman-compose up -d --build
# 或使用仓库提供的脚本（优先 Podman，否则 Docker）
./scripts/start-for-client.sh   # Linux/macOS
# .\scripts\start-for-client.ps1  # Windows
```

**方式 B：无 Docker（本机 MariaDB + Python）**

参见 [DEPLOY_CLIENT_NO_DOCKER.md](../DEPLOY_CLIENT_NO_DOCKER.md)，在本机起好 MariaDB 与后端后，保证 `http://localhost:8000` 可用。

---

## 二、运行模拟客户端

建议先等待 API 就绪，再发请求。

```bash
cd client-simulator
pip install -r requirements.txt   # 仅需 requests

# 等待 API 就绪（最多约 60 秒）
python wait_for_api.py

# 调用 /api/run-analysis：DDL 可选 + 数据文件 + SQL 分析
python run_analysis_demo.py

# 可选：再测 /api/execute-sql/files
python execute_sql_files_demo.py
```

环境变量（可选）：

- `TRUSTED_COMPUTE_API`：默认 `http://localhost:8000`，可改为实际地址。

---

## 三、一键启动并测试（可选）

在**项目根目录**执行，会先尝试用 Docker/Podman 启动服务，再等待 API，最后跑上述两个 demo：

```bash
# Linux/macOS
./scripts/start-for-client.sh
cd client-simulator && python wait_for_api.py && python run_analysis_demo.py && python execute_sql_files_demo.py

# Windows PowerShell（项目根）
.\scripts\start-for-client.ps1
cd client-simulator; python wait_for_api.py; python run_analysis_demo.py; python execute_sql_files_demo.py
```

---

## 四、目录说明

| 文件 | 说明 |
|------|------|
| `wait_for_api.py` | 轮询等待 `TRUSTED_COMPUTE_API` 就绪 |
| `run_analysis_demo.py` | 模拟客户端调用 `POST /api/run-analysis`（DDL + 数据文件 + SQL） |
| `execute_sql_files_demo.py` | 模拟客户端调用 `POST /api/execute-sql/files` |
| `run_tests.sh` / `run_tests.cmd`（推荐）/ `run_tests.ps1` | 依次执行：等待 API → run_analysis_demo → execute_sql_files_demo |
| `data/` | 演示用 CSV（orders.csv、users.csv）与可选 DDL（schema.sql） |
