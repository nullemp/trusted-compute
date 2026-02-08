# 无 Docker 环境部署说明

当客户环境无法安装或使用 Docker 时，可按以下方式部署：**单独安装 MariaDB、Python 后端、前端**，并通过环境变量启用「本地沙箱」模式，使任务在本地 Python 子进程中执行（无容器隔离）。

---

## 一、架构差异简要说明

| 项目         | 有 Docker 时                     | 无 Docker 时                         |
| ------------ | --------------------------------- | ------------------------------------ |
| 数据库       | 容器 `mariadb:11`（MariaDB）     | 本机或单独服务器安装 MariaDB         |
| 后端         | 容器内 Python + 挂载 docker.sock | 本机 Python + 直连 MariaDB           |
| 前端         | 容器内 Node 开发服务器           | 本机 Node 构建后由 Nginx/后端托管    |
| 任务沙箱     | 每次 `docker run` 新容器执行     | `SANDBOX_MODE=local` 时本地子进程执行 |

**安全说明**：`SANDBOX_MODE=local` 下任务代码在与后端同一台机器上、以子进程方式执行，**无隔离**，仅适用于**可信环境**（如内网、仅可信用户提交任务）。若需强隔离，必须使用 Docker（或其它隔离方案）。

---

## 二、环境准备

- **MariaDB 10.6+**
- **Python 3.11+**（后端 + 沙箱依赖：pandas、numpy 等，见 `backend/requirements.txt`）
- **Node.js 18+**（仅用于构建前端静态资源；运行时也可用 Nginx 等托管）

---

## 三、数据库

1. 安装并启动 MariaDB。
2. 创建库与用户（与 docker-compose 中一致即可）：

```sql
CREATE DATABASE trusted_compute_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'trusted_compute'@'%' IDENTIFIED BY 'trusted_compute_pass';
GRANT ALL ON trusted_compute_db.* TO 'trusted_compute'@'%';
FLUSH PRIVILEGES;
```

3. 记下连接信息，例如：`mysql+pymysql://trusted_compute:trusted_compute_pass@<MariaDB 主机>:3306/trusted_compute_db`。

---

## 四、后端（Python）

1. 进入后端目录并创建虚拟环境（推荐）：

```bash
cd backend
python3 -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

2. 配置环境变量（无 Docker 时需显式设置数据库地址，并启用本地沙箱）：

```bash
# 必选：MariaDB 连接（按实际主机/端口修改）
export DATABASE_URL="mysql+pymysql://trusted_compute:trusted_compute_pass@localhost:3306/trusted_compute_db"

# 无 Docker 时必选：使用本地子进程执行任务（无容器隔离）
export SANDBOX_MODE=local

# 可选
export SECRET_KEY="your-secret-key-change-in-production"
```

3. 启动后端：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

本地沙箱会使用当前 Python 解释器执行 `backend/sandbox/runner.py`，依赖已由 `requirements.txt` 中的 pandas、numpy 满足，无需再装 Docker。

---

## 五、前端

### 方式 A：本机开发服务器（适合联调）

```bash
cd frontend
npm install
# 确保请求发往后端地址，例如 .env 或 build 时 REACT_APP_API_URL=http://localhost:8000
npm start
```

浏览器访问前端提供的地址（如 http://localhost:3000），API 指向后端 8000 端口。

### 方式 B：构建静态资源后由 Nginx/后端托管（适合生产）

```bash
cd frontend
npm install
REACT_APP_API_URL=http://<后端对外地址>:8000 npm run build
```

将 `build/` 目录部署到 Nginx 或其它 Web 服务器，或由后端挂静态路由（需自行在 FastAPI 中配置 `StaticFiles`）。

---

## 六、环境变量汇总（无 Docker）

| 变量             | 必填 | 说明 |
| ---------------- | ---- | ---- |
| `DATABASE_URL`   | 是   | MariaDB 连接串，如 `mysql+pymysql://user:pass@host:3306/dbname` |
| `SANDBOX_MODE`   | 无 Docker 时为是 | 设为 `local` 时用本地子进程执行任务，不依赖 Docker |
| `SECRET_KEY`     | 建议 | 生产环境务必修改 |

未设置 `SANDBOX_MODE` 时默认为 `docker`，若本机无 Docker 或未挂载 docker.sock，执行任务会报错并提示可设置 `SANDBOX_MODE=local`。

---

## 七、小结

- **无 Docker 时**：安装 MariaDB + Python 后端 + 前端（Node 仅用于构建），后端设置 `DATABASE_URL` 与 `SANDBOX_MODE=local` 即可运行并执行任务。
- **本地沙箱**：任务在与后端同机的 Python 子进程中执行，无进程/网络隔离，仅适用于可信环境；若客户需要强隔离，仍需提供 Docker 或等价隔离方案。
