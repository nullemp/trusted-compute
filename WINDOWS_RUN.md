# 在 Windows 上运行本项目

有两种方式：**用 Docker（推荐）** 或 **不用 Docker（本机安装各组件）**。

---

## 方式一：用 Docker 在 Windows 上跑（推荐）

### 1. 安装 Docker Desktop for Windows

- 下载：https://www.docker.com/products/docker-desktop/
- 安装后重启，确保任务栏里 Docker 图标正常（WSL 2 或 Hyper-V 按提示配置）。
- 若拉取镜像慢，可在 **Docker Desktop → Settings → Docker Engine** 里加镜像加速，例如：
  ```json
  "registry-mirrors": ["https://docker.m.daocloud.io"]
  ```

### 2. 打开终端并进入项目目录

在项目根目录（含 `docker-compose.yml` 的目录）打开 **PowerShell** 或 **CMD**：

```powershell
cd D:\develop\trusted-compute\trusted-compute
```

（请把路径改成你的实际路径。）

### 3. 启动所有服务（含前端）

前端在 compose 里用了 `profile`，需要显式带上 `--profile frontend`：

```powershell
docker-compose --profile frontend up -d --build
```

**若拉取基础镜像失败（超时/EOF）**，可指定国内镜像再构建：

```powershell
$env:PYTHON_IMAGE="docker.m.daocloud.io/library/python:3.11-slim"
$env:NODE_IMAGE="docker.m.daocloud.io/library/node:18-alpine"
docker-compose --profile frontend up -d --build
```

### 4. 等待启动完成

```powershell
docker-compose logs -f
```

看到 backend、frontend 无报错即可。按 `Ctrl+C` 退出日志。

### 5. 访问

- **前端页面**：http://localhost:3000  
- **后端 API 文档**：http://localhost:8000/docs  
- **后端 API**：http://localhost:8000  

### 6. 只启动后端 + 数据库（不要前端界面时）

```powershell
docker-compose up -d --build
```

此时不会启动 frontend，只会有 mariadb、sandbox 镜像构建、backend。

### 7. 停止服务

```powershell
docker-compose --profile frontend down
```

---

## 方式二：不用 Docker，在 Windows 本机跑

适合本机不能或不想用 Docker 的情况。任务会以 **本地子进程** 执行（无容器隔离，仅适合可信环境）。

### 1. 安装依赖

| 组件       | 要求              | 说明 |
| ---------- | ----------------- | ---- |
| MariaDB    | 10.6+             | 可用 [MariaDB 官方安装包](https://mariadb.org/download/) 或 XAMPP 等。 |
| Python     | 3.11+             | 从 [python.org](https://www.python.org/downloads/) 安装，勾选 “Add to PATH”。 |
| Node.js    | 18+               | 从 [nodejs.org](https://nodejs.org/) 安装。 |

### 2. 创建数据库与用户

用 MariaDB 客户端或 HeidiSQL 等执行：

```sql
CREATE DATABASE trusted_compute_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'trusted_compute'@'%' IDENTIFIED BY 'trusted_compute_pass';
GRANT ALL ON trusted_compute_db.* TO 'trusted_compute'@'%';
FLUSH PRIVILEGES;
```

### 3. 后端（Python）

在 **PowerShell** 中：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

若执行策略限制脚本，先执行：`Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

设置环境变量并启动（在同一 PowerShell 窗口）：

```powershell
$env:DATABASE_URL="mysql+pymysql://trusted_compute:trusted_compute_pass@localhost:3306/trusted_compute_db"
$env:SANDBOX_MODE="local"
uvicorn main:app --host 0.0.0.0 --port 8000
```

保持此窗口不关。后端地址：http://localhost:8000 ，文档：http://localhost:8000/docs 。

### 4. 前端（新开一个 PowerShell）

```powershell
cd frontend
npm install
$env:REACT_APP_API_URL="http://localhost:8000"
npm start
```

浏览器会打开 http://localhost:3000 ，请求会发到本机 8000 端口的后端。

### 5. 环境变量小结（本机无 Docker）

| 变量           | 必填 | 说明 |
| -------------- | ---- | ---- |
| `DATABASE_URL` | 是   | MariaDB 连接串，如 `mysql+pymysql://trusted_compute:trusted_compute_pass@localhost:3306/trusted_compute_db` |
| `SANDBOX_MODE` | 是   | 设为 `local`，用本机子进程执行任务，不依赖 Docker |
| `REACT_APP_API_URL` | 前端 | 开发时设为 `http://localhost:8000`，保证请求到本机后端 |

---

## 常见问题（Windows）

- **端口被占用**：改 `docker-compose.yml` 里端口映射，或关闭占用 3000/8000/3306 的程序。
- **Docker 报错找不到 docker.sock**：用方式二（本机跑），并设置 `SANDBOX_MODE=local`。
- **前端连不上后端**：确认后端已启动，且前端用 `REACT_APP_API_URL=http://localhost:8000` 后重新 `npm start`。
- **pip/npm 很慢**：可配置国内 PyPI / npm 镜像源。

按上述任选一种方式即可在 Windows 上跑起来；更多细节见 [QUICK_START.md](QUICK_START.md)、[DEPLOY_WITHOUT_DOCKER.md](DEPLOY_WITHOUT_DOCKER.md)。
