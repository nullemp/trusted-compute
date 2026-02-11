# Trusted Compute Sandbox

沙箱计算服务：在**隔离容器**内执行 SQL（SQLite）与 Python，结果直接返回，不落盘、无持久化数据库。

---

## 1. 服务组成

使用 **Podman**（及 podman compose）运行；**本项目采用 Podman**，内网/不能联网的机器上不安装 Docker。

| 服务 | 说明 | 端口 |
|------|------|------|
| **backend** | FastAPI：提供 REST API，接收请求后通过 `podman run --rm -i` 启动沙箱容器执行 SQL/Python，返回结果。 | 8000 |
| **sandbox** | 仅用于**构建镜像**，非长驻服务。每次执行时由 backend 启动临时容器，执行完即删除。 | - |

- 无独立前端，通过**调用 API** 或运行 **examples / client-simulator** 使用。
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
| POST | `/api/execute-sql` | 在沙箱内用 SQLite 执行 SQL，结果直接返回。支持单表或多表，见 [docs/SQL_USAGE.md](docs/SQL_USAGE.md)。 |
| POST | `/api/execute-python` | 在沙箱内执行 Python 代码（可用的 pandas/numpy），代码末尾需设置 `result` 变量，结果直接返回。 |

交互式文档：浏览器打开 <http://localhost:8000/docs>。

### 4.2 运行示例

**快速验证（推荐）**

- **Windows**：在项目根目录执行  
  `examples\test_sql.cmd`  
  （内部用 PowerShell 调 `test_sql.ps1`，会先 GET `/` 再 POST `/api/execute-sql`，并打印结果。）
- **PowerShell**：`.\examples\test_sql.ps1`
- **Python**：`python examples/test_sql.py`

**多表 + 多条 SQL 示例**

- 先启动服务（见第 2 节），再执行：  
  `python examples/run_sql_examples.py`  
  脚本会读取 `client-simulator/data/` 下 CSV，构造多表请求调用 `POST /api/execute-sql`。

**client-simulator 一键示例**

- 进入 `client-simulator`，执行对应脚本，会先等待 API 就绪，再运行 `examples/run_sql_examples.py`：
  - Windows：`client-simulator\run_tests.cmd` 或 `client-simulator\run_tests.ps1`
  - Linux/macOS：`cd client-simulator && ./run_tests.sh`

依赖：`pip install -r client-simulator/requirements.txt`（主要含 `requests`）。

### 4.3 内网部署（构建也不联网）

在联网环境执行一次 `scripts/export-images-for-offline.ps1`（或 `.sh`），将生成的 `runtime/images/*.tar` 随项目拷贝到内网；内网运行相同启动脚本即可，无需再构建或拉取。backend/sandbox 的 requirements 已打进镜像；若内网还要跑 Python 示例脚本且无 PyPI，需在联网机用 `pip download -r client-simulator/requirements.txt -d client-simulator/offline_wheels` 下载 wheel 后一并拷贝，内网用 `pip install --no-index --find-links=client-simulator/offline_wheels -r client-simulator/requirements.txt` 安装。详见 [docs/OFFLINE_DEPLOY.md](docs/OFFLINE_DEPLOY.md) 与 [runtime/images/README.md](runtime/images/README.md)。

### 4.4 环境变量（可选）

- `TRUSTED_COMPUTE_API`：API 根地址，默认 `http://localhost:8000`。示例脚本会读取该变量。
- `BUNDLED_RUNTIME_ROOT`：覆盖运行时根目录（默认使用项目下 `runtime/`）。详见 [ENV_VARS_WINDOWS.md](ENV_VARS_WINDOWS.md)。
- `USE_OFFICIAL_HUB=1`：从 Docker Hub 拉取基础镜像（默认可能使用国内镜像）。仅联网构建时有效。
- Windows 下使用 Podman 若出现 WSL 相关提示，可参考 [WSL_SETUP_WINDOWS.md](WSL_SETUP_WINDOWS.md)。

---

## 5. 其他说明与文档

- **[docs/OFFLINE_DEPLOY.md](docs/OFFLINE_DEPLOY.md)**：内网部署、构建阶段也不联网时的完整流程。

- **沙箱执行方式**：每次请求都会启动一个临时容器（`podman run --rm -i`），将 JSON 从 stdin 传入容器内的 `runner.py`，从 stdout 读取结果。需在运行 backend 的环境中安装 Podman 并成功构建沙箱镜像 `trusted-compute-sandbox`。
- **性能**：每次执行都会冷启动一个容器，单次约 2–10 秒量级；沙箱镜像为多阶段构建以控制体积。
- 本仓库为简化实现，便于理解多方安全计算与沙箱隔离；生产环境可考虑 FATE、SecretFlow 等方案。
