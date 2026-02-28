# 加解密与测试脚本总结（供后续对话参考）

## 1. 整体约定

- **算法**：SM4-CBC + PKCS7 填充（块大小 16 字节）。
- **密文文件格式**：`[前 16 字节 IV] + [SM4-CBC 密文]`。IV 不单独传参，解密时从数据前 16 字节读取。
- **密钥**：16 字节，脚本侧用 32 个十六进制字符（key_hex）表示；仅传 `key_hex`，不传 IV。

---

## 2. 加密侧（生成密文文件）

| 项目 | 说明 |
|------|------|
| **脚本** | `examples/gen_enterprise_dump_encrypted_sm4_cbc.py` |
| **输入** | 默认 `examples/data/enterprise_dump.json` |
| **输出** | 默认 `examples/data/enterprise_dump_encrypted.bin`（格式：16 字节 IV + 密文） |
| **测试用写死** | 脚本内常量：`TEST_KEY_HEX = "00112233445566778899AABBCCDDEEFF"`，`TEST_IV_HEX = "0102030405060708090A0B0C0D0E0F10"`。不传 `--key-hex` 时用固定 key，IV 固定用上述值。 |
| **核心逻辑** | `_pkcs7_pad` → `sm4_cbc_encrypt(key, iv, padded)` → 写文件 `iv + cipher`。轮密钥由 `sm4_key_schedule(key)` 生成（与 C 版 sm4 一致）。 |

---

## 3. 解密侧（沙箱内）

| 项目 | 说明 |
|------|------|
| **位置** | `backend/sandbox/runner.py`，全部为纯 Python，无 C 依赖。 |
| **入口** | `run_python()` 开头调用 `_maybe_decrypt_sm4_from_input_params(input_params)`；若存在 `cipher_b64` + `key_hex`，则先解密再执行模型。 |
| **解密流程** | `_maybe_decrypt_sm4_from_input_params`：base64 解码 → 前 16 字节为 IV、其余为密文 → `_sm4_cbc_decrypt_py(key, iv, cipher)` → JSON 解析 → 将 `payload["data"]` 写入 `input_params["data"]`。 |
| **一次性解密** | `_sm4_cbc_decrypt_py(key, iv, data)`：内部用 `_Sm4CbcDecryptCtx(key, iv)`，`update(data)` + `final()`，返回去 PKCS7 后的明文。 |
| **流式 ctx** | `_Sm4CbcDecryptCtx`：含 `update(data)`（按块解密并缓冲未满 16 字节）、`final()`（处理剩余块并做 PKCS7 校验与去填充）。轮密钥由 `_sm4_key_schedule(key)` 生成，与 C 版一致。 |
| **PKCS7** | `_unpad_pkcs7(data, block_size=16)`：要求 `len(data) % 16 == 0`，校验最后一字节为填充长度并去掉尾部填充。 |
| **SM4 底层** | `_SBOX_TABLE`、`_FK`、`_CK`，以及 `_sm4_key_schedule`、`_sm4_encrypt_block`、`_sm4_decrypt_block`（解密轮密钥顺序反向），与 C 版 sm4.c 算法一致。 |

---

## 4. 接口与调用链

| 环节 | 说明 |
|------|------|
| **客户端测试脚本** | `examples/run_python_from_files.py`。必参：`--data`（密文文件路径）、`--key`（32 位 hex）；可选 `--model`，默认 `examples/models/enterprise_aggregate_model.py`。 |
| **请求** | POST `/api/python-from-files`：表单 `data_file`（密文二进制）、`model_file`（Python 模型）、`key_hex`（无 `iv_hex`）。 |
| **后端** | `backend/main.py`：若提供 `key_hex`，则将 `data_file` 整份读入并 base64 为 `cipher_b64`，与 `key_hex` 一并放入 `input_params` 传给沙箱。 |
| **沙箱** | `runner.py` 根据 `cipher_b64` + `key_hex` 在沙箱内解密，得到 JSON，再执行 `enterprise_aggregate_model.py`；模型只看到已解密的 `input_params["data"]`。 |

---

## 5. 测试命令（Windows PowerShell，项目根目录）

```powershell
# 1. 生成密文（使用写死的 TEST_KEY_HEX、TEST_IV_HEX）
python examples\gen_enterprise_dump_encrypted_sm4_cbc.py

# 2. 调用解密并执行模型（需先启动后端，如 scripts\start-for-client.ps1）
python examples\run_python_from_files.py --data examples\data\enterprise_dump_encrypted.bin --model examples\models\enterprise_aggregate_model.py --key 00112233445566778899AABBCCDDEEFF
```

- 后端默认：`http://localhost:8000`，可通过环境变量 `TRUSTED_COMPUTE_API` 修改。
- 模型脚本只做业务计算，不包含加解密逻辑；加解密仅在 runner 与生成脚本中。

---

## 6. 相关文件一览

| 文件 | 作用 |
|------|------|
| `examples/gen_enterprise_dump_encrypted_sm4_cbc.py` | 加密：读 JSON → PKCS7 + SM4-CBC 加密 → 写 IV+密文。 |
| `examples/run_python_from_files.py` | 客户端：上传密文文件 + key_hex，调用 /api/python-from-files，打印结果。 |
| `examples/models/enterprise_aggregate_model.py` | 业务模型：仅使用 `input_params["data"]` 做聚合，与加解密无关。 |
| `backend/main.py` | 接收 data_file、model_file、key_hex；有 key_hex 时传 cipher_b64 + key_hex 给沙箱。 |
| `backend/sandbox/runner.py` | 沙箱入口：SM4-CBC 解密（含流式 ctx、PKCS7）、JSON 解析，再 exec 模型代码。 |
| `backend/sandbox/Dockerfile` | 沙箱镜像：仅 Python 依赖，无 C/crypto 目录。 |

---

## 7. 轮密钥与明文密钥关系

- 用户传入的 **key_hex**（32 个十六进制字符）= 16 字节明文密钥。
- **32 个轮密钥** 由 `_sm4_key_schedule(key)` / `sm4_key_schedule(key)` 从该 16 字节密钥推导，与 C 版 sm4 的 key schedule 一致；同一 key 得到相同 32 个轮密钥。
