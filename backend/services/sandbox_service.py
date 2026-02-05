"""
数据沙箱服务：每次执行任务时启动新的 Docker 容器，任务结束后自动销毁容器（--rm）。
"""
import json
import subprocess
import time
from typing import Dict, Any

from sqlalchemy.orm import Session

from models import Task


class SandboxService:
    def __init__(self):
        self.sandbox_image = __import__("os").getenv("SANDBOX_IMAGE", "trusted-compute-sandbox")

    def execute_task(self, db: Session, task: Task, input_params: Dict[str, Any]) -> Dict[str, Any]:
        """每次任务在新容器中执行，执行完毕后容器销毁；下次任务再新建容器。"""
        start = time.time()

        payload = {
            "model_type": task.model_type,
            "model_code": task.model_code,
            "input_params": input_params,
        }
        stdin_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        try:
            proc = subprocess.run(
                [
                    "docker",
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
                "error": "Docker 不可用，请确认已挂载 Docker socket 且镜像 trusted-compute-sandbox 已构建",
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
