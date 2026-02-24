"""
实例隔离：每个沙箱一个独立 MariaDB 容器 + 数据卷，销毁时删除容器与卷。
"""
import os
import subprocess
import time
import uuid
from typing import Optional, Tuple

# 容器名与卷名前缀，便于过滤与清理
SANDBOX_DB_PREFIX = "tc-sandbox-db-"
SANDBOX_VOLUME_PREFIX = "tc-sandbox-data-"


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


def create_sandbox() -> Tuple[Optional[str], Optional[str]]:
    """
    为沙箱启动独立 MariaDB 容器并绑定数据卷。
    返回 (sandbox_id, error_message)。成功时 error_message 为 None。
    """
    sandbox_id = uuid.uuid4().hex[:16]
    container = _container_name(sandbox_id)
    volume = _volume_name(sandbox_id)
    runtime = _get_runtime()
    network = os.getenv("SANDBOX_NETWORK", "trusted-compute_default")
    root_password = os.getenv("MARIADB_ROOT_PASSWORD", "trusted_compute_root")
    image = os.getenv("MARIADB_IMAGE", "docker.io/library/mariadb:11.2")

    # 先创建卷（显式创建便于 destroy 时精确删除）
    ok, out = _run([runtime, "volume", "create", volume], timeout=10)
    if not ok:
        return None, f"创建卷失败: {out}"

    # 启动容器：数据目录绑定到该卷
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
        return None, f"启动 DB 容器失败: {out}"

    # 等待 MariaDB 就绪（同一网络下 host 为容器名）
    if not _wait_mariadb_ready(container, 3306, "root", root_password):
        _run([runtime, "stop", container], timeout=15)
        _run([runtime, "rm", container], timeout=10)
        _run([runtime, "volume", "rm", volume], timeout=5)
        return None, "MariaDB 启动超时"

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
