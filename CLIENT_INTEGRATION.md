# 集成到客户端说明（不依赖客户机 Docker/Node）

本说明面向**将可信模型计算平台集成进自有客户端**的场景：不假设客户机上已安装 Docker 或 Node.js；**数据库使用 MariaDB/MySQL**（由客户机自装或随客户端一起部署）。

---

## 一、目标与原则

- **不依赖客户机 Docker/Node**：不要求客户安装 Docker、Node；前端由后端托管静态资源。
- **单进程对外**：一个后端进程同时提供 API 与 Web 界面（前端 build 放到 `backend/static/`）。
- **数据库**：使用 **MariaDB/MySQL**，连接串通过 `DATABASE_URL` 配置（客户机需能访问到数据库）。
- **任务执行**：无 Docker 时使用 `SANDBOX_MODE=local`，在本地子进程中执行任务（仅适用于可信环境）。

---

## 二、运行时依赖（客户机）

- **MariaDB 10.6+ 或 MySQL**：必须。客户机本机安装，或连接既有数据库服务。
- **Python 3.11+**：运行后端（或通过 PyInstaller 等打成单可执行文件则可不装 Python）。
- **前端**：无需 Node，由后端挂出 `static/` 目录即可。

---

## 三、集成步骤

### 1. 数据库

在 MariaDB/MySQL 中创建库与用户（与 docker-compose 一致即可）：

```sql
CREATE DATABASE trusted_compute_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'trusted_compute'@'%' IDENTIFIED BY 'trusted_compute_pass';
GRANT ALL ON trusted_compute_db.* TO 'trusted_compute'@'%';
FLUSH PRIVILEGES;
```

记下连接信息，例如：`mysql+pymysql://trusted_compute:trusted_compute_pass@localhost:3306/trusted_compute_db`。

### 2. 准备后端

- 使用项目中的 `backend/` 目录。
- 安装依赖（在开发/打包机上执行一次）：
  ```bash
  cd backend
  pip install -r requirements.txt
  ```

### 3. 构建前端静态资源（在开发/打包机执行一次）

- 构建时让前端请求**同源**（即由后端同一端口提供 API）：
  ```bash
  cd frontend
  npm install
  set REACT_APP_API_URL=          # Windows: 留空表示同源
  npm run build
  ```
  Linux/macOS：`export REACT_APP_API_URL= && npm run build`

- 将 `frontend/build/` 下**全部内容**复制到 `backend/static/`（若没有 `static` 目录则新建）。
  - 即：`backend/static/index.html`、`backend/static/static/` 等与 build 输出一致。

### 4. 启动方式（客户机）

在客户机上运行后端，并配置好 MariaDB 连接与本地沙箱：

```bash
cd backend
set DATABASE_URL=mysql+pymysql://trusted_compute:trusted_compute_pass@localhost:3306/trusted_compute_db
set SANDBOX_MODE=local
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

- **DATABASE_URL**：必填，指向客户机可访问的 MariaDB/MySQL。
- **SANDBOX_MODE=local**：无 Docker 时必设，任务在本机子进程执行。
- 若已按步骤 3 放置 `backend/static/`，则：
  - 打开浏览器访问 **http://&lt;本机&gt;:8000/** 即为 Web 界面；
  - API 为 **http://&lt;本机&gt;:8000/api/...**，文档为 **http://&lt;本机&gt;:8000/docs**。

### 5. 环境变量汇总（集成模式）

| 变量 | 必填 | 说明 |
|------|------|------|
| `DATABASE_URL` | 是 | MariaDB/MySQL 连接串，如 `mysql+pymysql://user:pass@host:3306/dbname` |
| `SANDBOX_MODE` | 无 Docker 时为是 | 设为 `local`，否则任务执行会依赖 Docker |
| `STATIC_DIR` | 否 | 静态资源目录，默认 `backend/static` |
| `SECRET_KEY` | 建议 | 生产环境务必修改 |

---

## 四、与 Docker 部署的差异

| 项目 | Docker 部署 | 集成到客户端（本方案） |
|------|-------------|---------------------------|
| 数据库 | MariaDB 容器 | 客户机 MariaDB/MySQL（自装或既有） |
| 前端 | 独立容器或单独起 Node | 后端挂载 `static/`，同进程提供 |
| 任务沙箱 | Docker 容器 | 本地子进程（`SANDBOX_MODE=local`） |

---

## 五、安全说明

- **本地沙箱**：适合**可信环境**（如内网、仅可信用户提交任务）。本地子进程无隔离，若需强隔离，需客户环境提供 Docker 或其它隔离方案。
- **生产环境**：务必设置 `SECRET_KEY`，并视需求收紧 CORS、HTTPS 等。

按上述步骤即可在不依赖客户机 Docker/Node 的前提下，将本平台集成进自有客户端；数据库统一使用 MariaDB/MySQL。
