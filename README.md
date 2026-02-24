# Trusted Compute Sandbox

沙箱计算服务：**实例隔离**（推荐）— 每个沙箱对应独立 MariaDB 容器与数据卷，销毁时删除容器与卷；在沙箱内执行 SQL 与 Python。

---

## 1. 服务组成

使用 **Podman**（及 podman compose）运行；**本项目采用 Podman**，内网/不能联网的机器上不安装 Docker。

| 服务 | 说明 | 端口 |
|------|------|------|
| **backend** | FastAPI：提供 REST API；创建/销毁沙箱（独立 DB 容器+卷）、在沙箱内执行 SQL/Python。 | 8000 |
| **sandbox** | 仅用于**构建镜像**，非长驻服务。执行 SQL 时由 backend 启动临时 runner 容器，连到该沙箱的 DB 容器。 | - |

- 无独立前端，通过**调用 API** 或运行 **examples** 中的脚本使用。
- 技术栈：Python FastAPI、Podman 沙箱（每次请求起一个容器）。

---

## 2. 如何启动

在**项目根目录**（包含 `docker-compose.yml` 和 `scripts` 的目录）执行。

### 方式一：脚本启动（推荐，采用 Podman）

脚本优先使用项目下 `runtime/podman` 或系统 PATH 中的 Podman。Windows 下会检查 WSL 与 Podman Machine。

- **Windows (cmd)**：`scripts\start-for-client.cmd`
- **PowerShell**：`scripts\start-for-client.ps1`
- **Linux / macOS**：`scripts/start-for-client.sh`

首次运行如缺少镜像会拉取；本地已有镜像则直接使用。**内网部署、构建阶段也不能联网**时，请先按 [内网部署说明](docs/OFFLINE_DEPLOY.md) 在联网环境导出镜像，再将项目拷贝到内网，用同一套启动脚本即可（会自动 load 并 `--no-build`）。

### 方式二：直接使用 Podman Compose

在项目根目录执行：

```bash
podman compose up -d --build
# 或：podman-compose up -d --build
```

### 启动后

- 后端 API：<http://localhost:8000>
- 交互式文档：<http://localhost:8000/docs>

---

## 3. 如何停止

在项目根目录执行与启动方式对应的停止命令。

### 使用脚本启动的 → 用脚本停止

- **Windows (cmd)**：`scripts\stop-for-client.cmd`
- **PowerShell**：`scripts\stop-for-client.ps1`
- **Linux / macOS**：`scripts/stop-for-client.sh`

### 使用 Compose 启动的 → 手动 down

```bash
docker compose down
# 或：docker-compose down
```

---

## 4. 如何使用

### 4.1 API 说明

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 健康检查，返回 API 名称与版本。 |
| POST | `/api/sandboxes` | 创建沙箱：启动独立 MariaDB 容器并绑定数据卷，返回 `sandbox_id`。 |
| DELETE | `/api/sandboxes/{sandbox_id}` | 销毁沙箱：停止并删除 DB 容器与关联数据卷。 |
| POST | `/api/execute-sql` | 在指定沙箱的 MariaDB 中执行 SQL（需传 `sandbox_id`）。支持单表或多表，见 [docs/SQL_USAGE.md](docs/SQL_USAGE.md)。 |
| POST | `/api/execute-python` | 在沙箱内执行 Python 代码（pandas/numpy），代码末尾需设置 `result` 变量，结果直接返回。 |

交互式文档：浏览器打开 <http://localhost:8000/docs>。

### 4.2 运行示例（演示）

- 先启动服务（见第 2 节），在项目根目录执行：  
  `python examples/demo.py`  
  （或 `python examples/run_sql_examples.py`，逻辑相同。）  
  演示脚本会读取 **examples/data/dbprofile.sql**（建表 DDL）、**users.csv / orders.csv**（数据）、**query.sql**（要执行的 SQL），调用 `POST /api/execute-sql` 并打印结果。  
  可选：先运行 `python examples/wait_for_api.py` 等待 API 就绪。  
- **依赖安装**（运行前需执行一次）：
  - 有网：`pip install -r examples/requirements.txt`（或 `python -m pip install -r examples/requirements.txt`）
  - 使用项目内离线包（无 PyPI 或已拷贝 `examples/offline_wheels/`）：  
    `pip install --no-index --find-links=examples/offline_wheels -r examples/requirements.txt`  
    （或 `python -m pip install --no-index --find-links=examples/offline_wheels -r examples/requirements.txt`）

### 4.3 内网部署（构建也不联网）

在联网环境执行一次 `scripts\export-images-for-offline.cmd`（Windows，推荐）或 `scripts/export-images-for-offline.sh`（Linux/macOS）：会构建并导出 `runtime/images/*.tar`（含 **mariadb.tar**，沙箱 DB 用）、并**顺带打包** examples 的 Python 依赖到 `examples/offline_wheels/`（需本机已安装 Python/pip）；将整份项目（含上述内容）拷贝到内网后，用相同启动脚本即可**预加载所有镜像（含 MariaDB）**并启动，无需再构建或拉取，首次创建沙箱也无需联网。若导出时未装 Python、未生成 `offline_wheels`，可稍后在同一联网机运行 `scripts\download-examples-wheels.cmd`（Windows）或 `scripts/download-examples-wheels.sh` 补打；内网安装示例依赖：`pip install --no-index --find-links=examples/offline_wheels -r examples/requirements.txt`。详见 [docs/OFFLINE_DEPLOY.md](docs/OFFLINE_DEPLOY.md) 与 [runtime/images/README.md](runtime/images/README.md)。

### 4.4 环境变量（可选）

- `TRUSTED_COMPUTE_API`：API 根地址，默认 `http://localhost:8000`。示例脚本会读取该变量。
- `BUNDLED_RUNTIME_ROOT`：覆盖运行时根目录（默认使用项目下 `runtime/`）。详见 [ENV_VARS_WINDOWS.md](ENV_VARS_WINDOWS.md)。
- `USE_OFFICIAL_HUB=1`：从 Docker Hub 拉取基础镜像（默认可能使用国内镜像）。仅联网构建时有效。
- **实例隔离**：`MARIADB_ROOT_PASSWORD`（沙箱 DB 的 root 密码）、`MARIADB_IMAGE`（MariaDB 镜像）、`SANDBOX_NETWORK`（沙箱 DB 容器加入的网络）。
- Windows 下使用 Podman 若出现 WSL 相关提示，可参考 [WSL_SETUP_WINDOWS.md](WSL_SETUP_WINDOWS.md)。

---

## 5. 其他说明与文档

- **[docs/OFFLINE_DEPLOY.md](docs/OFFLINE_DEPLOY.md)**：内网部署、构建阶段也不联网时的完整流程。

- **沙箱执行方式**：每次请求都会启动一个临时容器（`podman run --rm -i`），将 JSON 从 stdin 传入容器内的 `runner.py`，从 stdout 读取结果。需在运行 backend 的环境中安装 Podman 并成功构建沙箱镜像 `trusted-compute-sandbox`。
- **性能**：每次执行都会冷启动一个容器，单次约 2–10 秒量级；沙箱镜像为多阶段构建以控制体积。
- 本仓库为简化实现，便于理解多方安全计算与沙箱隔离；生产环境可考虑 FATE、SecretFlow 等方案。
