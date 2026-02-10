# Trusted Compute Platform

A multi-party secure computation platform: multiple data providers participate in computation tasks and get results without exposing raw data. Supports SQL and Python analysis, data masking, and result encryption.

---

## 1. What services does this project run?

This repo uses **Docker Compose** (or Podman + compose) to run three components:

| Service   | Description | Port |
|-----------|-------------|------|
| **mariadb** | Database for projects, tasks, participants, etc.; supports bulk load (LOAD DATA). | 3306 |
| **backend** | FastAPI backend: REST API, runs SQL/Python tasks, invokes sandbox, masking and encryption. | 8000 |
| **sandbox** | Used only to **build the image**; not long-running. Backend starts it with `docker run --rm` per task, then removes it for isolation. | - |

- There is no separate frontend. You use the system by **calling the backend API** or running the **client-simulator** scripts.
- Stack: Python FastAPI, MariaDB, Docker/Podman sandbox, AES-256 encryption and masking.

---

## 2. How to start

Run everything from the **project root** (the directory that contains `docker-compose.yml` and `scripts`).

### Option A: Start with scripts (recommended; auto-detects Podman/Docker)

Scripts prefer `runtime/podman` or `runtime/docker` under the project, then fall back to the system PATH. On Windows with Podman they check WSL.

- **Windows (cmd)**:`scripts\start-for-client.cmd`
- **PowerShell**:`scripts\start-for-client.ps1`
- **Linux / macOS**:`scripts/start-for-client.sh`

On first run, if images are missing you’ll see a message that they will be pulled from the network; if they already exist locally, they are used as-is.

### Option B: Docker Compose directly

If you have Docker and want to use compose from the project root:

```bash
docker-compose up -d --build
```

### Pre-pulling images (optional)

To pull base images in advance (or export them for offline use):

- Windows:`scripts\pull-images.cmd` or `scripts\pull-images.ps1`
- Linux / macOS:`scripts/pull-images.sh`

This pulls the MariaDB and Python base images and exports them under `runtime/images/*.tar` for fully offline use; the start script will load them automatically when present.

### After start

- Backend API:<http://localhost:8000>
- API docs (Swagger):<http://localhost:8000/docs>

---

## 3. How to stop

When you’re done, run the matching stop from the **project root**.

### If you started with scripts → stop with scripts

- **Windows (cmd)**:`scripts\stop-for-client.cmd`
- **PowerShell**:`scripts\stop-for-client.ps1`
- **Linux / macOS**:`scripts/stop-for-client.sh`

These run `compose down` with the same Podman/Docker setup and stop the backend and mariadb containers.

### If you started with Docker Compose → run down manually

```bash
docker compose down
# or older CLI
docker-compose down
```

To also remove volumes (wipe DB data):`docker compose down -v`.

---

## 4. How to use

### 4.1 Call the API directly

Use curl, Postman, or any HTTP client against `http://localhost:8000`. Reference:

- **Interactive docs**:open <http://localhost:8000/docs> in a browser.

Main capabilities:

- **Project management**:create projects, join projects, list participants (`/api/projects`, etc.).
- **Task management**:create tasks, execute tasks, get results (`/api/projects/{id}/tasks`, `/api/tasks/{id}/execute`, etc.).
- **Direct SQL execution (no project/task)**:  
  - Submit data + SQL:`POST /api/execute-sql`  
  - Single CSV file + SQL:`POST /api/execute-sql/file`  
  - Multiple CSVs + one SQL:`POST /api/execute-sql/files`
- **Client-style analysis (DDL + data files + SQL/Python)**:`POST /api/run-analysis` (optional DDL; import tables per config, then run SQL or Python analysis).

### 4.2 Run examples with client-simulator

The `client-simulator` directory contains example scripts that call the API.

1. Install dependencies (once):  
   `pip install -r client-simulator/requirements.txt`
2. Ensure the services are running (see section 2).
3. Run examples:
   - Single run:`python client-simulator/run_analysis_demo.py` or `python client-simulator/execute_sql_files_demo.py`
   - Or run both in one go:  
     - Windows:`client-simulator\run_tests.cmd` or `client-simulator\run_tests.ps1`  
     - Linux/macOS:`cd client-simulator && ./run_tests.sh`

The scripts wait for the API to be ready, then call `/api/run-analysis`, `/api/execute-sql/files`, etc., and print results in the console.

### 4.3 Environment variables (optional)

- `BUNDLED_RUNTIME_ROOT`:Override the runtime root (instead of project `runtime/`). See [ENV_VARS_WINDOWS.md](ENV_VARS_WINDOWS.md).
- `USE_OFFICIAL_HUB=1`:Use Docker Hub for image pull (default uses a domestic mirror).
- On Windows with Podman, if you see a WSL-related message, see [WSL_SETUP_WINDOWS.md](WSL_SETUP_WINDOWS.md).

---

## 5. Other notes

- **Performance**:Tasks run in separate containers (`docker run --rm` per run), so there is cold-start overhead (roughly 2–10 seconds per run). The sandbox image uses a multi-stage build to keep size down.
- **Client machines without Docker**:If you only need to call the API and don’t run compose, you can deploy MariaDB and the Python backend separately and set `SANDBOX_MODE=local`; see any in-repo deployment docs if present.
- This repo is a simplified implementation for understanding multi-party secure computation; for production you may want mature options such as FATE or SecretFlow.
