# 把 Docker 集成到客户端

让客户端安装包**自带或引导安装容器运行时**，由客户端进程**自动启动**后端与数据库容器，用户无需单独装 Docker、也不用手动执行 docker-compose。

---

## 使用 Podman 可以不依赖客户环境么？

**可以。** 只要把 **Podman 随客户端一起安装**（捆绑或静默安装），就**不要求客户环境预装**任何运行时；且 **MariaDB、Python 也都不用在客户机上装**——它们都在容器里跑。

| 在客户机上 | 用 Podman/Docker 起整套服务时 |
|------------|------------------------------|
| **不需要装** | Docker、Podman（可由安装包带）、**MariaDB**、**Python**、Node |
| **原因** | 数据库（MariaDB）、后端（Python）、沙箱都在容器里跑，由 compose 一起启动 |

也就是说：客户环境上**不用装 MariaDB，也不用装 Python**，只要能把容器跑起来（Podman 由我们装或用户已有 Docker）即可。

| 含义 | 说明 |
|------|------|
| **不依赖客户环境** | 用户无需事先安装 Docker、Podman、Node、**Python**、**MariaDB**；由**客户端安装包**在安装或首次运行时完成 Podman（及本项目）的安装与启动，MariaDB 与 Python 均在容器内运行。 |
| **需要满足的** | 客户机仍需满足 Podman 的**系统要求**（见下），以便能跑容器。 |

**Podman 系统要求（简要）**  
- **Windows**：通常需 WSL2 或 Hyper-V（Podman 会装轻量 VM）；部分版本支持纯 Windows 容器。  
- **Linux**：内核与常见发行版即可，可选 rootless 运行。  
- **macOS**：需 Podman Machine（基于虚拟机）。

**实现方式**  
- **Windows**：在客户端安装包（如 NSIS/MSI）中加入 Podman 安装程序，安装客户端时**静默执行** Podman 安装（如 `podman-installer.msi /quiet`），或首次启动时检测并静默安装。  
- **Linux**：在 .deb/.rpm 中声明对 `podman` 的依赖（用户 `apt install 你的客户端` 时会自动装 Podman），或把 Podman 二进制及依赖打进安装目录、由客户端通过固定 PATH 调用。  
- 安装/首次运行完成后，用本仓库提供的 `scripts/start-for-client.*` 或等价逻辑，设 `CONTAINER_RUNTIME=podman` 并执行 `podman-compose up -d --build`，即可做到**不依赖客户环境预装任何东西**（MariaDB、Python 均在容器内运行）。

---

## 一、两种集成思路

| 方式 | 说明 | 适用 |
|------|------|------|
| **A. 客户端捆绑 Podman** | 安装包内带 Podman，静默安装；客户端启动时用 `podman-compose` 或等价命令起 backend + MariaDB | 希望用户机**完全不装 Docker**，由客户端提供运行时 |
| **B. 客户端调用已有 Docker** | 不捆绑运行时，客户端启动时在项目目录执行 `docker-compose up -d`，要求用户已装 Docker Desktop / Docker Engine | 用户可接受预装 Docker 的场景 |

---

## 二、方案 A：客户端捆绑 Podman（推荐，无 Docker 依赖）

Podman 与 Docker 命令行兼容（`podman run` ≈ `docker run`），可无守护进程、rootless 运行，适合随客户端一起安装。此方案下 **MariaDB、Python 均在容器内运行，客户机上无需单独安装**。

### 0. 捆绑运行时目录约定（不依赖客户环境）

若希望**完全不依赖客户机已安装的 Docker/Podman**，可将运行时随客户端一起发布到项目下的 **`runtime/`** 目录，启动脚本会优先使用该目录中的二进制，再回退到 PATH。

| 平台   | 捆绑 Podman 路径              | 捆绑 Docker 路径               |
|--------|-------------------------------|--------------------------------|
| Windows | `runtime\podman\podman.exe`   | `runtime\docker\docker.exe`    |
| Linux/macOS | `runtime/podman/podman`  | `runtime/docker/docker`        |

- 将 Podman 或 Docker 的**可执行文件**（及同目录下 `podman-compose`/`docker-compose` 若需要）放入上述对应子目录即可。
- 可选环境变量 **`BUNDLED_RUNTIME_ROOT`**：指定“运行时根目录”的绝对路径，不设则默认为项目根目录下的 `runtime`。
- 脚本执行顺序：先查 `runtime/podman` 或 `runtime/docker`，若存在则用该路径并加入 PATH，再执行 compose；否则再查系统 PATH 中的 podman/docker。

这样客户端安装包只需包含：本项目资源（compose + backend + sandbox）+ 上述 `runtime/` 下的运行时，用户无需预装任何容器环境。

### 1. 安装包内包含

- **Podman 安装程序**（或便携版）：  
  - Windows: [Podman 官网](https://podman.io/) 下载安装包，或使用 `podman-4.x.msi` 静默安装。  
  - Linux: 安装包内带 `podman` 二进制或脚本 `apt/yum install podman`。
- **podman-compose**（或用 `podman play kube` 的 yaml）：  
  - 若用 compose：`pip install podman-compose` 或内嵌二进制。  
  - 或把 compose 转为 Podman 的 pod/play kube 描述，用 `podman play kube` 启动。

### 2. 客户端启动流程（示例）

1. 检查 Podman 是否在 PATH 中（或使用安装包自带的 `podman` 路径）。
2. 若未安装，执行静默安装（如 Windows: `podman-xxx.msi /quiet`）。
3. 在**本项目的资源目录**（含 `docker-compose.yml` 的目录）执行：
   ```bash
   podman-compose up -d --build
   ```
   或等价的 `podman play kube` 命令（需先把 compose 转为 kube yaml）。
4. 等待 backend 健康（如轮询 `http://localhost:8000/docs` 或健康接口）。
5. 客户端调用 `http://localhost:8000/api/run-analysis` 等 API。

### 3. 后端使用 Podman 跑沙箱

后端默认用 `docker` 调沙箱；若客户端只装了 Podman，需让后端用 Podman 执行任务：

- 在 backend 的环境变量中设置：
  ```bash
  CONTAINER_RUNTIME=podman
  ```
- 若 backend 跑在**同一台机的容器里**，该容器需能调宿主机上的 Podman（例如挂载 Podman 的 socket 或把 `podman` 二进制挂进去并调用宿主机上的 Podman）。  
- 若 backend 是**宿主机直接跑的进程**（不容器化），则本机安装 Podman 后设 `CONTAINER_RUNTIME=podman` 即可。

本项目已支持通过环境变量选择运行时：**`CONTAINER_RUNTIME=docker`（默认）或 `CONTAINER_RUNTIME=podman`**，沙箱会执行 `podman run ...` 而不是 `docker run ...`。

### 4. 镜像构建与 socket

- **构建镜像**：首次或升级时在项目目录执行 `podman-compose build`（或 `podman build` 构建 backend/sandbox 镜像），可放在客户端“首次运行”或“更新”流程里。
- **Podman socket**：若 backend 跑在容器内，需把宿主机 Podman 的 socket 挂进 backend 容器（Linux 常见路径：`/run/podman/podman.sock`），并在 compose 里为 backend 增加 volume，例如：`/run/podman/podman.sock:/run/podman/podman.sock`。Windows 下 Podman 使用 named pipe，需按 Podman 文档配置挂载。同时 backend 容器内需能执行 `podman` 命令（可挂入宿主机 podman 二进制或容器内安装 podman）。

---

## 三、方案 B：客户端调用用户本机 Docker

不捆绑运行时，假设用户已安装 Docker Desktop 或 Docker Engine。

### 1. 客户端启动流程

1. 检查本机是否有 `docker` 命令（或检测 Docker 是否在运行）。
2. 若未安装，可提示用户安装 Docker Desktop 或打开安装向导。
3. 在**本项目资源目录**执行：
   ```bash
   docker-compose up -d --build
   ```
   （不需要前端时可去掉 `--profile frontend`，仅 backend + mariadb + 构建 sandbox 镜像。）
4. 等待服务就绪后，客户端调用 `http://localhost:8000/...`。

### 2. 资源目录建议

- 将本仓库中**至少**以下内容随客户端一起发布到固定目录（如安装目录下的 `trusted-compute` 子目录）：
  - `docker-compose.yml`
  - `backend/`（含 Dockerfile、代码、requirements）
  - `backend/sandbox/`（含 Dockerfile、runner.py）
- 前端可选；若不做 Web 界面，可不带 `frontend/`，compose 不启 frontend 即可。

---

## 四、环境变量汇总（与 Docker/Podman 相关）

| 变量 | 说明 |
|------|------|
| `CONTAINER_RUNTIME` | 沙箱用哪个命令：`docker`（默认）或 `podman`。客户端捆绑 Podman 时设为 `podman`。 |
| `SANDBOX_IMAGE` | 沙箱镜像名，默认 `trusted-compute-sandbox`。用 Podman 时同样用该镜像名（需先构建）。 |
| `SANDBOX_MODE` | `docker`/`podman` 时用容器跑任务；`local` 时用本机 Python 子进程，不依赖容器。 |

---

## 五、客户端一键启动脚本

仓库中已提供脚本，客户端可将其与项目资源一起打包，启动时调用即可（在**项目根目录**执行）。脚本**优先使用项目内 `runtime/podman` 或 `runtime/docker` 中的捆绑运行时**，若无则使用 PATH 中的 Podman/Docker；不启前端：

- **Windows**：`scripts/start-for-client.ps1`（PowerShell）
- **Linux / macOS**：`scripts/start-for-client.sh`（bash，需 `chmod +x`）

使用示例（在项目根目录下）：

```powershell
# Windows
.\scripts\start-for-client.ps1
```

```bash
# Linux/macOS
./scripts/start-for-client.sh
```

脚本会先查找项目下 `runtime/podman` 或 `runtime/docker` 中的可执行文件，若有则将其加入 PATH 并使用；否则检测本机 PATH 中的 `podman` 或 `docker`。若有 Podman 则设置 `CONTAINER_RUNTIME=podman` 并执行 `podman-compose up -d --build`（若无 podman-compose 则退化为 `docker-compose`），否则执行 `docker-compose up -d --build`。

---

## 六、小结

- **把 Docker 集成到客户端** = 由客户端负责**启动**后端与数据库（用 Docker 或 Podman），并可选择**捆绑 Podman** 从而不依赖用户预装 Docker。此时 **MariaDB、Python 都在容器里跑，客户机上不用装**。
- 本项目已支持 **`CONTAINER_RUNTIME=podman`**，客户端只要在 backend 环境中设置该变量，沙箱即用 Podman 执行任务。
- 客户端安装包可包含：本项目资源（compose + backend + sandbox）、Podman 安装程序（或便携版）、以及上述“一键启动”脚本，在启动时自动执行 compose 并轮询 API 就绪后再调用接口。
- **对比**：若客户环境**不跑容器**（见 [DEPLOY_CLIENT_NO_DOCKER.md](DEPLOY_CLIENT_NO_DOCKER.md)），则需在客户机上安装 MariaDB 与 Python，并设 `SANDBOX_MODE=local`。