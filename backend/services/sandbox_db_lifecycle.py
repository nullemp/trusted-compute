"""
实例隔离：每个沙箱一个独立 MariaDB 容器 + 数据卷，销毁时删除容器与卷。
Python 沙箱：每个沙箱一个工作目录，用于存放导入的数据/模型/密钥，销毁时删除目录。
"""
import os
import subprocess
import time
import uuid
import shutil
from typing import Optional, Tuple

# 容器名与卷名前缀，便于过滤与清理
SANDBOX_DB_PREFIX = "tc-sandbox-db-"
SANDBOX_VOLUME_PREFIX = "tc-sandbox-data-"

# Python 沙箱工作目录根。默认放在 backend 下，这样容器挂载 ./backend:/app 时宿主机可见；
# 可通过环境变量 PYTHON_SANDBOX_WORKSPACE 覆盖（如项目根下的 workspace/python_sandboxes）。
def _python_sandbox_root() -> str:
    default = os.path.join(os.path.dirname(__file__), "..", "workspace", "python_sandboxes")
    root = os.getenv("PYTHON_SANDBOX_WORKSPACE", default)
    os.makedirs(root, exist_ok=True)
    return root


def _get_runtime() -> str:
    import shutil
    requested = os.getenv("CONTAINER_RUNTIME", "docker").strip().lower()
    if shutil.which(requested):
        return requested
    if requested == "podman" and shutil.which("docker"):
        return "docker"
    return requested


def _container_name(sandbox_id: str) -> str:
    return f"{SANDBOX_DB_PREFIX}{sandbox_id}"


def _volume_name(sandbox_id: str) -> str:
    return f"{SANDBOX_VOLUME_PREFIX}{sandbox_id}"


def _run(cmd: list, timeout: int = 60) -> Tuple[bool, str]:
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (r.stdout or "").strip() + (r.stderr or "").strip()
        return r.returncode == 0, out
    except subprocess.TimeoutExpired:
        return False, "执行超时"
    except FileNotFoundError:
        return False, f"未找到命令: {cmd[0]}"
    except Exception as e:
        return False, str(e)


def _wait_mariadb_ready(host: str, port: int, user: str, password: str, max_wait_sec: int = 45) -> bool:
    try:
        import pymysql
    except ImportError:
        time.sleep(min(15, max_wait_sec))
        return True
    deadline = time.time() + max_wait_sec
    while time.time() < deadline:
        try:
            conn = pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                connect_timeout=3,
            )
            conn.close()
            return True
        except Exception:
            time.sleep(2)
    return False


def _create_mariadb_container(sandbox_id: str) -> Tuple[bool, str]:
    """
    为给定 sandbox_id 创建 MariaDB 容器与数据卷（不生成 id）。
    返回 (成功, 错误信息)。成功时错误信息为空字符串。
    """
    container = _container_name(sandbox_id)
    volume = _volume_name(sandbox_id)
    runtime = _get_runtime()
    network = os.getenv("SANDBOX_NETWORK", "trusted-compute_default")
    root_password = os.getenv("MARIADB_ROOT_PASSWORD", "trusted_compute_root")
    image = os.getenv("MARIADB_IMAGE", "docker.io/library/mariadb:11.2")

    ok, out = _run([runtime, "volume", "create", volume], timeout=10)
    if not ok:
        return False, f"创建卷失败: {out}"

    cmd = [
        runtime,
        "run",
        "-d",
        "--name", container,
        "-v", f"{volume}:/var/lib/mysql",
        "--network", network,
        "-e", f"MARIADB_ROOT_PASSWORD={root_password}",
        "--restart", "no",
        image,
    ]
    ok, out = _run(cmd, timeout=120)
    if not ok:
        _run([runtime, "volume", "rm", volume], timeout=5)
        return False, f"启动 DB 容器失败: {out}"

    if not _wait_mariadb_ready(container, 3306, "root", root_password):
        _run([runtime, "stop", container], timeout=15)
        _run([runtime, "rm", container], timeout=10)
        _run([runtime, "volume", "rm", volume], timeout=5)
        return False, "MariaDB 启动超时"

    return True, ""


def create_sandbox() -> Tuple[Optional[str], Optional[str]]:
    """
    为沙箱启动独立 MariaDB 容器并绑定数据卷。
    返回 (sandbox_id, error_message)。成功时 error_message 为 None。
    """
    sandbox_id = uuid.uuid4().hex[:16]
    ok, err = _create_mariadb_container(sandbox_id)
    if not ok:
        return None, err
    return sandbox_id, None


def destroy_sandbox(sandbox_id: str) -> Tuple[bool, str]:
    """
    销毁沙箱：停止并删除 DB 容器，删除关联数据卷。
    返回 (成功, 错误信息)。成功时错误信息为空字符串。
    """
    container = _container_name(sandbox_id)
    volume = _volume_name(sandbox_id)
    runtime = _get_runtime()

    _run([runtime, "stop", container], timeout=15)
    ok_rm, out_rm = _run([runtime, "rm", container], timeout=10)
    if not ok_rm and "No such container" not in out_rm:
        return False, f"删除容器失败: {out_rm}"

    ok_vol, out_vol = _run([runtime, "volume", "rm", volume], timeout=10)
    if not ok_vol and "No such volume" not in out_vol:
        return False, f"删除数据卷失败: {out_vol}"

    return True, ""


def sandbox_db_host(sandbox_id: str) -> str:
    """返回该沙箱 DB 在同一网络下的主机名（即容器名）。"""
    return _container_name(sandbox_id)


def sandbox_db_ip(sandbox_id: str) -> Optional[str]:
    """
    返回该沙箱 DB 容器在 trusted-compute_default 网络下的 IP。
    若 runner 与 DB 不在同一网络或解析容器名失败，用 IP 可绕过 name resolution。
    """
    runtime = _get_runtime()
    container = _container_name(sandbox_id)
    network = os.getenv("SANDBOX_NETWORK", "trusted-compute_default")
    # 网络名含 - 时须用 index；格式: {{ (index .NetworkSettings.Networks "name").IPAddress }}
    ok, out = _run(
        [runtime, "inspect", container, "--format", f'{{{{ (index .NetworkSettings.Networks "{network}").IPAddress }}}}'],
        timeout=5,
    )
    if not ok or not out or out.strip() == "<no value>":
        return None
    return out.strip()


def sandbox_exists(sandbox_id: str) -> bool:
    """检查沙箱 DB 容器是否在运行（runner 需能连上）。"""
    runtime = _get_runtime()
    container = _container_name(sandbox_id)
    ok, out = _run([runtime, "ps", "-q", "--filter", f"name=^{container}$"], timeout=5)
    return ok and bool(out.strip())


# ---------- Python 沙箱（创建 / 导入 / 销毁） ----------

def create_python_sandbox() -> Tuple[Optional[str], Optional[str]]:
    """
    创建 Python 沙箱：分配 sandbox_id、创建工作目录，并在同一 id 下启动专属 MariaDB 容器。
    即 Python 沙箱「内部」包含一个 MariaDB，模型可通过 input_params["_mariadb"] 连库。
    返回 (sandbox_id, error_message)。成功时 error_message 为 None。
    """
    sandbox_id = uuid.uuid4().hex[:16]
    root = _python_sandbox_root()
    path = os.path.join(root, sandbox_id)
    try:
        os.makedirs(path, exist_ok=False)
    except FileExistsError:
        return None, "沙箱 ID 冲突，请重试"
    except Exception as e:
        return None, str(e)
    meta = os.path.join(path, ".type")
    try:
        with open(meta, "w", encoding="utf-8") as f:
            f.write("python")
    except Exception as e:
        shutil.rmtree(path, ignore_errors=True)
        return None, str(e)

    ok, err = _create_mariadb_container(sandbox_id)
    if not ok:
        shutil.rmtree(path, ignore_errors=True)
        return None, err

    return sandbox_id, None


def python_sandbox_exists(sandbox_id: str) -> bool:
    """检查 Python 沙箱是否存在（工作目录存在且为 python 类型）。"""
    root = _python_sandbox_root()
    path = os.path.join(root, sandbox_id)
    return os.path.isdir(path) and os.path.isfile(os.path.join(path, ".type"))


def get_python_sandbox_dir(sandbox_id: str) -> Optional[str]:
    """返回 Python 沙箱工作目录路径；若不存在则返回 None。"""
    if not python_sandbox_exists(sandbox_id):
        return None
    return os.path.join(_python_sandbox_root(), sandbox_id)


def import_python_sandbox(
    sandbox_id: str,
    data_content: bytes,
    model_content: str,
    key_hex: str,
) -> Tuple[bool, str]:
    """
    向 Python 沙箱导入：将数据文件、模型脚本、密钥写入沙箱工作目录。
    返回 (成功, 错误信息)。
    """
    path = get_python_sandbox_dir(sandbox_id)
    if not path:
        return False, "沙箱不存在或已销毁"
    try:
        with open(os.path.join(path, "data.bin"), "wb") as f:
            f.write(data_content)
        with open(os.path.join(path, "model.py"), "w", encoding="utf-8") as f:
            f.write(model_content)
        with open(os.path.join(path, "key_hex.txt"), "w", encoding="utf-8") as f:
            f.write(key_hex.strip())
        return True, ""
    except Exception as e:
        return False, str(e)


def destroy_python_sandbox(sandbox_id: str) -> Tuple[bool, str]:
    """
    销毁 Python 沙箱：先删除该沙箱专属的 MariaDB 容器与卷，再删除工作目录。
    返回 (成功, 错误信息)。
    """
    root = _python_sandbox_root()
    path = os.path.join(root, sandbox_id)
    if not os.path.isdir(path):
        return False, "沙箱不存在或已销毁"
    type_file = os.path.join(path, ".type")
    if not os.path.isfile(type_file):
        return False, "非 Python 沙箱或目录已损坏"

    # 先销毁同 id 的 MariaDB 容器与卷（Python 沙箱创建时一并创建）
    destroy_sandbox(sandbox_id)

    try:
        shutil.rmtree(path)
        return True, ""
    except Exception as e:
        return False, str(e)


# ---------- SQL 沙箱（创建 / 导入 / 销毁，与 Python 沙箱同构） ----------

def create_sql_sandbox() -> Tuple[Optional[str], Optional[str]]:
    """
    创建 SQL 沙箱：分配 sandbox_id、创建工作目录，并在同一 id 下启动专属 MariaDB 容器。
    导入 SQL 脚本后可通过 run 在该库内执行。
    返回 (sandbox_id, error_message)。成功时 error_message 为 None。
    """
    sandbox_id = uuid.uuid4().hex[:16]
    root = _python_sandbox_root()
    path = os.path.join(root, sandbox_id)
    try:
        os.makedirs(path, exist_ok=False)
    except FileExistsError:
        return None, "沙箱 ID 冲突，请重试"
    except Exception as e:
        return None, str(e)
    meta = os.path.join(path, ".type")
    try:
        with open(meta, "w", encoding="utf-8") as f:
            f.write("sql")
    except Exception as e:
        shutil.rmtree(path, ignore_errors=True)
        return None, str(e)

    ok, err = _create_mariadb_container(sandbox_id)
    if not ok:
        shutil.rmtree(path, ignore_errors=True)
        return None, err

    return sandbox_id, None


def sql_sandbox_exists(sandbox_id: str) -> bool:
    """检查 SQL 沙箱是否存在（工作目录存在且 .type 为 sql）。"""
    root = _python_sandbox_root()
    path = os.path.join(root, sandbox_id)
    if not os.path.isdir(path):
        return False
    type_path = os.path.join(path, ".type")
    try:
        with open(type_path, "r", encoding="utf-8") as f:
            return f.read().strip() == "sql"
    except Exception:
        return False


def get_sql_sandbox_dir(sandbox_id: str) -> Optional[str]:
    """返回 SQL 沙箱工作目录路径；若不存在则返回 None。"""
    if not sql_sandbox_exists(sandbox_id):
        return None
    return os.path.join(_python_sandbox_root(), sandbox_id)


def import_sql_sandbox(
    sandbox_id: str,
    data_content: bytes,
    sql_content: str,
    key_hex: str,
) -> Tuple[bool, str]:
    """
    向 SQL 沙箱导入：加密数据文件（前 16 字节为 IV）、SQL 计算模型脚本、明文密钥，
    写入沙箱工作目录（data.bin、script.sql、key_hex.txt）。
    返回 (成功, 错误信息)。
    """
    path = get_sql_sandbox_dir(sandbox_id)
    if not path:
        return False, "沙箱不存在或已销毁"
    try:
        with open(os.path.join(path, "data.bin"), "wb") as f:
            f.write(data_content)
            f.flush()
            if hasattr(os, "fsync"):
                try:
                    os.fsync(f.fileno())
                except (AttributeError, OSError):
                    pass
        script_path = os.path.join(path, "script.sql")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(sql_content)
            f.flush()
            if hasattr(os, "fsync"):
                try:
                    os.fsync(f.fileno())
                except (AttributeError, OSError):
                    pass
        # 同时写入 model.py，与 Python 沙箱一致（表单均为 model_file），run 时 script.sql 优先
        with open(os.path.join(path, "model.py"), "w", encoding="utf-8") as f:
            f.write(sql_content)
            f.flush()
            if hasattr(os, "fsync"):
                try:
                    os.fsync(f.fileno())
                except (AttributeError, OSError):
                    pass
        with open(os.path.join(path, "key_hex.txt"), "w", encoding="utf-8") as f:
            f.write(key_hex.strip())
            f.flush()
            if hasattr(os, "fsync"):
                try:
                    os.fsync(f.fileno())
                except (AttributeError, OSError):
                    pass
        return True, ""
    except Exception as e:
        return False, str(e)


def destroy_sql_sandbox(sandbox_id: str) -> Tuple[bool, str]:
    """
    销毁 SQL 沙箱：先删除该沙箱专属的 MariaDB 容器与卷，再删除工作目录。
    返回 (成功, 错误信息)。
    """
    root = _python_sandbox_root()
    path = os.path.join(root, sandbox_id)
    if not os.path.isdir(path):
        return False, "沙箱不存在或已销毁"
    type_file = os.path.join(path, ".type")
    try:
        with open(type_file, "r", encoding="utf-8") as f:
            if f.read().strip() != "sql":
                return False, "非 SQL 沙箱或目录已损坏"
    except Exception:
        return False, "非 SQL 沙箱或目录已损坏"

    destroy_sandbox(sandbox_id)
    try:
        shutil.rmtree(path)
        return True, ""
    except Exception as e:
        return False, str(e)
