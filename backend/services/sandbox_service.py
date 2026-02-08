"""
数据沙箱服务：每次执行任务时启动新的 Docker 容器，任务结束后自动销毁容器（--rm）。
客户环境无 Docker 时可通过 SANDBOX_MODE=local 使用本地子进程执行（无隔离，仅适用于可信环境）。
"""
import json
import os
import subprocess
import sys
import time
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from models import Task

# 本地模式时 runner.py 的路径（相对于本文件：services/sandbox_service.py -> sandbox/runner.py）
_RUNNER_PATH = os.path.join(os.path.dirname(__file__), "..", "sandbox", "runner.py")


class SandboxService:
    def __init__(self):
        self.sandbox_image = os.getenv("SANDBOX_IMAGE", "trusted-compute-sandbox")
        self.sandbox_mode = os.getenv("SANDBOX_MODE", "docker").strip().lower()  # docker | local
        # 客户端可捆绑 Podman 时设 CONTAINER_RUNTIME=podman，与 docker 命令兼容
        self.container_runtime = os.getenv("CONTAINER_RUNTIME", "docker").strip().lower()  # docker | podman

    def _run_docker(self, stdin_bytes: bytes) -> subprocess.CompletedProcess:
        """使用 Docker/Podman 容器执行（需宿主机有对应运行时且挂载 socket）。"""
        return subprocess.run(
            [
                self.container_runtime,
                "run",
                "--rm",
                "--network", "none",
                "-i",
                self.sandbox_image,
            ],
            input=stdin_bytes,
            capture_output=True,
            timeout=60,
        )

    def _run_local(self, stdin_bytes: bytes) -> subprocess.CompletedProcess:
        """使用当前环境 Python 子进程执行 runner.py（无隔离，仅适用于可信环境、无 Docker 时）。"""
        runner_abs = os.path.abspath(_RUNNER_PATH)
        if not os.path.isfile(runner_abs):
            raise FileNotFoundError(f"沙箱入口脚本不存在: {runner_abs}")
        return subprocess.run(
            [sys.executable, "-u", runner_abs],
            input=stdin_bytes,
            capture_output=True,
            timeout=60,
            cwd=os.path.dirname(runner_abs),
        )

    def execute_task(self, db: Session, task: Task, input_params: Dict[str, Any]) -> Dict[str, Any]:
        """每次任务在新容器（或本地子进程）中执行，执行完毕后销毁。"""
        start = time.time()

        payload = {
            "model_type": task.model_type,
            "model_code": task.model_code,
            "input_params": input_params,
        }
        stdin_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        try:
            if self.sandbox_mode == "local":
                proc = self._run_local(stdin_bytes)
            else:
                proc = self._run_docker(stdin_bytes)
        except subprocess.TimeoutExpired:
            return {
                "type": task.model_type,
                "status": "error",
                "error": "执行超时",
                "execution_time": int(time.time() - start),
            }
        except FileNotFoundError:
            return {
                "type": task.model_type,
                "status": "error",
                "error": f"{self.container_runtime} 不可用，请确认已安装并挂载 socket 且镜像 trusted-compute-sandbox 已构建；或设置 SANDBOX_MODE=local 使用本地执行",
                "execution_time": int(time.time() - start),
            }
        except Exception as e:
            return {
                "type": task.model_type,
                "status": "error",
                "error": str(e),
                "execution_time": int(time.time() - start),
            }

        execution_time = int(time.time() - start)

        if proc.returncode != 0:
            return {
                "type": task.model_type,
                "status": "error",
                "error": (proc.stderr or proc.stdout or b"").decode("utf-8", errors="replace"),
                "execution_time": execution_time,
            }

        try:
            result = json.loads(proc.stdout.decode("utf-8"))
        except Exception as e:
            return {
                "type": task.model_type,
                "status": "error",
                "error": f"解析输出失败: {e}",
                "execution_time": execution_time,
            }

        result["execution_time"] = execution_time
        return result

    def execute_sql(
        self,
        data: list,
        sql: str,
        table_name: str = "input_data",
        columns: Optional[List] = None,
    ) -> Dict[str, Any]:
        """仅执行 SQL：将 data 插入内存表后执行 sql，直接返回结果（不落库、不加密）。"""
        start = time.time()
        input_params: Dict[str, Any] = {"data": data, "table_name": table_name}
        if columns is not None:
            input_params["columns"] = columns
        payload = {
            "model_type": "sql",
            "model_code": sql,
            "input_params": input_params,
        }
        stdin_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        try:
            if self.sandbox_mode == "local":
                proc = self._run_local(stdin_bytes)
            else:
                proc = self._run_docker(stdin_bytes)
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "执行超时"}
        except FileNotFoundError:
            return {
                "status": "error",
                "error": f"{self.container_runtime} 不可用；或设置 SANDBOX_MODE=local 使用本地执行",
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
