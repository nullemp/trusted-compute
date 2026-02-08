# 跑通 Demo 完整流程

从零开始，用**一条主线**把项目起起来并跑通客户端模拟脚本。

---

## 方式一：用 Podman 或 Docker（推荐）

### 1. 准备环境

- 本机已安装 **Podman** 或 **Docker**（二选一即可，脚本会优先用 Podman）。
- 若用 Podman，需再装 **podman-compose**（如 `pip install podman-compose` 或系统包）。

### 2. 启动服务（后端 + MariaDB，无前端）

在**项目根目录**（有 `docker-compose.yml` 的目录）执行：

```bash
# Linux / macOS
./scripts/start-for-client.sh
```

```powershell
# Windows PowerShell（项目根目录）
.\scripts\start-for-client.ps1
```

脚本会优先用 Podman，没有再用 Docker，执行 `up -d --build`，启动 MariaDB 与 backend。  
等待约 30 秒～1 分钟（首次会拉镜像、构建）。

### 3. 跑客户端模拟（发请求、看结果）

```bash
cd client-simulator
pip install -r requirements.txt
python wait_for_api.py
python run_analysis_demo.py
python execute_sql_files_demo.py
```

或一键执行：

```bash
cd client-simulator
pip install -r requirements.txt
./run_tests.sh          # Linux/macOS
# .\run_tests.cmd       # Windows（推荐，避免执行策略限制）；或 .\run_tests.ps1
```

看到两次「完成」、有 `result` 数据即表示跑通。

### 4. 可选：看 API 文档

浏览器打开：**http://localhost:8000/docs**

---

## 方式二：不用容器（本机 MariaDB + Python）

### 1. 准备环境

- 安装 **MariaDB 10.6+**，并启动服务。
- 安装 **Python 3.11+**。

### 2. 建库建用户

在 MariaDB 里执行：

```sql
CREATE DATABASE trusted_compute_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'trusted_compute'@'%' IDENTIFIED BY 'trusted_compute_pass';
GRANT ALL ON trusted_compute_db.* TO 'trusted_compute'@'%';
FLUSH PRIVILEGES;
```

### 3. 启动后端

在**项目根目录**：

```bash
cd backend
pip install -r requirements.txt
```

然后设置环境变量并启动（按系统选一种）：

**Windows PowerShell：**

```powershell
$env:DATABASE_URL = "mysql+pymysql://trusted_compute:trusted_compute_pass@localhost:3306/trusted_compute_db"
$env:SANDBOX_MODE = "local"
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Linux / macOS：**

```bash
export DATABASE_URL="mysql+pymysql://trusted_compute:trusted_compute_pass@localhost:3306/trusted_compute_db"
export SANDBOX_MODE=local
uvicorn main:app --host 0.0.0.0 --port 8000
```

保持该终端不关。

### 4. 跑客户端模拟

**新开一个终端**，在项目根目录：

```bash
cd client-simulator
pip install -r requirements.txt
python wait_for_api.py
python run_analysis_demo.py
python execute_sql_files_demo.py
```

或：

```bash
cd client-simulator
pip install -r requirements.txt
./run_tests.sh          # Linux/macOS
# .\run_tests.cmd       # Windows（推荐，避免执行策略限制）；或 .\run_tests.ps1
```

---

## 一条龙命令（方式一：有 Podman/Docker 时）

在**项目根目录**一次性执行（Linux/macOS 示例）：

```bash
./scripts/start-for-client.sh && \
cd client-simulator && \
pip install -q -r requirements.txt && \
python wait_for_api.py && \
python run_analysis_demo.py && \
python execute_sql_files_demo.py && \
echo "=== Demo 全部跑通 ==="
```

Windows PowerShell（项目根目录）：

```powershell
.\scripts\start-for-client.ps1; cd client-simulator; pip install -q -r requirements.txt; python wait_for_api.py; python run_analysis_demo.py; python execute_sql_files_demo.py; Write-Host "=== Demo 全部跑通 ==="
```

---

## 预期结果

- **run_analysis_demo.py**：返回 `status: success`，`result` 里是按用户汇总的订单金额（如 Alice、Bob、Carol 的 total）。
- **execute_sql_files_demo.py**：同样返回成功及连表查询结果。
- 若某一步报错，可根据报错信息查 [DEPLOY_CLIENT_NO_DOCKER.md](DEPLOY_CLIENT_NO_DOCKER.md)、[client-simulator/README.md](client-simulator/README.md) 或 API 文档 http://localhost:8000/docs 排查。
