"""
Sandbox service: run each request in a new container (docker run --rm -i <image>), stdin JSON -> stdout JSON.
"""
import json
import os
import subprocess
import time
from typing import Dict, Any, List, Optional


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

    def _run_docker(self, stdin_bytes: bytes) -> subprocess.CompletedProcess:
        """Run in Docker/Podman container (host must have runtime and socket mounted)."""
        print(f"Sandbox: starting container image={self.sandbox_image} runtime={self.container_runtime}", flush=True)
        result = subprocess.run(
            [
                self.container_runtime,
                "run",
                "--rm",
                "--network",
                "none",
                "-i",
                self.sandbox_image,
            ],
            input=stdin_bytes,
            capture_output=True,
            timeout=60,
        )
        print(f"Sandbox: container finished exit_code={result.returncode}", flush=True)
        return result

    def _run_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run one payload in container: stdin JSON -> runner.py -> stdout JSON."""
        start = time.time()
        stdin_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            proc = self._run_docker(stdin_bytes)
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
            return {
                "status": "error",
                "error": (proc.stderr or proc.stdout or b"").decode("utf-8", errors="replace"),
            }

        try:
            out = json.loads(proc.stdout.decode("utf-8"))
        except Exception as e:
            return {"status": "error", "error": f"解析输出失败: {e}"}

        out["execution_time_ms"] = int((time.time() - start) * 1000)
        return out

    def execute_sql(
        self,
        *,
        sql: str,
        data: Optional[list] = None,
        table_name: str = "input_data",
        columns: Optional[List] = None,
        tables: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        在沙箱内使用 SQLite 执行 SQL。
        - 单表: 传 data/table_name/columns
        - 多表: 传 tables=[{table_name, data, columns?}, ...]
        """
        input_params: Dict[str, Any] = {}
        if tables is not None:
            input_params["tables"] = tables
        else:
            input_params["data"] = data or []
            input_params["table_name"] = table_name
            if columns is not None:
                input_params["columns"] = columns

        payload = {
            "model_type": "sql",
            "model_code": sql,
            "input_params": input_params,
        }
        return self._run_payload(payload)

    def execute_python(self, *, code: str, input_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """在沙箱内执行 Python 代码（pandas/numpy 可用）。"""
        payload = {
            "model_type": "python",
            "model_code": code,
            "input_params": input_params or {},
        }
        return self._run_payload(payload)

