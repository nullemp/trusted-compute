## SQL 沙箱执行逻辑说明（含测试用例）

本文档基于当前代码实现，说明 **SQL 沙箱** 从创建到产出加密结果文件的执行流程，并给出可直接运行的测试用例。

---

## 1. 输入与输出概念

- **输入数据文件 `data.bin`**  
  - 明文来源：`enterprise_dump.json`，结构为：
    - `metadata`：描述信息；
    - `schema`：每张表的 DDL 文本（mysqldump 风格）；
    - `data`：`{ table_name: [row, ...], ... }`，每行是 JSON 对象。
  - 加密格式：  
    - 先对 `enterprise_dump.json` 做 PKCS7 补齐；  
    - 使用 SM4‑CBC（固定 16 字节密钥 `key_hex` 和 16 字节 IV）加密；  
    - 输出文件字节布局：`[前 16 字节为 IV] + [后续为 SM4‑CBC 密文]`。

- **SQL 计算脚本 `script.sql`**  
  - 例如：

    ```sql
    -- examples/models/script.sql
    SELECT SUM(salary) AS total_salary FROM employees;
    ```

  - 假定解密并建表后，数据库中存在 `employees` 等表。

- **输出结果文件 `result_*.bin`**  
  - 明文内容：优先为 **mysqldump 导出的 `_tc_result_` 表 SQL**（即 `sql_dump`），否则回退为本地生成的 SQL 片段或 JSON。  
  - 加密方式：使用与输入数据相同的 `key_hex` 和同一个 IV（直接取原始 `data.bin` 的前 16 字节），再做一次 SM4‑CBC 加密，文件格式同上。

---

## 2. 后端主要组件

- `backend/main.py`
  - 提供 HTTP API：`/api/sandboxes`、`/api/sandboxes/{id}/import-and-run`、`/api/sandboxes/{id}/run` 等。
  - 负责：
    - 创建 SQL 沙箱（工作目录 + 独立 MariaDB 容器）；
    - 读取数据/脚本/密钥；
    - 调用 `sandbox_service.execute_sql` 触发沙箱计算；
    - 根据 `RESULTS_ROOT` + `RESULTS_HOST_ROOT` 生成结果文件，并返回宿主机绝对路径。

- `backend/services/sandbox_service.py`
  - 封装沙箱容器的生命周期（每次执行起一个 `trusted-compute-sandbox` 容器，跑完即退出）。
  - 将 `model_type="sql"` + `model_code`（SQL 文本）+ `input_params` 通过 stdin 传给容器内的 `runner.py`，接收 stdout JSON。

- `backend/sandbox/runner.py`
  - 运行在 `trusted-compute-sandbox` 容器内部，是 SQL 模型的真正执行环境。
  - 负责：
    - SM4‑CBC 解密和 JSON 解析；
    - 在专属 MariaDB 数据库中建表、灌数据；
    - 执行 `script.sql`，生成结果表 `_tc_result_`；
    - 调用 `mysqldump` 导出 `_tc_result_`，并将 dump SQL 放入结果 JSON 的 `result.sql_dump` 字段。

---

## 3. SQL 沙箱执行流程（导入 + 执行一体化）

推荐使用新的便捷接口：`POST /api/sandboxes/{sandbox_id}/import-and-run`，一次完成「导入 + 执行」。  
当前支持两种模式：

- **模式 A：仅导入，不执行运算（model_file 为空）**
  - 只上传 `data_file` + `key_hex`；
  - 沙箱将 `data_file` 解密为 JSON：
    - 若是 `enterprise_dump.json` 这种带 `schema` + `data` 的结构，会：
      - 从 `schema.*` 拼接出整段 DDL，在 MariaDB 内按原始类型（INT/DOUBLE/VARCHAR 等）建表；
      - 将 `data` 中每张表的数据灌入对应表；
    - 若 JSON 已经带有 `ddl` / `tables` 字段，则直接按这些字段建表与灌数；
  - 不执行额外 SQL（没有计算脚本）；
  - 最后对整个 database 执行 `mysqldump`，将所有表导出为 SQL，再加密写入 `result_*.bin`。

- **模式 B：导入后执行 SQL 模型脚本（model_file 为 script.sql）**
  - 上传 `data_file` + `model_file` + `key_hex`；
  - 数据导入过程与模式 A 相同（同样会优先使用 JSON 中的 `schema`/`ddl` 来建表）；
  - 之后在该 database 中执行 `script.sql`（支持多条语句，按顺序执行，取第一条有结果集的语句）；
  - 将结果集写入 `_tc_result_` 表，再用 `mysqldump` 仅导出 `_tc_result_`，加密写入 `result_*.bin`。

### 3.1 创建 SQL 沙箱

1. 客户端调用：

   ```powershell
   $resp = curl.exe -X POST "http://localhost:8000/api/sandboxes?type=sql"
   $SANDBOX_ID = ($resp.Content | ConvertFrom-Json).sandbox_id
   $SANDBOX_ID
   ```

2. `backend/main.py::api_create_sandbox`：
   - 调用 `create_sql_sandbox()`：
     - 为该 `sandbox_id` 启动一个独立的 MariaDB 容器（实例隔离）；  
     - 为 SQL 沙箱创建工作目录（但在 `import-and-run` 场景下不再写入 data/script/key）。
   - 返回：

   ```json
   {"status":0,"sandbox_id":"<sandbox_id>","error":""}
   ```

### 3.2 导入并执行（`import-and-run`，模式 B：带模型脚本）

1. 客户端调用：

   ```powershell
   $DATA_FILE  = "D:\develop\trusted-compute\trusted-compute\examples\data\enterprise_dump_encrypted.bin"
   $MODEL_FILE = "D:\develop\trusted-compute\trusted-compute\examples\models\script.sql"
   $KEY_HEX    = "00112233445566778899AABBCCDDEEFF"

   $runResp = curl.exe -X POST "http://localhost:8000/api/sandboxes/$SANDBOX_ID/import-and-run" `
     -F "data_file=@$DATA_FILE" `
     -F "model_file=@$MODEL_FILE" `
     -F "key_hex=$KEY_HEX"

   $runJson = $runResp.Content | ConvertFrom-Json
   $runJson
   ```

2. `backend/main.py::api_import_and_run_sandbox`：

   - 校验 `sandbox_id` 对应的是 SQL 沙箱。
   - 从上传的 `data_file` / `model_file` / `key_hex` 读取：
     - `data_content: bytes`；
     - `sql_content: str`（脚本内容；为空字符串时表示不执行运算，仅导入并 dump，全库导出即模式 A）；  
     - `key_hex: str`（表单字段）。
   - **不再写入 workspace 目录**，而是直接在内存中构造 `cipher_b64`：

     ```python
     cipher_b64 = base64.b64encode(data_content).decode("ascii")
     ```

   - 调用（两种模式共用这一步）：

     ```python
     out = sandbox_service.execute_sql(
         sandbox_id=sandbox_id,
         sql=sql_content,
         cipher_b64=cipher_b64,
         key_hex=key_hex,
     )
     ```

   - 若 `out["status"] == "error"`：返回 `status=1` + 错误信息。
   - 否则调用 `_encrypt_and_save_result`：
     - 从 `data_content` 头 16 字节取出 IV；
     - 使用 `key_hex` 恢复 16 字节 SM4 密钥；
     - 优先从 `out["result"]["sql_dump"]` 取出 dump SQL 作为明文；
     - 若没有 `sql_dump`，退回为简易 SQL 片段或完整 JSON；
     - 使用 `sm4_cbc_encrypt_py` 做 SM4‑CBC 加密，拼接 `[IV + 密文]` 写入：

       ```text
       backend/results/<sandbox_id>/result_<timestamp>.bin
       ```

   - 为了让客户端直接拿到 **宿主机绝对路径**，`_encrypt_and_save_result` 返回的容器内路径会经过 `_to_host_results_path` 映射：
     - `RESULTS_ROOT`：容器内结果目录（默认 `/app/results`，挂载自 `./backend/results`）；  
     - `RESULTS_HOST_ROOT`：通过环境变量配置的宿主机目录，例如：

       ```powershell
       RESULTS_HOST_ROOT = "D:\develop\trusted-compute\trusted-compute\backend\results"
       ```

     - 后端最终在响应中返回 Windows 绝对路径，例如：

       ```json
       {
         "status": 0,
         "sandbox_id": "9d939ca047c64b5f",
         "path": "D:\\develop\\trusted-compute\\trusted-compute\\backend\\results\\9d939ca047c64b5f\\result_1772632235004.bin",
         "error": ""
       }
       ```

3. 客户端得到 `$runJson.path` 后，可以直接用解密脚本查看明文 SQL：
   - **模式 A（仅导入）：** 解密结果是整个 database 的 mysqldump SQL（所有表的 DDL+INSERT）；  
   - **模式 B（带脚本）：** 解密结果是 `_tc_result_` 这张结果表的 mysqldump SQL（只含计算结果）。

### 3.3 可选：销毁沙箱

```powershell
curl.exe -X DELETE "http://localhost:8000/api/sandboxes/$SANDBOX_ID"
```

用于清理对应的 MariaDB 容器和数据卷（结果文件会在 `backend/results/<sandbox_id>/` 下保留，直至手工删除）。

---

## 4. 容器内部 SQL 执行细节（runner.py）

以下为 `backend/sandbox/runner.py::run_sql` 的关键步骤。

### 4.1 SM4 解密与 JSON 解析

1. 发现 `input_params` 中包含 `cipher_b64`：
   - base64 解码得到 `[IV + 密文]`；
   - 分离出 `iv = cipher_all[:16]`，`cipher = cipher_all[16:]`；
   - 使用 `_sm4_cbc_decrypt_py(key, iv, cipher)` 解密并去 PKCS7 填充；
   - 将解密得到的 JSON 解析为字典 `payload`。

2. 若 `payload` 包含 `data` 字段，则：

   ```python
   input_params["data"] = payload.get("data", payload)
   ```

3. 为兼容 `enterprise_dump.json` 这种 `{table_name: rows, ...}` 结构，当：

   - `input_params["tables"]` 为空；  
   - 且 `input_params["data"]` 是一个字典 `{ "employees": [...], "departments": [...], ... }` 时，

   自动转换为多表模式：

   ```python
   input_params["tables"] = [
       {"table_name": name, "data": rows}
       for name, rows in input_params["data"].items()
       if isinstance(rows, list)
   ]
   input_params.pop("data", None)
   ```

### 4.2 在独立 database 中建表与灌数据

1. 生成 `db_name = "sandbox_" + uuid.uuid4().hex[:16]`。
2. 使用 root 连接 MariaDB，执行：

   ```sql
   CREATE DATABASE `db_name`;
   ```

3. 重新连接到该 `db_name`，按以下优先级加载数据：
   - 若有 `ddl`：先执行 DDL，再插入 `tables`；
   - 若有 `tables`：为每张表调用 `_create_table_from_data`，根据数据推断列名/类型，并插入行；
   - 若只有 `data`：视为单表 `input_data` 进行建表和插入。

### 4.3 执行脚本并导出结果表

1. 将整段 `sql_content` 按 `;` 分割为多条语句，依次执行；
2. 记录第一条有结果集的语句：
   - `result_columns`：列名列表；
   - `result_rows`：二维数组；
   - `row_count`：结果行数。

3. 若存在结果集：
   - 创建结果表 `_tc_result_`：
     - 若只有一条 `SELECT` 且不含 `INTO`：

       ```sql
       DROP TABLE IF EXISTS `_tc_result_`;
       CREATE TABLE `_tc_result_` AS <原始 SELECT>;
       ```

     - 否则退回到：手动建表 + 多条 `INSERT`。

4. 调用 `mysqldump` 导出 `_tc_result_`：

   ```bash
   mysqldump -h<host> -P<port> -u<user> -p<PASSWORD> \
     --skip-comments --skip-set-charset \
     <db_name> _tc_result_
   ```

   成功时将 `stdout` 原样放入返回 JSON 中的 `result.sql_dump`。

5. 清理临时 database：

   ```sql
   DROP DATABASE IF EXISTS `db_name`;
   ```

6. 返回结果 JSON（传回宿主机）：

   ```json
   {
     "status": "success",
     "type": "sql",
     "result": {
       "columns": ["total_salary"],
       "data": [[54000.0]],
       "row_count": 1,
       "sql_dump": "DROP TABLE IF EXISTS `_tc_result_`; ... INSERT INTO `_tc_result_` ...;"
     }
   }
   ```

---

## 5. 端到端测试用例

以下测试用例涵盖：创建 SQL 沙箱 → 导入并执行 → 解密结果 SQL。

### 5.1 前置准备

1. 通过 `scripts/start-for-client.ps1` 启动服务（Windows PowerShell）：

   ```powershell
   cd D:\develop\trusted-compute\trusted-compute
   .\scripts\start-for-client.ps1
   ```

   脚本会：
   - 启动 Podman/Docker；  
   - 构建/加载镜像；  
   - 设置 `RESULTS_HOST_ROOT`（指向 `backend\results`）并通过 docker-compose 传入 backend 容器；  
   - 启动 `trusted-compute-backend` 服务，监听 `http://localhost:8000`。

2. 确认存在示例文件：
   - `examples/data/enterprise_dump_encrypted.bin`
   - `examples/models/script.sql`

### 5.2 创建 SQL 沙箱

```powershell
$resp = curl.exe -X POST "http://localhost:8000/api/sandboxes?type=sql"
$SANDBOX_ID = ($resp.Content | ConvertFrom-Json).sandbox_id
$SANDBOX_ID
```

预期：输出一个 16 字节 hex 的 `sandbox_id`，例如 `9d939ca047c64b5f`。

### 5.3 导入并执行（import-and-run）

```powershell
$DATA_FILE  = "D:\develop\trusted-compute\trusted-compute\examples\data\enterprise_dump_encrypted.bin"
$MODEL_FILE = "D:\develop\trusted-compute\trusted-compute\examples\models\script.sql"
$KEY_HEX    = "00112233445566778899AABBCCDDEEFF"

$runResp = curl.exe -X POST "http://localhost:8000/api/sandboxes/$SANDBOX_ID/import-and-run" `
  -F "data_file=@$DATA_FILE" `
  -F "model_file=@$MODEL_FILE" `
  -F "key_hex=$KEY_HEX"

$runJson = $runResp.Content | ConvertFrom-Json
$runJson
```

预期返回结构类似：

```json
{
  "status": 0,
  "sandbox_id": "9d939ca047c64b5f",
  "path": "D:\\develop\\trusted-compute\\trusted-compute\\backend\\results\\9d939ca047c64b5f\\result_1772632235004.bin",
  "error": ""
}
```

注意：
- `path` 为 **宿主机上的绝对路径**（依赖 `RESULTS_HOST_ROOT` 环境变量配置正确）。

### 5.4 解密结果文件并查看 SQL

使用项目根目录下的 `decrypt_result.py`（脚本示例）：

```powershell
cd D:\develop\trusted-compute\trusted-compute

python .\decrypt_result.py `
  "D:\develop\trusted-compute\trusted-compute\backend\results\9d939ca047c64b5f\result_1772632235004.bin" `
  --out "D:\tmp\result.sql"
```

然后查看 `D:\tmp\result.sql`：

- 里面是 mysqldump 风格的 `_tc_result_` 表 SQL，例如：

  ```sql
  DROP TABLE IF EXISTS `_tc_result_`;
  CREATE TABLE `_tc_result_` (
    `total_salary` decimal(??,??) ...
  ) ...;
  INSERT INTO `_tc_result_` (`total_salary`) VALUES ('54000.0');
  ```

- 可以直接导入到任意 MySQL/MariaDB 实例：

  ```bash
  mysql -h ... -P ... -u ... -p your_db < D:\tmp\result.sql
  ```

### 5.5 清理沙箱

```powershell
curl.exe -X DELETE "http://localhost:8000/api/sandboxes/$SANDBOX_ID"
```

预期：返回 `{ "status": 0, "path": "", "error": "" }`，对应的 MariaDB 容器和卷会被删除。结果文件仍保留在 `backend\results\<sandbox_id>\` 下，供后续分析或人工删除。

