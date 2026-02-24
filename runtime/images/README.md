# 离线镜像（内网部署）

本目录用于存放 **预构建好的镜像 tar**，以便在**内网、构建阶段也不能联网**的环境中直接加载并启动，无需执行任何 build / pip / 拉取镜像。

**本项目采用 Podman**：内网机器**不安装 Docker**，仅使用 Podman。联网机构建导出时可用 Podman 或 Docker。

## 思路

- **联网环境**：执行导出脚本（见下），将 `trusted-compute-backend`、`trusted-compute-sandbox` 以及 **MariaDB** 镜像导出为 tar，放入本目录。
- **内网环境**：将整个项目（含 `runtime/images/*.tar`）拷贝过去，启动脚本会**先加载本目录下所有 .tar**（含 MariaDB），再 `compose up -d --no-build`，首次创建沙箱时无需再拉取 MariaDB。

## 一、联网环境：构建并导出（仅需执行一次）

在能访问外网、且已安装 Podman 或 Docker 的机器上，于**项目根目录**执行：

### 方式 A：使用导出脚本（推荐）

- **Windows**：`scripts\export-images-for-offline.cmd`（推荐）或 `.\scripts\export-images-for-offline.ps1`
- **Linux / macOS**：`./scripts/export-images-for-offline.sh`

脚本会执行 `compose build`，将 `trusted-compute-backend`、`trusted-compute-sandbox` 保存到 `runtime/images/`；并**拉取并保存 MariaDB 镜像**为 `mariadb.tar`（沙箱 DB 容器用，启动时预加载）；若本机已安装 Python/pip，会顺带将 examples 的 Python 依赖打包到 `examples/offline_wheels/`。

### 方式 B：手动命令

使用 Podman 时（推荐，与内网一致）：

```bash
podman compose build
mkdir -p runtime/images
podman save -o runtime/images/trusted-compute-backend.tar trusted-compute-backend
podman save -o runtime/images/trusted-compute-sandbox.tar trusted-compute-sandbox
# MariaDB（与 backend 使用的 MARIADB_IMAGE 一致，默认 docker.io/library/mariadb:11.2）
podman pull docker.io/library/mariadb:11.2
podman save -o runtime/images/mariadb.tar docker.io/library/mariadb:11.2
```

使用 Docker 时：将上述 `podman` 换为 `docker`，`podman compose` 换为 `docker-compose` 或 `docker compose`。

导出完成后，将**整个项目目录**（含 `runtime/images/*.tar`，若有 `examples/offline_wheels/` 也一并拷贝）打包到内网。

## 二、内网环境：加载并启动（不联网）

在目标内网机器上**仅安装 Podman**（不装 Docker），且项目已拷贝到位后：

### 方式 A：使用现有启动脚本（推荐）

直接运行与平时相同的启动脚本：

- **Windows**：`scripts\start-for-client.cmd` 或 `scripts\start-for-client.ps1`
- **Linux / macOS**：`scripts/start-for-client.sh`

脚本会检测到 `runtime/images/` 下存在 `.tar` 文件，**先按顺序 load 所有 .tar（含 MariaDB）**。默认会尝试重建 sandbox 镜像；若**内网不需要重建 sandbox**，请设置 **`SKIP_SANDBOX_REBUILD=1`** 后再运行启动脚本，则仅执行 `compose up -d --no-build`，**不会发起任何构建或拉取**。MariaDB 在启动时即加载，首次创建沙箱时无需联网。

### 方式 B：手动命令（内网统一用 Podman）

```bash
cd /path/to/trusted-compute

# 加载镜像（含 MariaDB，供沙箱 DB 容器使用）
podman load -i runtime/images/trusted-compute-backend.tar
podman load -i runtime/images/trusted-compute-sandbox.tar
podman load -i runtime/images/mariadb.tar

# 仅启动，不构建
podman compose up -d --no-build
# 或：podman-compose up -d --no-build
```

## 三、镜像与文件对应关系

| 镜像名 | 导出文件名（脚本默认） | 说明 |
|--------|------------------------|------|
| trusted-compute-backend | trusted-compute-backend.tar | 后端 API |
| trusted-compute-sandbox | trusted-compute-sandbox.tar | SQL/Python 执行沙箱 |
| docker.io/library/mariadb:11.2（或 MARIADB_IMAGE） | mariadb.tar | 沙箱独立 DB 容器；启动时预加载，首次创建沙箱无需拉取 |

启动脚本会加载 `runtime/images/` 下**所有 `.tar`**（含 mariadb.tar），再根据是否存在项目镜像决定是否使用 `--no-build`。

## 四、版本变更时

若修改了 Dockerfile、requirements、或 compose 中的镜像名，需在**联网环境**重新执行“一、构建并导出”，并更新内网环境中的 tar 文件后，再在内网重新 load 并 `up -d --no-build`。
