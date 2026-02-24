# 项目上下文总结（对话延续用）

本文档基于当前对话的完整内容整理，供新对话中继续开发时作为背景说明使用。可直接粘贴到新对话开头。

---

## 1. 项目基本信息

- **项目名称**：Trusted Compute Sandbox（可信计算沙箱）
- **技术栈**：
  - 后端：Python 3.11+、FastAPI、Uvicorn、Pydantic
  - 数据库：MariaDB（**无共享常驻实例**；每沙箱一个独立 MariaDB 容器 + 独立数据卷）
  - 沙箱执行：Podman/Docker 启动临时容器，容器内 runner.py（PyMySQL、pandas、numpy）
  - 编排：docker-compose / podman compose；推荐 Podman，内网不装 Docker
- **项目目标**：为数据流通/协作任务提供**实例隔离**的沙箱——每个沙箱对应独立 DB 容器与数据卷，支持创建沙箱、在沙箱内执行 SQL 与 Python、销毁沙箱（删除容器与卷）；支持内网/离线部署。
- **当前阶段**：核心功能已实现并跑通（创建/销毁沙箱、execute-sql、execute-python、离线镜像与启动脚本修复）；已有一份完整项目文档（docs/PROJECT_DOCUMENTATION.md）。无正式单元测试，通过示例脚本与 Swagger 做验证。

---

## 2. 当前实现情况

### 2.1 已完成的模块

- **backend/main.py**：FastAPI 应用；路由 GET /、POST /api/sandboxes、DELETE /api/sandboxes/{sandbox_id}、POST /api/execute-sql、POST /api/execute-python。
- **backend/schemas.py**：ExecuteSqlRequest（含 sandbox_id、sql、ddl、data/table_name/columns 或 tables）、ExecutePythonRequest、TableSpec。
- **backend/services/sandbox_service.py**：构造 payload，通过 subprocess 调用 podman/docker run 启动 runner 容器；execute_sql 时使用沙箱 DB 的 **IP**（优先）或主机名，通过 **payload 内 _mariadb** 传入 runner，避免依赖容器 -e 在某些环境（如 Windows Podman）下未生效或容器名解析失败。
- **backend/services/sandbox_db_lifecycle.py**：create_sandbox（创建卷、启动 MariaDB 容器、等待就绪）、destroy_sandbox（stop → rm 容器 → rm 卷）、sandbox_db_host、**sandbox_db_ip**（inspect 取容器 IP）、sandbox_exists。
- **backend/sandbox/runner.py**：stdin JSON → 根据 model_type 执行 SQL 或 Python → stdout JSON；SQL 时从 input_params["_mariadb"] 或环境变量取连接参数，每请求创建临时 database，执行后 DROP。
- **启动/停止脚本**：scripts/start-for-client.*、stop-for-client.*；Windows 下会检测 WSL、Podman Machine，加载 runtime/images/*.tar，**在离线镜像场景下仍会重建 sandbox 镜像**（保证 runner 代码最新），并为 Podman 将 runtime/docker 加入 PATH 以便 podman compose 找到 docker-compose.exe。
- **离线导出**：scripts/export-images-for-offline.* 构建 backend/sandbox 并拉取 MariaDB 镜像，导出为 runtime/images/*.tar（含 mariadb.tar）；使用国内镜像默认值避免 Docker Hub 超时；download-examples-wheels 在调用 pip 时临时取消代理避免 ProxyError。
- **示例**：examples/run_sql_examples.py 完整流程（创建沙箱 → 多次 execute-sql → finally 销毁沙箱）；execute-sql 超时 180s，destroy 60s；backend 沙箱执行超时由 SANDBOX_RUN_TIMEOUT 控制（默认 120s）。
- **文档**：README.md、docs/SQL_USAGE.md、docs/OFFLINE_DEPLOY.md、runtime/images/README.md、**docs/PROJECT_DOCUMENTATION.md**（完整开发/运维/测试文档）、WSL_SETUP_WINDOWS.md、ENV_VARS_WINDOWS.md。

### 2.2 已确认的架构设计

- **实例隔离**：无共享 MariaDB 服务；每个沙箱 = 一个 MariaDB 容器（tc-sandbox-db-&lt;id&gt;）+ 一个命名卷（tc-sandbox-data-&lt;id&gt;）；创建/销毁仅通过 API，Compose 中不定义 mariadb 服务。
- **SQL 执行**：backend 收到 execute-sql 后，先取沙箱 DB 的 **IP**（sandbox_db_ip），失败则用容器名；将连接信息放入 request body 的 **input_params["_mariadb"]**，与 sql/ddl/tables 一起通过 stdin 传给 runner；runner 连接该 IP/主机名上的 MariaDB，创建临时 database，执行 DDL/插入/用户 SQL，返回结果后 DROP DATABASE。
- **Python 执行**：无 DB；runner 使用 --network none，仅执行用户代码并返回 result。
- **网络**：所有沙箱 DB 与 runner 容器均加入同一网络（trusted-compute_default），backend 通过主机上的 podman/docker 启动这些容器（backend 容器挂载 socket）。

### 2.3 关键技术决策

- **DB 从 SQLite 改为 MariaDB**：满足“独立 DB 容器 + 数据卷、按沙箱销毁”的隔离需求。
- **连接信息经 payload 传递**：因在部分环境（如 Windows Podman）下容器 -e 未传入或容器名解析失败，改为在 input_params 中传 _mariadb（host/port/user/password），runner 优先使用该对象连接。
- **优先使用沙箱 DB 容器 IP**：避免 runner 与 DB 间 DNS/容器名解析失败（如 “Temporary failure in name resolution”），sandbox_service 中 _host = sandbox_db_ip(sandbox_id) or sandbox_db_host(sandbox_id)。
- **离线场景仍重建 sandbox 镜像**：存在 runtime/images/*.tar 时 compose 使用 --no-build，但脚本会先执行 compose build sandbox，确保 backend/sandbox/runner.py 的修改生效，避免 runner 仍用旧逻辑连 “mariadb” 或未读 _mariadb。
- **Podman 下 docker-compose**：若系统无 podman-compose，Podman 会查找 docker-compose；脚本将 runtime/docker 加入 PATH，使 podman compose 能找到项目自带的 docker-compose.exe（无需本机安装 Docker）。

### 2.4 特殊约束

- **安全**：沙箱内执行不可信 SQL/Python，依赖容器隔离；敏感信息（如 MARIADB_ROOT_PASSWORD）通过环境变量或 payload 传递，不落盘到代码库。
- **部署**：必须能执行 podman/docker 并挂载其 socket；Windows 需 WSL 与 Podman Machine；内网需提前在联网环境导出镜像与可选 examples 依赖。
- **隔离**：每沙箱独立 DB 与卷，销毁即删容器与卷；SQL 每请求在临时 database 内执行后删除，不跨请求残留。
- **数据库**：不使用 SQLite；无常驻 MariaDB 服务，仅按需起停沙箱 DB 容器。

---

## 3. 核心逻辑说明

### 3.1 高层运行逻辑

1. 用户或示例脚本调用 **POST /api/sandboxes** → backend 执行 create_sandbox() → 创建命名卷、启动 MariaDB 容器并加入 trusted-compute_default、轮询直至可连接 → 返回 sandbox_id。
2. 用户调用 **POST /api/execute-sql**（带 sandbox_id、sql、ddl/tables 或 data）→ backend 校验 sandbox_exists、取 sandbox_db_ip 或 sandbox_db_host、组装 input_params（含 _mariadb）→ 启动 runner 容器（--network trusted-compute_default），stdin 传入 JSON → runner 连接沙箱 MariaDB、建临时库、执行 DDL/插入/SQL、返回 JSON → backend 解析 stdout 并附加 execution_time_ms 返回给客户端。
3. **POST /api/execute-python**：backend 组装 model_type=python 的 payload，启动 runner（--network none），stdin/stdout 同上。
4. 用户调用 **DELETE /api/sandboxes/{sandbox_id}** → destroy_sandbox() → stop 容器、rm 容器、rm 卷。

### 3.2 数据流转

- **创建沙箱**：无用户数据；backend → podman/docker run MariaDB 容器 + 卷 → 返回 sandbox_id。
- **执行 SQL**：客户端 → backend（sandbox_id, sql, ddl, tables/data）→ backend 取 DB IP、组 payload → runner 容器（stdin JSON）→ runner 连 MariaDB、建临时库、写表、执行 SQL → 结果 JSON → stdout → backend → 客户端。
- **执行 Python**：客户端 → backend（code, input_params）→ runner 容器（无网）→ exec(code)、取 result → stdout JSON → backend → 客户端。
- **销毁沙箱**：客户端 sandbox_id → backend → stop/rm 容器、rm 卷。

### 3.3 模块关系

- **main** 依赖 schemas、sandbox_service、sandbox_db_lifecycle（create_sandbox、destroy_sandbox、sandbox_exists）。
- **sandbox_service** 依赖 sandbox_db_lifecycle（sandbox_exists、sandbox_db_ip、sandbox_db_host）；调用主机上的 podman/docker 运行镜像 trusted-compute-sandbox。
- **sandbox_db_lifecycle** 仅依赖主机上的 podman/docker 与 pymysql（等待 MariaDB 就绪）；不依赖其他业务模块。
- **runner** 在容器内独立运行，依赖 payload 与环境变量，无引用 backend 代码。

---

## 4. 部署方式

- **当前部署模型**：Compose 仅定义 backend 与 sandbox（build 用）；backend 挂载 ./backend 与 Docker/Podman socket；网络 trusted-compute_default；无 compose 级 MariaDB 服务。
- **容器与依赖**：  
  - 常驻：trusted-compute-backend（端口 8000）。  
  - 按需：trusted-compute-sandbox（runner，每次请求起一个 --rm 容器）、tc-sandbox-db-&lt;id&gt;（每个沙箱一个，带独立卷）。  
  - 镜像：trusted-compute-backend、trusted-compute-sandbox、MariaDB（如 mariadb:11.2），均由环境/Compose 或导出脚本指定。
- **环境依赖**：Podman 或 Docker；Windows 需 WSL 与 Podman Machine；若用脚本且存在 runtime/docker/docker-compose.exe，脚本会将其加入 PATH。
- **离线部署**：支持。在联网环境执行 export-images-for-offline.*，将 backend、sandbox、mariadb 的 tar 放入 runtime/images/，可选打包 examples 依赖到 examples/offline_wheels/；拷贝整份项目到内网后，同一启动脚本会 load 所有 tar、**重建 sandbox 镜像**、再 compose up --no-build。MariaDB 镜像在启动时即加载，首次创建沙箱无需拉取。
- **注意**：首次 build 或 export 时若无法访问 Docker Hub，使用 MARIADB_IMAGE 或脚本内默认国内镜像（如 docker.m.daocloud.io）；pip 若走不可用代理会报错，脚本里已对 download-examples-wheels 做临时取消代理处理。

---

## 5. 未完成事项 / 待优化点

- **测试**：无 pytest/单元测试；仅靠示例脚本与 Swagger 手测；可考虑为 API 与关键路径补自动化测试。
- **功能**：当前为“单次请求内”的 SQL/Python 执行与临时库；若需跨多次请求的持久表或更复杂的数据导入/导出/脱敏流程，需在现有 API 与沙箱生命周期上再设计。
- **性能**：每次 execute-sql 冷启动一个 runner 容器，约 2–10 秒量级；若需高吞吐可考虑池化或长驻 worker，会与当前“每请求一容器”的隔离模型权衡。
- **安全**：root 连接沙箱 DB、密码经环境变量/payload 传递；若需更强隔离或审计，可考虑专用 DB 用户、最小权限与审计日志。
- **技术债**：runner 与 backend 间约定（_mariadb 键、payload 结构）仅在代码与文档中体现，无 schema 或契约文件；可考虑在文档或接口定义中固化。
- **可讨论**：是否需要“沙箱列表/状态”查询接口、资源配额（如单用户最大沙箱数）、或与外部权限系统的集成方式。

---

## 6. 下一步建议

- **新对话优先**：若继续加功能，先对齐“项目上下文总结”与 docs/PROJECT_DOCUMENTATION.md，再在现有架构上扩展；若遇部署/启动问题，优先检查 Podman Machine、网络名、runtime/docker 的 PATH 与 sandbox 镜像是否已重建。
- **重构**：当前结构清晰，无紧急重构需求；若引入持久化或更多服务，再考虑拆分或扩展 backend 模块。
- **文档与测试**：PROJECT_DOCUMENTATION.md 已覆盖架构、部署、验证；建议在改动 API 或 payload 时同步更新该文档与 SQL_USAGE；若有回归需求，可增加接口级或端到端测试（如 pytest + TestClient 或 requests 调用 run_sql_examples 流程）。

---

## 7. 关键文件索引

| 用途 | 路径 |
|------|------|
| 完整项目文档 | docs/PROJECT_DOCUMENTATION.md |
| API 与快速开始 | README.md |
| SQL 接口说明 | docs/SQL_USAGE.md |
| 内网/离线部署 | docs/OFFLINE_DEPLOY.md、runtime/images/README.md |
| 沙箱生命周期 | backend/services/sandbox_db_lifecycle.py |
| 沙箱执行与 payload | backend/services/sandbox_service.py |
| 容器内 runner | backend/sandbox/runner.py |
| 启动脚本（含离线与 sandbox 重建） | scripts/start-for-client.ps1（及 .cmd、.sh） |
| 示例端到端 | examples/run_sql_examples.py |

---

*以上内容可直接粘贴到新对话作为项目背景，便于延续开发与排查问题。*
