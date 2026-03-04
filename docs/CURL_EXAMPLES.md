# 使用 curl 调用沙箱 API 示例

以下示例在 **Windows PowerShell** 下使用 `curl.exe`（请勿用 PowerShell 内置的 `curl` 别名）。服务默认地址：`http://localhost:8000`。  
**导入沙箱**时，Python 与 SQL 统一使用三参数：`data_file`（加密数据文件）、`model_file`（.py 或 .sql 脚本）、`key_hex`（明文密钥）。请将示例中的路径改为你本机的实际路径。

---

## 一、Python 沙箱完整示例（创建 → 导入 → 执行 → 销毁）

三步：创建 Python 沙箱 → 导入加密数据 + 模型脚本 + 密钥 → 执行；用完后销毁。加密数据文件格式：**前 16 字节 IV + SM4-CBC 密文**。

### 1. 创建 Python 沙箱

```powershell
curl.exe -X POST "http://localhost:8000/api/sandboxes?type=python"
```

返回示例：`{"status":0,"sandbox_id":"a1b2c3d4e5f67890","error":""}`，记下 `sandbox_id`。

### 2. 导入（三个参数：加密数据文件、Python 模型脚本、明文密钥）

```powershell
$SANDBOX_ID = "da1478ef32c44a92"
$DATA_FILE = "D:\develop\trusted-compute\trusted-compute\examples\data\enterprise_dump_encrypted.bin"
$MODEL_FILE = "D:\develop\trusted-compute\trusted-compute\examples\models\enterprise_aggregate_model.py"
$KEY_HEX = "00112233445566778899AABBCCDDEEFF"

curl.exe -X POST "http://localhost:8000/api/sandboxes/$SANDBOX_ID/import" -F "data_file=@$DATA_FILE" -F "model_file=@$MODEL_FILE" -F "key_hex=$KEY_HEX"
```

成功返回：`{"status":0,"sandbox_id":"...","error":""}`。

### 3. 执行（在沙箱内解密并跑 Python，默认连本沙箱 MariaDB）

```powershell
curl.exe -X POST "http://localhost:8000/api/sandboxes/$SANDBOX_ID/run"
```

可选：指定其他 DB 沙箱：  
`curl.exe -X POST "http://localhost:8000/api/sandboxes/$SANDBOX_ID/run?db_sandbox_id=另一个沙箱ID"`

### 4. 销毁沙箱

```powershell
curl.exe -X DELETE "http://localhost:8000/api/sandboxes/$SANDBOX_ID"
```

---

## 二、SQL 沙箱完整示例（创建 → 导入 → 执行 → 销毁）

三步：创建 SQL 沙箱 → 导入加密数据 + SQL 脚本 + 密钥 → 执行；用完后销毁。加密数据文件格式同上：**前 16 字节 IV + SM4-CBC 密文**。

### SQL 场景：仅走 3 步（创建 → 导入 → 销毁）

下面三条命令依次执行即可（将 `$DATA_FILE`、`$MODEL_FILE` 换成你本机路径；第二步的 `$SANDBOX_ID` 用第一步返回的 id 替换）。

```powershell
# 1. 创建 SQL 沙箱（返回 sandbox_id，用于后续两步）
curl.exe -X POST "http://localhost:8000/api/sandboxes?type=sql"

# 2. 导入沙箱（三参数：加密数据文件、.sql 脚本、明文密钥）
$SANDBOX_ID = "上一步返回的 sandbox_id"
$DATA_FILE = "D:\develop\trusted-compute\trusted-compute\examples\data\enterprise_dump_encrypted.bin"
$MODEL_FILE = "D:\develop\trusted-compute\trusted-compute\examples\script.sql"
$KEY_HEX = "00112233445566778899AABBCCDDEEFF"
curl.exe -X POST "http://localhost:8000/api/sandboxes/$SANDBOX_ID/import" -F "data_file=@$DATA_FILE" -F "model_file=@$MODEL_FILE" -F "key_hex=$KEY_HEX"

# 3. 销毁沙箱
curl.exe -X DELETE "http://localhost:8000/api/sandboxes/$SANDBOX_ID"
```

---

### 1. 创建 SQL 沙箱

```powershell
curl.exe -X POST "http://localhost:8000/api/sandboxes?type=sql"
```

返回示例：`{"status":0,"sandbox_id":"b2c3d4e5f6789012","error":""}`，记下 `sandbox_id`。

### 2. 导入（三参数与 Python 一致：data_file、model_file、key_hex；model_file 此处为 .sql 脚本）

```powershell
$SANDBOX_ID = "78841b8b775a4edb"
$DATA_FILE = "D:\develop\trusted-compute\trusted-compute\examples\data\enterprise_dump_encrypted.bin"
$MODEL_FILE = "D:\develop\trusted-compute\trusted-compute\examples\models\script.sql"
$KEY_HEX = "00112233445566778899AABBCCDDEEFF"

curl.exe -X POST "http://localhost:8000/api/sandboxes/$SANDBOX_ID/import" -F "data_file=@$DATA_FILE" -F "model_file=@$MODEL_FILE" -F "key_hex=$KEY_HEX"
```

成功返回：`{"status":0,"sandbox_id":"...","error":""}`。  
解密后 JSON 需含 `ddl` 和/或 `tables`（或 `data`+`table_name`），以便加载到 MariaDB 后执行 SQL。

### 3. 执行（沙箱内解密、加载到 MariaDB、执行 script.sql）

```powershell
curl.exe -X POST "http://localhost:8000/api/sandboxes/$SANDBOX_ID/run"
```

### 4. 销毁沙箱

```powershell
curl.exe -X DELETE "http://localhost:8000/api/sandboxes/$SANDBOX_ID"
```

---

## 三、仅 DB 沙箱（只建 MariaDB，用于 execute-sql）

```powershell
# 创建
curl.exe -X POST "http://localhost:8000/api/sandboxes?type=db"

# 销毁（将 SANDBOX_ID 换为实际返回值）
curl.exe -X DELETE "http://localhost:8000/api/sandboxes/$SANDBOX_ID"
```

---

## 四、一次性上传并执行（不建沙箱）

不经过创建/导入/销毁，直接传文件执行一次。

**Python：**

```powershell
curl.exe -X POST "http://localhost:8000/api/python-from-files" -F "data_file=@D:\develop\trusted-compute\trusted-compute\examples\data\enterprise_dump_encrypted.bin" -F "model_file=@D:\develop\trusted-compute\trusted-compute\examples\models\enterprise_aggregate_model.py" -F "key_hex=00112233445566778899AABBCCDDEEFF"
```

可选连库：加表单项 `-F "db_sandbox_id=已存在的DB沙箱ID"`。

---

## 五、健康检查

```powershell
curl.exe "http://localhost:8000/"
```

---

## 六、统一返回格式

- **status**：`0` 成功，`1` 失败  
- **sandbox_id**：当前沙箱 ID，失败时可能为 `null`  
- **error**：失败时的错误信息，成功时为 `""`

创建/导入/销毁均返回上述结构；**执行（run）** 成功时返回执行结果（如 `result`、`execution_time_ms`），失败时为 `status: 1` + `error`。