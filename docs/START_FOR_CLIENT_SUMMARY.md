# 客户端启动方式总结（Windows + Podman）

本文总结在 Windows 上通过 **start-for-client** 脚本启动后端与数据库的流程、常见问题及解决办法。

---

## 一、启动方式

### 1. 一键启动（推荐）

在**项目根目录**执行：

```cmd
.\scripts\start-for-client.cmd
```

或 PowerShell（若已放宽执行策略）：

```powershell
.\scripts\start-for-client.ps1
```

脚本会按顺序完成：

1. **检测运行时**：优先使用项目内 `runtime\podman\` 或 `runtime\docker\`，否则用系统 PATH 中的 podman/docker。
2. **WSL**（仅 Windows + Podman）：若未安装 WSL，自动执行 `wsl --install`（需 UAC）；若已安装但无发行版，会再次安装默认 Ubuntu。
3. **Podman Machine**（仅 Windows + Podman）：若无运行中的 VM，执行 `podman machine init` + `podman machine start`，并轮询 `podman info` 直至就绪（最多 60 秒）。
4. **docker-compose**：若 Podman 无 compose 插件，自动下载 docker-compose 到 `runtime\docker\docker-compose.exe`，并设置 `DOCKER_HOST=npipe:////./pipe/docker_engine`，使用国内镜像（DaoCloud）拉取 mariadb/python 镜像，关闭 BuildKit 做传统构建，最后执行 `docker-compose up -d --build`。

### 2. 不依赖客户环境（捆绑运行时）

- 将 **Podman** 或 **Docker** 可执行文件放入项目目录：
  - **Windows**：`runtime\podman\podman.exe` 或 `runtime\docker\docker.exe`
  - 可选：同目录放 `docker-compose.exe`
- 脚本会优先使用上述路径，无需客户机预装 Docker/Podman。
- 详见 [DOCKER_IN_CLIENT.md](../DOCKER_IN_CLIENT.md) 与 [runtime/README.md](../runtime/README.md)。

### 3. 仅用 Docker（不用 Podman）

- 安装 **Docker Desktop for Windows**，或将 `docker.exe` 放入 `runtime\docker\`。
- 若存在 `runtime\podman\`，脚本会优先用 Podman；可临时重命名或删除 `runtime\podman` 以改用 Docker。

---

## 二、遇到的问题与解决办法

### 1. PowerShell 禁止运行脚本

**现象**：`无法加载文件 ... .ps1，因为在此系统上禁止运行脚本`  

**原因**：PowerShell 默认执行策略为 Restricted，禁止运行本地脚本。

**解决**：
- 使用 **.cmd 包装器**（推荐）：运行 `.\scripts\start-for-client.cmd` 或 `.\scripts\download-runtime.cmd`，内部通过 `powershell -ExecutionPolicy Bypass` 调用 .ps1，无需改策略。
- 或放宽策略（当前用户）：以管理员打开 PowerShell，执行  
  `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`。

---

### 2. 未找到 podman-compose / docker-compose

**现象**：`podman-compose not found, using docker-compose`，随后 `docker-compose 不是内部或外部命令`。

**原因**：Podman 5.x 安装包不一定带 compose 插件；系统也未安装 docker-compose。

**解决**：脚本已内置逻辑：检测到 Podman 无 compose 时，自动从 GitHub（或镜像）下载 **docker-compose** 到 `runtime\docker\docker-compose.exe`，并用**完整路径**调用，避免依赖 PATH。若下载失败，会提示手动下载并放入该路径。

---

### 3. WSL 未安装 / 无发行版

**现象**：`Cannot connect to Podman`、`wsl.exe --install` 提示，或“没有已安装的分发”。

**原因**：Podman 在 Windows 上依赖 WSL；WSL 需先安装且至少有一个 Linux 发行版（如 Ubuntu）。

**解决**：
- 脚本会先检测 WSL（`wsl -l -v` / `wsl -e echo 0`），未就绪时自动执行 `wsl --install`（会弹 UAC）。
- 若已启用 WSL 但无发行版，再次运行脚本会补装默认 Ubuntu；若提示需重启，重启后再运行脚本。
- 为避免“反复弹 UAC”的循环，脚本用 marker 文件记录“已触发安装”，已安装过则不再重复执行安装，直接尝试启动 Podman。

---

### 4. Podman Machine “VM already exists” 仍报错

**现象**：`Error: podman-machine-default: VM already exists`，随后提示“Podman needs WSL”并退出。

**原因**：脚本把 `podman machine init` 的任意非零退出都当成失败；而“VM 已存在”时 init 会报错但只需执行 `podman machine start`。

**解决**：脚本改为：无论 init 是否成功都执行 `podman machine start`，再用 `podman info` 轮询最多 60 秒判断是否就绪，不再仅凭 init 的退出码报错。

---

### 5. Podman Machine “未达到 running” / 启动后立即检查失败

**现象**：`Podman Machine did not reach running state` 或刚 start 就检查列表没有 “running”。

**原因**：`podman machine start` 返回后，VM 和 API 可能还需几秒才就绪；或 `podman machine list` 输出格式/编码与预期不符。

**解决**：
- 用 **`podman info` 的退出码**判断就绪，替代解析 list 输出。
- 启动后**轮询最多 60 秒**，每秒执行一次 `podman info`，成功即继续。

---

### 6. docker-compose 报 “connection refused” / “i/o timeout”

**现象**：`Error response from daemon: connection refused` 或 `i/o timeout`。

**原因**：  
- 刚启动 Podman Machine 后，npipe 可能尚未开始监听。  
- 或拉取镜像时连 Docker Hub 超时（国内网络）。

**解决**：
- 在确认 “Podman Machine is running.” 后**等待约 5 秒**再执行 compose。
- 使用 **cmd** 在**同一进程**中设置 `DOCKER_HOST=npipe:////./pipe/docker_engine` 再调用 docker-compose，避免子进程拿不到环境变量。
- **国内镜像**：设置 `MARIADB_IMAGE=docker.m.daocloud.io/library/mariadb:11`、`PYTHON_IMAGE=docker.m.daocloud.io/library/python:3.11-slim`（在 docker-compose.yml 中通过变量引用）。
- compose 失败时**自动重试一次**（间隔 10 秒）。

---

### 7. 镜像名 “invalid reference format” / 环境变量带空格

**现象**：`parsing reference "docker.m.daocloud.io/library/mariadb:11 ": invalid reference format` 或 `parsing "0 ": invalid syntax`。

**原因**：在 cmd 中用 `set VAR=value` 时，若写法不当会带入**尾部空格**，导致镜像名或 DOCKER_BUILDKIT 等变量值带空格。

**解决**：在 cmd 中一律使用 **`set "VAR=value"`** 形式（等号后、引号内无空格），并在 PowerShell 中正确转义引号（反引号 `"），确保传给 compose 的值无首尾空格。

---

### 8. BuildKit 拉取 moby/buildkit 超时

**现象**：`pulling image moby/buildkit:buildx-stable-1` 后长时间无输出或 i/o timeout。

**原因**：docker-compose 默认使用 BuildKit 构建，会先拉取 buildkit 镜像，在国内易超时。

**解决**：在运行 compose 前设置 **`DOCKER_BUILDKIT=0`** 和 **`COMPOSE_DOCKER_CLI_BUILD=0`**，使用传统 `docker build`，不再拉取 buildkit 镜像；基础镜像仍使用国内源（mariadb、python）。

---

### 9. 构建完成后“卡住”无输出

**现象**：镜像构建成功、出现 “SECURITY WARNING” 后长时间无新输出。

**原因**：compose 在启动容器并等待 **mariadb healthcheck** 通过，以及 backend 依赖 db 就绪；这几步可能需 1～3 分钟且控制台常无新输出。

**解决**：属正常现象，**多等 2～3 分钟**。可另开终端执行 `podman ps -a`（需先设 `DOCKER_HOST=npipe:////./pipe/docker_engine`）查看容器是否已 Up；若已 Up，可直接访问 http://localhost:8000/docs 。

---

### 10. PowerShell 下运行客户端脚本无输出

**现象**：在 PowerShell 中直接执行 `python -u wait_for_api.py`、`run_analysis_demo.py`、`execute_sql_files_demo.py` 时，控制台没有任何输出（“等待 API 就绪”、JSON 结果、“完成”等都不显示）。

**原因**：Windows 控制台默认代码页可能不是 UTF-8（如 CP936），Python 以 UTF-8 输出时可能导致乱码或不显示；或 stdout 缓冲/编码导致输出未及时显示。

**解决**：
- **推荐**：在运行 Python 前设置环境变量：`$env:PYTHONIOENCODING = "utf-8"`，然后执行脚本；或先执行 `chcp 65001` 将控制台切到 UTF-8。
- 使用项目提供的 **run_tests.cmd**（推荐，无需改执行策略）或 **run_tests.ps1**：在 `client-simulator` 目录下执行 `.\run_tests.cmd` 即可；脚本会设置 `PYTHONIOENCODING=utf-8`，且三个 demo 脚本内已对 Windows 强制 stdout/stderr 使用 UTF-8 并带 `flush=True`，输出应能正常显示。
- 若仍无输出，确认已安装依赖：`pip install requests`；并确认后端已启动（如先执行 `.\scripts\start-for-client.cmd`）。

---

## 三、脚本与配置要点速查

| 项目 | 说明 |
|------|------|
| 启动入口 | `.\scripts\start-for-client.cmd`（或 .ps1） |
| 捆绑运行时 | `runtime\podman\podman.exe` 或 `runtime\docker\docker.exe` |
| WSL | 需 Windows 10 2004+ / Win11；无 WSL 时脚本会尝试 `wsl --install` |
| Podman compose | 无插件时自动下载 docker-compose 到 `runtime\docker\`，并设 DOCKER_HOST |
| 国内镜像 | MARIADB_IMAGE、PYTHON_IMAGE 指向 DaoCloud；DOCKER_BUILDKIT=0 避免拉 buildkit |
| 环境变量 | 在 cmd 中用 `set "VAR=value"`，避免值带空格 |

---

## 四、成功后的访问地址

- **后端 API 文档**：http://localhost:8000/docs  
- **后端 API**：http://localhost:8000  
- **MariaDB**：localhost:3306（用户/库见 docker-compose.yml）

若需前端界面，需使用 `docker-compose --profile frontend up -d --build`（或 podman compose 等价命令），并访问 http://localhost:3000 。

---

## 五、浏览器里如何测试

后端启动后，用浏览器打开 **http://localhost:8000/docs**，即可在 Swagger 页面里点接口、填参数、上传文件并查看返回结果。

### 1. 先确认服务就绪

- 在文档页找到 **GET /**，点击 “Try it out” → “Execute”。
- 若返回 `200` 且响应体类似 `{"message":"..."}`，说明服务正常。

### 2. 测试「多表 CSV + 一条 SQL」：POST /api/execute-sql/files

1. 找到 **POST /api/execute-sql/files**，点击 “Try it out”。
2. **config**（必填）填下面 JSON（与 client-simulator 的 demo 一致，两表：orders、users，一条汇总 SQL）：

```json
{
  "tables": [
    {
      "table_name": "orders",
      "ddl": "id INT, user_id INT, amount DECIMAL(10,2), created_at VARCHAR(20)",
      "has_header": true,
      "delimiter": ","
    },
    {
      "table_name": "users",
      "ddl": "id INT, name VARCHAR(100)",
      "has_header": true,
      "delimiter": ","
    }
  ],
  "sql": "SELECT u.name, SUM(o.amount) AS total FROM orders o JOIN users u ON o.user_id = u.id GROUP BY u.name"
}
```

3. **files**：上传两个 CSV。顺序须与上面 `tables` 一致：  
   - 第 1 个：orders.csv（列如 id, user_id, amount, created_at）  
   - 第 2 个：users.csv（列如 id, name）  
   可直接用项目里 `client-simulator/data/orders.csv` 和 `client-simulator/data/users.csv`。
4. 点击 “Execute”，在响应里看 `status`、`result.columns`、`result.data` 即为数据处理结果。

### 3. 测试「DDL + 数据文件 + SQL 分析」：POST /api/run-analysis

1. 找到 **POST /api/run-analysis**，点击 “Try it out”。
2. **config** 填（analysis_type 为 sql，同上 SQL）：

```json
{
  "tables": [
    {
      "table_name": "orders",
      "ddl": "id INT, user_id INT, amount DECIMAL(10,2), created_at VARCHAR(20)",
      "has_header": true,
      "delimiter": ","
    },
    {
      "table_name": "users",
      "ddl": "id INT, name VARCHAR(100)",
      "has_header": true,
      "delimiter": ","
    }
  ],
  "analysis_type": "sql",
  "sql": "SELECT u.name, SUM(o.amount) AS total FROM orders o JOIN users u ON o.user_id = u.id GROUP BY u.name"
}
```

3. **files**：同样上传 `orders.csv`、`users.csv`（顺序与 tables 一致）。
4. **ddl_file**（可选）：可上传 `client-simulator/data/schema.sql`；不传则按 config 里每表的 ddl 建表。
5. 点击 “Execute”，响应中的 `result.data` 即为按用户汇总的订单金额等结果。

### 小结

| 操作           | 地址 / 接口                      |
|----------------|----------------------------------|
| 打开 API 文档  | http://localhost:8000/docs      |
| 检查服务就绪   | GET /                            |
| 多表 CSV + SQL | POST /api/execute-sql/files     |
| DDL + 文件 + SQL 分析 | POST /api/run-analysis |

---

## 六、使用 curl 测试

在终端用 curl 调用接口时，需保证后端已启动（如 `.\scripts\start-for-client.cmd`），且从 **client-simulator** 目录执行（或把下面路径改成你的 orders.csv、users.csv 所在路径）。

### 1. 检查服务是否就绪

```bash
curl -s http://localhost:8000/
```

返回 JSON 即表示服务正常。

### 2. POST /api/execute-sql/files（多表 CSV + 一条 SQL）

**方式一：config 用文件（推荐，避免引号转义）**

先把 config 存成文件，例如在 `client-simulator` 下创建 `config_execute.json`：

```json
{"tables":[{"table_name":"orders","ddl":"id INT, user_id INT, amount DECIMAL(10,2), created_at VARCHAR(20)","has_header":true,"delimiter":","},{"table_name":"users","ddl":"id INT, name VARCHAR(100)","has_header":true,"delimiter":","}],"sql":"SELECT u.name, SUM(o.amount) AS total FROM orders o JOIN users u ON o.user_id = u.id GROUP BY u.name"}
```

然后执行（**Linux/macOS/Git Bash**）。注意：用文件传 config 时字段名须为 **config_file**。若使用从数据库导出的 **schema.sql** 作为建表依据，可同时传 **ddl_file**：

```bash
cd client-simulator
curl -s -X POST http://localhost:8000/api/execute-sql/files \
  -F "config_file=@config_execute.json" \
  -F "ddl_file=@data/schema.sql" \
  -F "files=@data/orders.csv" \
  -F "files=@data/users.csv"
```

**Windows CMD 或 PowerShell**（PowerShell 中必须写 **curl.exe**）：

```cmd
cd client-simulator
curl.exe -s -X POST http://localhost:8000/api/execute-sql/files -F "config_file=@config_execute.json" -F "ddl_file=@data/schema.sql" -F "files=@data/orders.csv" -F "files=@data/users.csv"
```

**方式二：config 直接写在命令行（Linux/macOS/Git Bash，Form 字段名为 config）**

```bash
curl -s -X POST http://localhost:8000/api/execute-sql/files \
  -F 'config={"tables":[{"table_name":"orders","ddl":"id INT, user_id INT, amount DECIMAL(10,2), created_at VARCHAR(20)","has_header":true,"delimiter":","},{"table_name":"users","ddl":"id INT, name VARCHAR(100)","has_header":true,"delimiter":","}],"sql":"SELECT u.name, SUM(o.amount) AS total FROM orders o JOIN users u ON o.user_id = u.id GROUP BY u.name"}' \
  -F "files=@data/orders.csv" \
  -F "files=@data/users.csv"
```

### 3. POST /api/run-analysis（DDL + 数据文件 + SQL 分析）

同样建议把 config 写入文件 `config_run.json`（内容见下），再传参。

**config_run.json**（单行）：

```json
{"tables":[{"table_name":"orders","ddl":"id INT, user_id INT, amount DECIMAL(10,2), created_at VARCHAR(20)","has_header":true,"delimiter":","},{"table_name":"users","ddl":"id INT, name VARCHAR(100)","has_header":true,"delimiter":","}],"analysis_type":"sql","sql":"SELECT u.name, SUM(o.amount) AS total FROM orders o JOIN users u ON o.user_id = u.id GROUP BY u.name"}
```

**Linux/macOS/Git Bash**（用文件传 config 时字段名为 **config_file**）：

```bash
curl -s -X POST http://localhost:8000/api/run-analysis \
  -F "config_file=@config_run.json" \
  -F "files=@data/orders.csv" \
  -F "files=@data/users.csv"
```

带 DDL 文件（可选）：

```bash
curl -s -X POST http://localhost:8000/api/run-analysis \
  -F "config_file=@config_run.json" \
  -F "files=@data/orders.csv" \
  -F "files=@data/users.csv" \
  -F "ddl_file=@data/schema.sql"
```

**Windows CMD 或 PowerShell**（PowerShell 请用 **curl.exe**）：

```cmd
curl.exe -s -X POST http://localhost:8000/api/run-analysis -F "config_file=@config_run.json" -F "files=@data/orders.csv" -F "files=@data/users.csv"
```

### 4. 查看返回结果

上述 curl 会直接输出接口返回的 JSON。其中：

- `"status":"success"` 表示成功；
- `result.columns` 为列名数组；
- `result.data` 为行数据（如按用户汇总的订单金额）。

若需格式化输出，可将结果管道给 `jq`（需已安装）：`curl -s ... | jq .`
