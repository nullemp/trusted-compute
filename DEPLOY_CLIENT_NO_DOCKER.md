# 客户环境无 Docker 部署说明

客户机上**不安装 Docker**、**不需要前端**时，按本说明部署：在客户机上安装 **MariaDB** 和 **Python**，启动后端即可；客户端进程通过 HTTP 调用 API（如 `POST /api/run-analysis`）。

> **若改用容器**：客户机可用 Podman/Docker 跑整套服务（见 [DOCKER_IN_CLIENT.md](DOCKER_IN_CLIENT.md)），则**无需在客户机上装 MariaDB 和 Python**，数据库与后端均在容器内运行。

---

## 一、客户机需要安装的组件

| 组件 | 版本要求 | 说明 |
|------|----------|------|
| **MariaDB** | 10.6+ | 或 MySQL 5.7+，用于存业务库；执行 DDL、导入数据、SQL 分析均在此库或临时库中 |
| **Python** | 3.11+ | 运行后端；任务中的 Python 分析在本地子进程中执行，无需 Docker |

**不需要**：Docker、Node.js、前端构建。

---

## 二、部署步骤

### 1. 安装并启动 MariaDB

- Windows：从 [MariaDB 官网](https://mariadb.org/download/) 下载安装包安装。
- Linux：`sudo apt install mariadb-server` 或 `yum install mariadb-server`，并启动服务。

### 2. 创建数据库与用户

用 MariaDB 客户端或命令行执行（密码可按需修改）：

```sql
CREATE DATABASE trusted_compute_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'trusted_compute'@'%' IDENTIFIED BY 'trusted_compute_pass';
GRANT ALL ON trusted_compute_db.* TO 'trusted_compute'@'%';
FLUSH PRIVILEGES;
```

记下连接串，例如：`mysql+pymysql://trusted_compute:trusted_compute_pass@localhost:3306/trusted_compute_db`。

### 3. 部署后端代码并安装依赖

将项目中的 **backend** 目录拷贝到客户机，然后：

```bash
cd backend
python -m venv .venv
```

**Windows（PowerShell）：**

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Linux / macOS：**

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. 配置环境变量（无 Docker 必设）

**Windows（PowerShell，当前会话）：**

```powershell
$env:DATABASE_URL = "mysql+pymysql://trusted_compute:trusted_compute_pass@localhost:3306/trusted_compute_db"
$env:SANDBOX_MODE = "local"
```

**Windows（CMD）：**

```cmd
set DATABASE_URL=mysql+pymysql://trusted_compute:trusted_compute_pass@localhost:3306/trusted_compute_db
set SANDBOX_MODE=local
```

**Linux / macOS：**

```bash
export DATABASE_URL="mysql+pymysql://trusted_compute:trusted_compute_pass@localhost:3306/trusted_compute_db"
export SANDBOX_MODE=local
```

- **DATABASE_URL**：必须设为本机或可访问的 MariaDB 连接串。  
- **SANDBOX_MODE=local**：必须设置，否则任务执行会尝试调 Docker 并报错。设为 `local` 后，SQL/Python 分析在本地 Python 子进程中执行，不依赖 Docker。

### 5. 启动后端

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

保持该进程运行。服务地址：`http://<本机IP>:8000`，API 文档：`http://<本机IP>:8000/docs`。

---

## 三、客户端如何调用

- 无需浏览器、无需前端页面；客户端进程（脚本、自研程序等）直接发 HTTP 请求即可。
- 推荐入口：**POST /api/run-analysis**（传 DDL、数据文件、分析 SQL 或 Python）。
- 请求格式、参数说明、示例见 **[CLIENT_API.md](CLIENT_API.md)**。

---

## 四、环境变量汇总（客户环境无 Docker）

| 变量 | 必填 | 说明 |
|------|------|------|
| `DATABASE_URL` | 是 | MariaDB/MySQL 连接串 |
| `SANDBOX_MODE` | 是 | 必须设为 `local`，否则会尝试使用 Docker |

---

## 五、安全与隔离说明

- **SANDBOX_MODE=local** 时，用户提交的 SQL 与 Python 代码在**本机 Python 子进程**中执行，**无容器隔离**，仅适合**可信环境**（如内网、仅可信客户端调用）。若需强隔离，需在客户环境提供 Docker 或其它隔离方案。

---

## 六、故障排查

- **执行任务报错提示 Docker**：检查是否已设置 `SANDBOX_MODE=local` 并重启后端。
- **数据库连接失败**：检查 MariaDB 是否启动、`DATABASE_URL` 的主机/端口/用户名/密码/库名是否正确。
- **端口占用**：可改为 `--port 8080` 等其它端口。

更多无 Docker 的通用说明见 [DEPLOY_WITHOUT_DOCKER.md](DEPLOY_WITHOUT_DOCKER.md)。
