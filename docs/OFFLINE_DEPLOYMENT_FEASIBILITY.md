# 离线部署可行性分析

**目标**：判断本项目是否可以在完全无外网环境下部署和运行。
**依据**：当前项目目录、Dockerfile、compose、依赖文件及脚本。

---

## 1. 当前是否支持离线部署

**结论：部分支持（在满足前提条件下可实现完全离线运行）**

| 判断                       | 依据                                                                                                                                                                                                                                                                                                                                     |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **部分支持**         | 文档与脚本已支持「联网机导出 → 内网加载启动」流程；内网侧若**不执行任何 build** 且仅使用已加载的镜像，可做到零外网访问。                                                                                                                                                                                                          |
| **脚本与文档不一致** | `docs/OFFLINE_DEPLOY.md`、`runtime/images/README.md` 写明内网「不再执行 build、不访问网络」；但 `scripts/start-for-client.ps1` / `scripts/start-for-client.sh` 在检测到 `runtime/images/*.tar` 后会**先执行一次** `compose build sandbox`（为保证 runner 代码最新），该步骤在完全离线下会失败（需拉取基础镜像、pip）。 |
| **实际可完全离线**   | 启动脚本在 sandbox 重建失败时**不退出**（Linux 下忽略该失败继续执行，Windows 仅打印 WARNING），仍会执行 compose up -d --no-build，使用已加载的 backend、sandbox、mariadb 镜像，故无外网时仍能正常启动并运行。                                                                                                                      |

**判断依据（具体路径）**：

- `scripts/start-for-client.ps1` 第 139–161 行：`$usedOfflineImages` 为真时先 `podman compose build sandbox`，失败仅告警后继续 `podman compose up -d --no-build`。
- `scripts/start-for-client.sh` 第 52–58 行：存在 tar 时 `podman compose build sandbox ... || true`，然后 `COMPOSE_UP_ARGS="up -d --no-build"`。
- `docs/OFFLINE_DEPLOY.md` 第 43 行：「执行 `compose up -d --no-build`，**不再执行 build，不访问网络**」——与脚本实际「先 build sandbox 再 up」不一致。

---

## 2. 项目中涉及外网依赖的部分

### 2.1 Docker 镜像是否需要在线拉取

| 场景                 | 是否需在线     | 依据                                                                                                                                                                                                                        |
| -------------------- | -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **联网机导出** | 是             | `scripts/export-images-for-offline.ps1` 第 54–55、78–79 行：`compose build` 会拉取 `PYTHON_IMAGE`（默认 `python:3.11-slim`）；第 99–100 行：`$runtime pull $MariadbPull` 拉取 MariaDB。                        |
| **内网运行**   | 否（若按流程） | 使用 `runtime/images/*.tar` 通过 `podman/docker load` 加载后，backend 启动沙箱 DB 时使用环境变量 `MARIADB_IMAGE`（`docker-compose.yml` 第 31 行、`sandbox_db_lifecycle.py` 第 85 行），镜像已本地存在则无需拉取。 |

**相关文件**：

- `docker-compose.yml` 第 11、21 行：`PYTHON_IMAGE: ${PYTHON_IMAGE:-python:3.11-slim}`。
- `scripts/export-images-for-offline.sh` 第 58–62 行：拉取并 save MariaDB 为 `mariadb.tar`。

### 2.2 是否依赖外部 API

**否。**

- `backend/main.py`：仅 FastAPI 路由、本地调用 `sandbox_service` 与 `sandbox_db_lifecycle`，无 `requests.get/post` 或其它外网 HTTP 调用。
- 运行时仅依赖本机 Podman/Docker socket（`docker-compose.yml` 第 33 行 `volumes: - /var/run/docker.sock`）、本地子进程启动容器，无第三方 API。

### 2.3 是否使用在线包管理（pip / npm / apt 等）

| 位置                                 | 阶段                 | 是否在线 | 依据                                                                                                                                                                                                                                                            |
| ------------------------------------ | -------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **backend/Dockerfile**         | 构建镜像（仅联网机） | 是       | 第 13–14 行：`apt-get update && apt-get install`；第 25 行：`pip install -r requirements.txt`。                                                                                                                                                            |
| **backend/sandbox/Dockerfile** | 构建镜像（仅联网机） | 是       | 第 6 行：`RUN pip install --no-cache-dir --target /install pandas numpy pymysql`。                                                                                                                                                                            |
| **examples**                   | 本机跑示例脚本       | 可选     | `examples/requirements.txt`（requests）；联网机可执行 `scripts/download-examples-wheels.ps1`（第 45 行 `pip download`）生成 `examples/offline_wheels/`，内网用 `pip install --no-index --find-links=...`（见 `run_sql_examples.py` 第 23 行提示）。 |

### 2.4 是否需要在线 license 验证

**否。** 代码与配置中未发现任何 license 或激活接口。

### 2.5 是否使用云服务（S3 / OSS / RDS 等）

**否。** 无对象存储、无托管数据库；沙箱 DB 为本地容器内 MariaDB（`sandbox_db_lifecycle.py` 启动独立容器 + 卷）。

### 2.6 是否存在在线更新机制

**否。** 无自动更新、无版本检查接口；仅通过重新导出镜像 tar 与项目拷贝做版本更新。

---

## 3. 依赖分析

### 3.1 运行时依赖

| 依赖                               | 说明                                                           | 离线来源                                                                                                                                      |
| ---------------------------------- | -------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| Podman 或 Docker                   | 宿主机容器运行时，backend 通过 socket 调起容器                 | 需内网预装或放入 `runtime/podman` / `runtime/docker`（脚本会优先使用 `BUNDLED_RUNTIME_ROOT`，见 `start-for-client.ps1` 第 64–65 行） |
| docker-compose（与 Podman 配合时） | 用于 `podman compose` 的 compose 实现                        | 需预置在 `runtime/docker/docker-compose.exe`（脚本第 31–32、97–98 行），**不会自动下载**（第 39–40 行提示）                        |
| 三个镜像                           | trusted-compute-backend、trusted-compute-sandbox、mariadb:11.2 | 由 `runtime/images/*.tar` load 得到                                                                                                         |

### 3.2 构建时依赖（仅联网导出阶段）

| 依赖              | 位置                                                                      | 说明                                                                                                                           |
| ----------------- | ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| 基础镜像          | `backend/Dockerfile` 第 3 行、`backend/sandbox/Dockerfile` 第 4、9 行 | `ARG PYTHON_IMAGE=python:3.11-slim`，可从 `PYTHON_IMAGE` 指定国内镜像（如 `docker.m.daocloud.io/...`）                   |
| apt + curl        | `backend/Dockerfile` 第 13–22 行                                       | 安装 curl 并从 `https://download.docker.com/linux/static/stable/...` 下载 Docker CLI；使用 Debian 源（脚本可改为阿里云镜像） |
| pip 包（backend） | `backend/requirements.txt` + Dockerfile 第 25 行                        | fastapi、uvicorn、pydantic、python-multipart、pymysql                                                                          |
| pip 包（sandbox） | `backend/sandbox/Dockerfile` 第 6 行                                    | pandas、numpy、pymysql                                                                                                         |
| MariaDB 镜像      | 导出脚本                                                                  | 默认拉取 `docker.io/library/mariadb:11.2` 或 `MARIADB_IMAGE` / 国内镜像并 save 为 `mariadb.tar`                          |

### 3.3 必须提前下载的内容

- **镜像 tar**：`trusted-compute-backend.tar`、`trusted-compute-sandbox.tar`、`mariadb.tar`（由 `scripts/export-images-for-offline.*` 在联网机生成）。
- **可选**：`examples/offline_wheels/`（`scripts/download-examples-wheels.*`），供内网本机运行示例时 `pip install --no-index --find-links=...`。

### 3.4 可本地打包的内容

- 上述三个镜像 tar 已包含 backend/sandbox 内全部 pip 依赖，无需在内网再装。
- 若内网需跑 `run_sql_examples.py` 等，可将 `examples/offline_wheels/` 与项目一起拷贝，实现本地打包安装。

---

## 4. 数据库与中间件

| 项目                         | 结论 | 依据                                                                                                                                             |
| ---------------------------- | ---- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| **是否依赖外部数据库** | 否   | 无 RDS/云数据库；每个沙箱由 `sandbox_db_lifecycle.create_sandbox()` 在本机启动独立 MariaDB 容器（`sandbox_db_lifecycle.py` 第 92–102 行）。 |
| **是否可本地化部署**   | 是   | MariaDB 以容器形式按沙箱起停，镜像来自 `MARIADB_IMAGE`，内网使用已 load 的 `mariadb.tar` 即可。                                              |
| **是否需要初始化数据** | 否   | 沙箱 DB 为空库；每笔 execute-sql 在临时 database 内执行后 DROP（见文档与 runner 逻辑），无统一初始化脚本依赖。                                   |
| **数据卷是否可迁移**   | 是   | 卷名为 `tc-sandbox-data-<sandbox_id>`（第 31 行），为 Podman/Docker 命名卷，可按运行时文档做备份/迁移。                                        |

---

## 5. 容器化情况

### 5.1 Dockerfile 是否包含在线 apt / yum 安装

| 文件                                 | 是否在线     | 依据                                                                                                                                                                                                                            |
| ------------------------------------ | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **backend/Dockerfile**         | 是           | 第 8–10 行：改写 Debian 源为 mirrors.aliyun.com（可离线前在镜像中固化）；第 13–14 行：`apt-get update && apt-get install`；第 19 行：`curl -fsSL "https://download.docker.com/linux/static/stable/..."` 下载 Docker CLI。 |
| **backend/sandbox/Dockerfile** | 否（无 apt） | 仅多阶段 `FROM` + `pip install`，无 apt/yum。                                                                                                                                                                               |

### 5.2 镜像是否可提前打包成 tar

**可以。**

- `scripts/export-images-for-offline.ps1` 第 87–91、96–106 行：`$runtime save -o ...` 生成 `trusted-compute-backend.tar`、`trusted-compute-sandbox.tar`、`mariadb.tar`。
- 内网通过 `podman/docker load -i runtime/images/*.tar` 加载（`start-for-client.ps1` 第 54–56 行）。

### 5.3 Build 阶段在线依赖

- **backend 镜像 build**：需拉取 `PYTHON_IMAGE`、apt 源、download.docker.com、pip 安装 backend/requirements.txt。
- **sandbox 镜像 build**：需拉取 `PYTHON_IMAGE`、pip 安装 pandas/numpy/pymysql。
- 以上仅在**联网机**执行一次；导出 tar 后内网不再执行这些 build。

---

## 6. 若当前不能完全离线部署：缺失项与改造点

当前在「按文档手动 load + up --no-build、且不执行 build」或「使用现有启动脚本并接受 sandbox 重建失败」两种方式下，**均可实现完全离线运行**。若希望内网**完全不发起任何网络请求**且与文档一致，可做如下改造。

### 6.1 缺失项列表

| 缺失项                       | 说明                                                                                                |
| ---------------------------- | --------------------------------------------------------------------------------------------------- |
| 启动脚本会主动 build sandbox | 存在 tar 时仍执行 `compose build sandbox`，会尝试拉取基础镜像和 pip，在纯离线环境产生失败或超时。 |
| 文档与脚本不一致             | 文档称「不再执行 build」，脚本实际会先 build sandbox。                                              |
| docker-compose 未随包提供    | Windows 下若未预置 `runtime/docker/docker-compose.exe`，脚本不会自动下载（仅提示）。              |

### 6.2 需要补充的改造点

| 改造点                                       | 优先级  | 说明                                                                                                                                                                                                   |
| -------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| ~~增加「严格离线」选项，跳过 sandbox 重建~~ | ~~高~~ | **已实现**：设置环境变量 `SKIP_SANDBOX_REBUILD=1`（或 `true`）后，检测到 tar 时仅 load + `compose up -d --no-build`，不执行 `compose build sandbox`。内网不需要重建 sandbox 时使用即可。 |
| 文档与脚本对齐                               | 中      | 已在 OFFLINE_DEPLOY.md、runtime/images/README.md 中写明：默认会尝试重建 sandbox；内网不重建时设置 `SKIP_SANDBOX_REBUILD=1`。                                                                         |
| 可选：导出时包含 python 基础镜像             | 低      | 若希望内网也能成功执行 `compose build sandbox`（例如代码变更后在内网重打 sandbox），可增加导出 `python:3.11-slim` 的 tar，并在 build 时使用已 load 的该镜像。                                      |

### 6.3 改造优先级与复杂度

- **高**：增加严格离线开关（脚本几行判断 + 不执行 build sandbox）——**低复杂度**。
- **中**：文档同步——**低复杂度**。
- **低**：基础镜像 + 离线 pip 支持以便内网 build sandbox——**中复杂度**（需多导出一个 tar、可能需 sandbox 构建阶段使用 `--no-index` + 本地 wheel）。

---

## 7. 完整离线部署改造方案

### 7.1 镜像预打包策略

- **维持现状**：在联网机执行 `scripts/export-images-for-offline.ps1` 或 `export-images-for-offline.sh`，生成：
  - `runtime/images/trusted-compute-backend.tar`
  - `runtime/images/trusted-compute-sandbox.tar`
  - `runtime/images/mariadb.tar`
- **可选**：若需内网能重打 sandbox，再导出 `python:3.11-slim`（或 `PYTHON_IMAGE` 对应镜像）为 `runtime/images/python-base.tar`，并在内网先 load 该镜像；同时为 sandbox 提供离线 wheel 目录并在 Dockerfile 中使用 `pip install --no-index --find-links=...`（需改 Dockerfile 与导出脚本）。

### 7.2 依赖缓存策略

- **容器内依赖**：已包含在 backend/sandbox 的镜像 tar 中，无需额外缓存。
- **本机示例依赖**：联网机执行 `scripts/download-examples-wheels.*`，将 `examples/offline_wheels/` 随项目拷贝，内网使用：
  `pip install --no-index --find-links=examples/offline_wheels -r examples/requirements.txt`

### 7.3 本地镜像仓库是否需要

**不需要。** 当前设计为 load 本地 tar 后直接使用本地镜像名（trusted-compute-backend、trusted-compute-sandbox、docker.io/library/mariadb:11.2），无需私有 registry。

### 7.4 安装包准备清单

| 内容                          | 来源                            | 放置位置                                             |
| ----------------------------- | ------------------------------- | ---------------------------------------------------- |
| 三个镜像 tar                  | 联网机 export 脚本              | `runtime/images/`                                  |
| examples 离线 wheel（可选）   | 联网机 download-examples-wheels | `examples/offline_wheels/`                         |
| Podman 或 Docker              | 内网预装或自带                  | 系统 PATH 或 `runtime/podman` / `runtime/docker` |
| docker-compose（Podman 场景） | 预下载                          | `runtime/docker/docker-compose.exe`（Windows）     |

### 7.5 推荐部署流程

1. **联网机（一次性）**

   - 执行 `scripts/export-images-for-offline.ps1`（或 .sh）。
   - 可选：执行 `scripts/download-examples-wheels.ps1`（或 .sh）。
   - 将整个项目目录（含 `runtime/images/*.tar`、若有则含 `examples/offline_wheels/`）打包。
2. **内网机**

   - 安装 Podman（或使用项目自带 `runtime/podman`）；若用 Podman 且无内置 compose，将 `docker-compose.exe` 放入 `runtime/docker/`。
   - 解压项目后，在项目根目录执行 `scripts/start-for-client.ps1`（或 .sh）。
   - 脚本会 load `runtime/images/*.tar`，然后尝试 build sandbox（纯离线会失败，可忽略），再执行 `compose up -d --no-build`，服务可用。
3. **严格离线（零网络尝试）**

   - 若已改造支持「严格离线」开关：设置该变量后执行上述启动脚本。
   - 或手动执行：
     `podman load -i runtime/images/trusted-compute-backend.tar`（及 sandbox、mariadb），
     然后 `podman compose up -d --no-build`（不执行任何 build）。

---

## 8. 最终结论

| 项目                               | 结论                                                                                                                                                                                                                                           |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **是否可以实现完全离线部署** | **可以。** 在联网机导出三份镜像 tar（及可选 examples/offline_wheels）并拷贝至内网后，内网仅需 Podman（或 Docker）与可选 docker-compose，执行现有启动脚本即可运行；若环境完全无外网，sandbox 重建会失败但不影响使用已加载镜像启动。       |
| **预计改造成本**             | **低。** 若仅需「完全离线且不发起任何网络请求」，增加跳过 sandbox 重建的开关并同步文档即可；若还需内网可重打 sandbox，则需额外导出基础镜像与离线 pip 方案，成本为**中**。                                                          |
| **风险点**                   | ① 内网未预装或未捆绑 Podman/Docker，或未预置 docker-compose，会导致启动失败；② 文档与脚本关于「是否执行 build」的描述不一致，可能误导运维；③ 若内网需运行示例脚本且未准备 `examples/offline_wheels/`，需在内网有 pip 源或提前打包 wheel。 |

---

*以上分析基于当前仓库的 Dockerfile、docker-compose.yml、requirements.txt、scripts 及 docs，并以具体文件路径为据。*
