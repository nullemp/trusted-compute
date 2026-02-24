# 内网部署（构建阶段也不联网）

在内网环境中无法访问外网、且**构建阶段也不能联网**时，采用「联网机一次性构建并导出 → 内网仅加载并启动」的方式，内网侧不执行任何 build、不拉取镜像、不访问 PyPI。

**本项目采用 Podman**：不能联网的内网机器上**不安装 Docker**，仅安装并使用 Podman。联网机构建导出时可用 Podman 或 Docker；内网加载与启动统一使用 Podman。

## 流程概览

| 阶段 | 环境 | 操作 |
|------|------|------|
| 1. 构建并导出 | **联网**（Podman 或 Docker；建议本机有 Python） | 执行 `scripts/export-images-for-offline.*`：构建并导出镜像到 `runtime/images/*.tar`，并**顺带打包** examples 的 Python 依赖到 `examples/offline_wheels/`（需本机已安装 Python/pip） |
| 2. 拷贝 | - | 将**整个项目目录**（含 `runtime/images/*.tar`，若有 `examples/offline_wheels/` 也一并拷贝）打包到内网 |
| 3. 加载并启动 | **内网**（仅 Podman，不装 Docker） | 运行 `scripts/start-for-client.*`；脚本会检测 tar、用 Podman load，再 `podman compose up -d --no-build`，不发起任何网络请求 |

## 联网环境：构建并导出

在能上网的机器上（已安装 Podman 或 Docker），于项目根目录执行：

- **Windows**：`scripts\export-images-for-offline.cmd`（推荐，避免执行策略限制）或 `.\scripts\export-images-for-offline.ps1`
- **Linux / macOS**：`chmod +x scripts/export-images-for-offline.sh && ./scripts/export-images-for-offline.sh`

脚本会（使用检测到的 Podman 或 Docker）：

1. 执行 `compose build`（会拉取基础镜像、执行 Dockerfile，需联网）。
2. 将镜像 `trusted-compute-backend`、`trusted-compute-sandbox` 导出为：
   - `runtime/images/trusted-compute-backend.tar`
   - `runtime/images/trusted-compute-sandbox.tar`
3. **依赖打包**：若本机已安装 Python 与 pip，会顺带执行 `scripts/download-examples-wheels.*`，将 examples 所需依赖（如 requests）下载到 `examples/offline_wheels/`，拷贝项目时一并带上即可在内网离线安装（见下文「本机 Python 依赖」）。若未安装 Python，仅会提示可稍后单独运行该脚本，镜像导出仍视为成功。

详细说明与手动命令见 [runtime/images/README.md](../runtime/images/README.md)。

## 内网环境：加载并启动

1. 将项目（含 `runtime/images/*.tar`，若有 `examples/offline_wheels/` 也一并拷贝）拷贝到内网机器。
2. 内网机器**仅安装 Podman**（不安装 Docker，无需能上网）。
3. 在项目根目录执行与平时相同的启动脚本：
   - **Windows**：`scripts\start-for-client.cmd` 或 `scripts\start-for-client.ps1`
   - **Linux / macOS**：`scripts/start-for-client.sh`

脚本会：

1. 发现 `runtime/images/` 下存在 `.tar` 文件。
2. 执行 `load` 加载镜像。
3. 若未设置 `SKIP_SANDBOX_REBUILD=1`，会尝试重建 sandbox 镜像（内网无网时会失败但不影响后续）；若**内网不需要重建 sandbox**，请设置环境变量 **`SKIP_SANDBOX_REBUILD=1`**（或 `true`），则仅执行 `compose up -d --no-build`，**不发起任何 build、不访问网络**。

如需完全手动，可参考 [runtime/images/README.md](../runtime/images/README.md) 中的「内网环境：加载并启动」命令（内网统一使用 `podman`）。

## requirements.txt 与联网

项目里有两类依赖，离线部署时都要考虑到：

| 位置 | 用途 | 何时需要联网 | 内网做法 |
|------|------|--------------|----------|
| **backend/requirements.txt** | 构建 backend 镜像时在容器内 `pip install`（fastapi、uvicorn 等） | 仅在**联网机**执行 `compose build` 时 | 已打进导出的镜像 tar，内网 load 后无需再装、**不涉及** |
| **backend/sandbox**（Dockerfile 内 pip） | 构建 sandbox 镜像时在容器内装 pandas、numpy | 同上，仅在联网机构建时 | 同上，已打进镜像 |
| **examples/requirements.txt** | 在本机跑示例脚本（如 `run_sql_examples.py`）时需要 `requests` | 若在内网执行 `pip install -r examples/requirements.txt` 会访问 PyPI，**需要联网** | 见下文「本机 Python 依赖（离线装）」 |

结论：**服务端（backend + sandbox）的 requirements 已在导出镜像时装好，内网不碰、不需联网。** 只有在内网也要跑示例/客户端脚本时，才需要在内网解决本机 Python 依赖（requests）。

### 本机 Python 依赖（离线装）

若内网**无 PyPI、无内网 pip 源**，又要运行 `examples/run_sql_examples.py` 等，需在**联网机**先准备好 wheel，再随项目拷贝到内网用离线安装。

**联网机执行（一次性）：**

- **推荐**：运行 `scripts/export-images-for-offline.*` 时，若本机已安装 Python/pip，会**自动**将 examples 依赖下载到 `examples/offline_wheels/`，无需再单独操作。
- 若导出时未装 Python 或需补打依赖，可单独执行：
  - Windows：`.\scripts\download-examples-wheels.ps1`
  - Linux/macOS：`./scripts/download-examples-wheels.sh`
  - 或手动：`pip download -r examples/requirements.txt -d examples/offline_wheels`（若 `pip` 未识别可用 `python -m pip download ...`）。

将 `examples/offline_wheels/` 随项目一起拷贝到内网（或打包进离线安装包）。

**内网机执行（无网络）：**

```bash
cd /path/to/trusted-compute
pip install --no-index --find-links=examples/offline_wheels -r examples/requirements.txt
```

若内网有**内网 pip 源**，也可直接在内网执行 `pip install -r examples/requirements.txt`，无需上述 download 步骤。

若不运行 `examples/demo.py` 等依赖 requests 的示例，本机可不装 Python 依赖。

## 总结

- **内网部署、构建也不能联网**：在联网机用导出脚本生成 `runtime/images/*.tar`，拷贝整份项目到内网；内网机仅装 Podman，用原有启动脚本即可 load + 启动，无需在内网做任何构建或拉取。
- **requirements.txt**：backend/sandbox 的依赖已打进导出镜像，内网不涉及；本机跑示例脚本需要的 `examples/requirements.txt`（如 requests）在内网无 PyPI 时，需在联网机 `pip download` 出 wheel 后拷贝到内网用 `pip install --no-index --find-links=...` 安装。
