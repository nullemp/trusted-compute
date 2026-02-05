# 代码执行流程说明

## 一、表是啥时候创建的？

**时机**：后端服务**第一次启动**时（例如 `docker-compose up` 后 backend 容器跑起来时）。

**位置**：`backend/main.py` 第 17-18 行：

```python
# Create tables
Base.metadata.create_all(bind=engine)
```

**含义**：  
- 导入 `main.py` 时会执行到这两行。  
- `engine` 连的是 MariaDB（`database.py` 里的 `DATABASE_URL`）。  
- `Base.metadata.create_all(bind=engine)` 会根据 `models.py` 里定义的 `Project`、`Participant`、`Task`、`TaskResult` 等模型，在数据库里**自动建表**（若表已存在则跳过）。  
- 所以**不需要**你手动执行建表 SQL，只要后端成功连上 MariaDB 并启动，表就会在那时创建好。

---

## 二、整体架构（谁调谁）

```
前端 (React)
    ↓ HTTP
后端 (FastAPI, main.py)
    ↓ 调用
各 Service（project_service, task_service, sandbox_service, encryption_service, data_masking_service）
    ↓ 读写
数据库 (MariaDB)  /  沙箱容器 (Docker)
```

---

## 三、「执行任务」的完整代码执行流程

以**用户在前端点击「执行任务」并提交入参**为例，从请求进入到返回结果，顺序如下。

### 1. 前端发请求

- 用户点击「执行任务」，输入 `input_params`（如 `{"threshold": 100}`），确认。
- 前端调用：  
  `POST /api/tasks/{task_id}/execute`  
  Body: `{ "input_params": { "threshold": 100 } }`。

### 2. 后端入口：`main.py` 的 `execute_task`

- 路由：`@app.post("/api/tasks/{task_id}/execute")`。
- 步骤：
  1. **查任务**  
     `task = task_service.get_task(db, task_id)`  
     从 MariaDB 读出该任务的 `model_type`、`model_code`、`output_config` 等。
  2. **沙箱执行**  
     `raw_result = sandbox_service.execute_task(db, task, execute_request.input_params)`  
     这里才真正“跑代码”，见下一节。
  3. **掐掉计时**  
     `execution_time = raw_result.pop("execution_time", None)`  
     沙箱会把执行时间塞进 `raw_result`，这里拿出来单独用，避免后面脱敏/加密把时间当数据。
  4. **脱敏**  
     `masked_result = data_masking_service.mask_data(raw_result, task.output_config)`  
     按任务配置（如对某字段哈希、泛化）对结果做脱敏。
  5. **加密**  
     `encrypted_result = encryption_service.encrypt_result(masked_result)`  
     把脱敏后的结果整体加密成一段密文（如 AES）。
  6. **落库并返回**  
     `result = task_service.save_result(db, task_id, encrypted_result, execution_time)`  
     把密文、哈希、执行时间等写入 `task_results` 表，并返回给前端（前端先看到的是“密文 + 可点「查看明文」”）。

### 3. 沙箱里到底发生了什么：`sandbox_service.execute_task`

- **作用**：在**独立 Docker 容器**里执行用户代码，不接触主进程和主机网络，执行完容器就销毁（`--rm`）。
- **步骤**：
  1. **拼输入**  
     把 `task.model_type`、`task.model_code`、用户传入的 `input_params` 拼成一个 JSON：  
     `payload = { "model_type": "sql"|"python", "model_code": "...", "input_params": {...} }`  
     转成 UTF-8 字节：`stdin_bytes = json.dumps(payload).encode("utf-8")`。
  2. **起容器**  
     ```bash
     docker run --rm --network none -i trusted-compute-sandbox
     ```  
     - `--rm`：跑完就删容器。  
     - `--network none`：无网络。  
     - `-i`：把上面那段 JSON 从**标准输入**喂给容器里的进程。  
     镜像 `trusted-compute-sandbox` 的入口是 `python /app/runner.py`（见 `backend/sandbox/Dockerfile`）。
  3. **等结束**  
     `subprocess.run(..., input=stdin_bytes, capture_output=True, timeout=60)`  
     主进程把 `stdin_bytes` 喂给 `docker run`，容器内 `runner.py` 从 stdin 读 JSON，执行完后把结果 JSON 打到 stdout，主进程从 `proc.stdout` 读回来。
  4. **解析并带回**  
     对 `proc.stdout` 做 `json.loads`，得到 `raw_result`（字典），再塞回 `execution_time`，返回给 `main.py` 的 `execute_task`。

### 4. 容器里在跑什么：`backend/sandbox/runner.py`

- **作用**：沙箱镜像里唯一的“业务逻辑”；从 stdin 读一条 JSON，执行 SQL 或 Python，把结果打成 JSON 从 stdout 写出。
- **步骤**：
  1. **读输入**  
     `payload = json.load(sys.stdin)`  
     就是上面 `sandbox_service` 传进来的 `{ "model_type", "model_code", "input_params" }`。
  2. **按类型执行**  
     - `model_type == "sql"` → `run_sql(model_code, input_params)`  
       - 把 `input_params` 里键值替换到 `model_code` 里的 `{{key}}`。  
       - 当前是**演示**：不连真实库，直接返回一段模拟的 `result`（列名 + 行数据）。  
     - `model_type == "python"` → `run_python(model_code, input_params)`  
       - 在进程里 `exec(model_code, local_names)`，其中 `local_names` 里有 `input_params`、`pd`、`np`。  
       - 执行完后从 `local_names["result"]` 取用户代码里写的 `result`，转成字典（例如 DataFrame → columns + data），再包成 `{"type":"python", "status":"success", "result": ...}`。
  3. **输出**  
     `print(json.dumps(out, ensure_ascii=False), flush=True)`  
     这一行就是沙箱给外界的“唯一输出”，被 `subprocess` 捕获成 `proc.stdout`。

### 5. 数据流小结（执行任务）

```
用户点击执行
  → POST /api/tasks/{id}/execute
  → main.execute_task
      → task_service.get_task(db, task_id)           # 从 DB 读任务定义
      → sandbox_service.execute_task(...)
          → 拼 JSON → docker run --rm -i 沙箱镜像
              → 容器内 runner.py: json.load(sys.stdin)
              → run_sql() 或 run_python() → print(json.dumps(out))
          → 主进程读 stdout → json.loads → raw_result
      → data_masking_service.mask_data(raw_result)   # 脱敏
      → encryption_service.encrypt_result(...)       # 加密
      → task_service.save_result(db, ...)            # 写 task_results 表
  → 返回密文等给前端
```

---

## 四、其他常见请求的流程（简要）

| 操作       | 入口（main.py）           | 主要动作 |
|------------|----------------------------|----------|
| 创建项目   | `POST /api/projects`       | `project_service.create_project(db, body)` → 插 `projects` 表 |
| 加入项目   | `POST /api/projects/{id}/join` | `project_service.join_project(...)` → 插/更新 `participants` 表 |
| 创建任务   | `POST /api/projects/{id}/tasks` | `task_service.create_task(db, project_id, body)` → 插 `tasks` 表 |
| 任务列表   | `GET /api/projects/{id}/tasks`  | `task_service.list_tasks(db, project_id)` → 查 `tasks` 表 |
| 结果列表   | `GET /api/tasks/{id}/results`   | `task_service.get_task_results(db, task_id)` → 查 `task_results` 表 |
| 查看明文   | `GET /api/tasks/{tid}/results/{rid}/decrypt` | `task_service.get_result` → `encryption_service.decrypt_result` → 返回脱敏后的明文 |

---

## 五、表结构从哪里来（再强调一次）

- **定义**：在 `backend/models.py`（`Project`、`Participant`、`Task`、`TaskResult` 等，用 SQLAlchemy 的 `Column`、`ForeignKey` 等）。
- **真正建表**：只在 `main.py` 里那一句 `Base.metadata.create_all(bind=engine)`，在后端**进程启动时**执行一次；之后每次请求只用这些表做增删改查，不会重复建表。

如果你关心的是“表什么时候被 create 出来的”，答案就是：**后端第一次启动并成功连上 MariaDB 的时候**。
