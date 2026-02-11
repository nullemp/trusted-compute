# Database setup and known issues

This document summarizes how the backend uses MariaDB and how to fix common database-related errors when running the client-simulator or calling the API.

---

## 1. Overview

- **Database**: MariaDB (container `trusted-compute-db`).
- **App user**: `trusted_compute` / `trusted_compute_pass` (see `docker-compose.yml`).
- **Default database**: `trusted_compute_db` (used for app metadata and for execute-sql flows).
- **Connection URL**: Set via `DATABASE_URL`; backend uses it in `backend/database.py`.

Two API flows use the database in different ways:

| Flow                          | API                             | Creates DB? | Tables                                                     | Notes                                                             |
| ----------------------------- | ------------------------------- | ----------- | ---------------------------------------------------------- | ----------------------------------------------------------------- |
| **Run analysis**        | `POST /api/run-analysis`      | Yes         | Permanent in a**per-job database** `tc_job_<uuid>` | Needs `CREATE` (and use of that DB) for `trusted_compute`.    |
| **Execute SQL (files)** | `POST /api/execute-sql/files` | No          | **Temporary** in default DB                          | Needs a**selected database** (default or explicit `USE`). |

---

## 2. Run-analysis: per-job database and CREATE permission

### What happens

- Each `POST /api/run-analysis` creates a **new database** named `tc_job_<16 hex chars>`.
- Code: `backend/services/run_analysis_service.py` (around line 156):
  - `cursor.execute(f"CREATE DATABASE `{job_db}`")`
  - `cursor.execute(f"USE `{job_db}`")`
- Then it runs DDL, imports files, runs SQL or Python, and later drops the job DB.

### Why it can fail

- By default, the MariaDB image grants `trusted_compute` only rights on `trusted_compute_db`, **not** `CREATE` on the server.
- You get:
  `(1044, "Access denied for user 'trusted_compute'@'%' to database 'tc_job_...'")`

### Fix: grant CREATE (and recommended: full privileges) to `trusted_compute`

**Option A – New installs (recommended)**An init script runs when the MariaDB data directory is first created:

- **File**: `backend/mariadb-init/02-grant-create.sql`
- **Mounted in**: `docker-compose.yml` → `mariadb` service → `/docker-entrypoint-initdb.d/02-grant-create.sql`
- **Content**: `GRANT CREATE ON *.* TO 'trusted_compute'@'%'; FLUSH PRIVILEGES;`

So **new** `docker compose up` (with an empty volume) will have the right permissions.

**Option B – Existing data (already have a running MariaDB volume)**
Init scripts run only on first init. If the volume already exists, run once:

```bash
docker exec -it trusted-compute-db mariadb -u root -proot_pass -e "GRANT CREATE ON *.* TO 'trusted_compute'@'%'; FLUSH PRIVILEGES;"
```

If problems persist (e.g. still “Access denied” to `tc_job_*`), grant full privileges and restart the backend:

```bash
docker exec -it trusted-compute-db mariadb -u root -proot_pass -e "GRANT ALL PRIVILEGES ON *.* TO 'trusted_compute'@'%'; FLUSH PRIVILEGES;"
docker restart trusted-compute-backend
```

(Use `podman` instead of `docker` if you use Podman.)

---

## 3. Execute-sql/files: “No database selected”

### What happens

- `POST /api/execute-sql/files` does **not** create a database.
- It uses the **default database** from `DATABASE_URL` (e.g. `trusted_compute_db`) and creates **temporary tables** there, then runs the user SQL.
- Code: `backend/services/execute_sql_service.py` → `execute_sql_from_files` (and related paths).

### Why it can fail

- In some environments, the connection from the app may not have a default database selected.
- Creating a temporary table without a selected database causes:
  `(1046, 'No database selected')`

### Fix: explicit USE in backend

The backend was updated to **always select the database** from the connection URL before creating temporary tables:

- **File**: `backend/services/execute_sql_service.py`
- **Change**: After opening the connection and cursor, run:
  - `db_name = getattr(engine.url, "database", None)`
  - If `db_name` is set: `cursor.execute(f"USE `{db_name}`")`
- **Applied in**: `execute_sql_from_files`, `execute_sql_from_file`, and `execute_sql_mariadb`.

No manual DB or permission change is required; ensure the backend is running the updated code (restart if not using `--reload`).

---

## 4. Quick reference

| Symptom                                        | Cause                                                  | Fix                                                                                                                                                                                                        |
| ---------------------------------------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Access denied ... to database 'tc_job_...'` | `trusted_compute` cannot create or use job DBs       | Grant CREATE (or ALL) to `trusted_compute`; for new installs use `backend/mariadb-init/02-grant-create.sql`; for existing installs run the `docker exec ... GRANT` above. Restart backend if needed. |
| `No database selected` (1046)                | Connection has no default DB when creating temp tables | Backend now runs `USE <db>` from URL; deploy updated `execute_sql_service.py` and restart backend.                                                                                                     |
| Init script not running                        | MariaDB init runs only when data dir is**empty** | Either use a new volume (`docker compose down -v` then `up`) or apply the GRANT manually (Option B above).                                                                                             |

---

## 5. Files involved

- **backend/database.py** – `DATABASE_URL`, engine.
- **backend/services/run_analysis_service.py** – Creates `tc_job_*` DB, runs DDL/import/SQL.
- **backend/services/execute_sql_service.py** – Uses default DB, creates temp tables, runs `USE` when needed.
- **backend/mariadb-init/02-grant-create.sql** – Grants CREATE to `trusted_compute` on first init.
- **docker-compose.yml** – MariaDB env (`MARIADB_USER`, `MARIADB_DATABASE`, etc.) and init script mount.
