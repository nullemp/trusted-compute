"""
Sandbox service: run each request in a new container (docker run --rm -i <image>), stdin JSON -> stdout JSON.
"""
import json
import os
import subprocess
import time
from typing import Dict, Any, List, Optional

from .sandbox_db_lifecycle import sandbox_db_host, sandbox_db_ip, sandbox_exists


class SandboxService:
    def __init__(self):
        self.sandbox_image = os.getenv("SANDBOX_IMAGE", "trusted-compute-sandbox")
        # CONTAINER_RUNTIME=podman: use podman if in PATH, else fall back to docker (Podman socket is docker-compatible)
        requested = os.getenv("CONTAINER_RUNTIME", "docker").strip().lower()
        self.container_runtime = self._resolve_runtime(requested)

    def _resolve_runtime(self, requested: str) -> str:
        """Use requested runtime if available in PATH; otherwise fall back to docker (Podman socket is docker-compatible)."""
        import shutil
        if shutil.which(requested):
            return requested
        if requested == "podman" and shutil.which("docker"):
            return "docker"  # backend image has docker CLI; host Podman often exposes docker.sock
        return requested

    def _run_docker(
        self,
        stdin_bytes: bytes,
        *,
        use_network: bool = False,
        container_env: Optional[Dict[str, str]] = None,
    ) -> subprocess.CompletedProcess:
        """Run in Docker/Podman container (host must have runtime and socket mounted)."""
        print(f"Sandbox: starting container image={self.sandbox_image} runtime={self.container_runtime}", flush=True)
        cmd = [
            self.container_runtime,
            "run",
            "--rm",
            "-i",
            self.sandbox_image,
        ]
        if use_network:
            network = os.getenv("SANDBOX_NETWORK", "trusted-compute_default")
            cmd.extend(["--network", network])
        else:
            cmd.extend(["--network", "none"])
        if container_env:
            for k, v in container_env.items():
                cmd.extend(["-e", f"{k}={v}"])
        run_timeout = int(os.getenv("SANDBOX_RUN_TIMEOUT", "120"))
        result = subprocess.run(
            cmd,
            input=stdin_bytes,
            capture_output=True,
            timeout=run_timeout,
        )
        print(f"Sandbox: container finished exit_code={result.returncode}", flush=True)
        return result

    def _run_payload(
        self,
        payload: Dict[str, Any],
        *,
        use_network: bool = False,
        container_env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Run one payload in container: stdin JSON -> runner.py -> stdout JSON."""
        start = time.time()
        stdin_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            proc = self._run_docker(
                stdin_bytes,
                use_network=use_network,
                container_env=container_env,
            )
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "执行超时"}
        except FileNotFoundError:
            return {
                "status": "error",
                "error": f"{self.container_runtime} 不可用；请确认已安装并挂载 socket，且镜像 {self.sandbox_image} 已构建",
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

        if proc.returncode != 0:
            # #region agent log
            try:
                ts = int(time.time() * 1000)
                log_path = os.path.join(os.path.dirname(__file__), "..", "debug-0268b0.log")
                payload = {
                    "sessionId": "0268b0",
                    "id": f"log_{ts}",
                    "timestamp": ts,
                    "runId": "pre-fix",
                    "hypothesisId": "H3",
                    "location": "backend/services/sandbox_service.py:_run_payload/nonzero_exit",
                    "message": "runner container non-zero exit",
                    "data": {
                        "returncode": proc.returncode,
                        "stdout": proc.stdout.decode("utf-8", errors="replace") if isinstance(proc.stdout, bytes) else str(proc.stdout),
                        "stderr": proc.stderr.decode("utf-8", errors="replace") if isinstance(proc.stderr, bytes) else str(proc.stderr),
                    },
                }
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            except Exception:
                pass
            # #endregion
            return {
                "status": "error",
                "error": (proc.stderr or proc.stdout or b"").decode("utf-8", errors="replace"),
            }

        try:
            out = json.loads(proc.stdout.decode("utf-8"))
        except Exception as e:
            # #region agent log
            try:
                ts = int(time.time() * 1000)
                log_path = os.path.join(os.path.dirname(__file__), "..", "debug-0268b0.log")
                payload = {
                    "sessionId": "0268b0",
                    "id": f"log_{ts}",
                    "timestamp": ts,
                    "runId": "pre-fix",
                    "hypothesisId": "H4",
                    "location": "backend/services/sandbox_service.py:_run_payload/json_error",
                    "message": "failed to parse runner stdout as JSON",
                    "data": {
                        "error": str(e),
                        "stdout_sample": proc.stdout[:500].decode("utf-8", errors="replace") if isinstance(proc.stdout, bytes) else str(proc.stdout)[:500],
                    },
                }
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(payload, ensure_ascii=False) + "\n")
            except Exception:
                pass
            # #endregion
            return {"status": "error", "error": f"解析输出失败: {e}"}

        out["execution_time_ms"] = int((time.time() - start) * 1000)
        return out

    def execute_sql(
        self,
        *,
        sandbox_id: str,
        sql: str,
        ddl: Optional[str] = None,
        data: Optional[list] = None,
        table_name: str = "input_data",
        columns: Optional[List] = None,
        tables: Optional[List[Dict[str, Any]]] = None,
        cipher_b64: Optional[str] = None,
        key_hex: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        在指定沙箱的独立 MariaDB 中执行 SQL（实例隔离：每沙箱一库一卷）。
        - sandbox_id: 由 POST /api/sandboxes 创建。
        - 可选 cipher_b64 + key_hex：密文（base64），前 16 字节为 IV，在 runner 内 SM4-CBC 解密后按 JSON 的 ddl/tables/data 加载再执行 sql。
        - 可选 ddl: 先执行 DDL 建表，再按 tables 插入数据。
        - 单表: 传 data/table_name/columns；多表: 传 tables=[...]
        """
        if not sandbox_exists(sandbox_id):
            return {"status": "error", "error": f"沙箱不存在或已销毁: {sandbox_id}"}

        input_params: Dict[str, Any] = {}
        if cipher_b64 is not None and key_hex is not None:
            input_params["cipher_b64"] = cipher_b64
            input_params["key_hex"] = key_hex
        else:
            if ddl:
                input_params["ddl"] = ddl
            if tables is not None:
                input_params["tables"] = tables
            else:
                input_params["data"] = data or []
                input_params["table_name"] = table_name
                if columns is not None:
                    input_params["columns"] = columns
        # 通过 payload 传入 DB 连接。优先用容器 IP 避免 runner 与 DB 间容器名解析失败（如 Windows Podman）
        root_password = os.getenv("MARIADB_ROOT_PASSWORD", "trusted_compute_root")
        _host = sandbox_db_ip(sandbox_id) or sandbox_db_host(sandbox_id)
        input_params["_mariadb"] = {
            "host": _host,
            "port": 3306,
            "user": "root",
            "password": root_password,
        }

        payload = {
            "model_type": "sql",
            "model_code": sql,
            "input_params": input_params,
        }
        mariadb_env = {
            "MARIADB_HOST": _host,
            "MARIADB_PORT": "3306",
            "MARIADB_USER": "root",
            "MARIADB_PASSWORD": root_password,
        }
        return self._run_payload(
            payload,
            use_network=True,
            container_env=mariadb_env,
        )

    def execute_python(
        self,
        *,
        code: str,
        input_params: Optional[Dict[str, Any]] = None,
        use_network: bool = False,
        container_env: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        在沙箱内执行 Python 代码（pandas/numpy 可用）。
        当模型需要连库时，由调用方传入 use_network=True 和 container_env（如 MARIADB_*），
        并将 _mariadb 放入 input_params，与 execute_sql 一致。
        """
        payload = {
            "model_type": "python",
            "model_code": code,
            "input_params": input_params or {},
        }
        return self._run_payload(
            payload,
            use_network=use_network,
            container_env=container_env,
        )

