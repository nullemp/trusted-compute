# 捆绑容器运行时 (Bundled container runtime)

本目录用于放置随客户端一起分发的 **Podman** 或 **Docker** 可执行文件，使 `scripts/start-for-client.*` 不依赖客户机已安装的运行时。

## 目录结构

将可执行文件放到以下路径之一即可（二选一）：

| 平台 | 使用 Podman | 使用 Docker |
|------|-------------|-------------|
| **Windows** | `runtime\podman\podman.exe` | `runtime\docker\docker.exe` |
| **Linux/macOS** | `runtime/podman/podman` | `runtime/docker/docker` |

建议同时放入同目录下的 `podman-compose` / `docker-compose`，以便脚本直接使用。

## 自动下载运行时

在项目根目录执行：

- **Windows (PowerShell)**  
  ```powershell
  .\scripts\download-runtime.ps1
  ```
  会下载 Podman 安装包并安装到本机，再将可执行文件复制到 `runtime\podman\`。

- **Linux / macOS (bash)**  
  ```bash
  ./scripts/download-runtime.sh
  ```
  会按系统安装 Podman 或提示使用包管理器，并可选复制到 `runtime/podman/`。

## 手动下载

若希望自行放置二进制：

- **Podman**  
  - Windows: [GitHub Releases](https://github.com/containers/podman/releases) 中的 `podman-installer-windows-amd64.msi` 或 `podman-remote-release-windows_amd64.zip`。  
  - Linux: 各发行版包管理器（如 `apt install podman` / `dnf install podman`），或从 [Releases](https://github.com/containers/podman/releases) 取静态包。  
  - macOS: `podman-installer-macos-*.pkg` 或 `podman-remote-release-darwin_*.zip`。
- **Docker**  
  - Windows: [Docker Desktop](https://docs.docker.com/desktop/install/windows-install/) 或 Docker Engine 安装后，将 `docker.exe` 等复制到 `runtime\docker\`。  
  - Linux/macOS: 安装 Docker 后，将 `docker` 等复制到 `runtime/docker/`。

环境变量 **`BUNDLED_RUNTIME_ROOT`** 可指定“运行时根目录”的绝对路径，不设则默认为项目根下的 `runtime`。

详见 [DOCKER_IN_CLIENT.md](../DOCKER_IN_CLIENT.md)。
