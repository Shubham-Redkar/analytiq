# AnalytIQ — Local Development Guide

This guide describes how to set up, run, test, and contribute to the **AnalytIQ** platform during local development on Windows 11 using WSL2 (Ubuntu).

---

## 1. Prerequisites

### Windows 11 & WSL2
- Windows 11 with WSL2 enabled.
- Ubuntu 22.04 LTS or 24.04 LTS distribution installed in WSL2.
- Docker Desktop for Windows with WSL2 integration enabled for your Ubuntu distribution.

### Linux-Native Working Directory
Always clone and work inside the Linux-native filesystem to avoid WSL2 9P filesystem performance overhead and file permission anomalies:
```bash
# Recommended directory
cd ~/projects/analytiq
```
Avoid developing directly under `/mnt/c/`.

### Tooling Requirements
- **GNU Make**: v4.0+ (standard in Ubuntu: `sudo apt install make` if not present)
- **Python**: 3.12+ (managed by `uv`)
- **uv**: Modern, fast Python package and project manager (v0.5+)
- **Node.js**: v20+ LTS or v22+ LTS (Node v24 supported)
- **npm**: v10+ (bundled with Node.js)
- **Git**: v2.30+
- **Docker & Docker Compose**: v2.20+
- **curl**: For health probe verification

---

## 2. Quickstart with Makefile

The root-level `Makefile` is the primary interface for local development workflows.

```bash
# 1. View all available targets and descriptions
make help

# 2. Complete project setup (backend uv sync + frontend npm ci)
make setup

# 3. Configure local environment files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local

# 4. Start local infrastructure (PostgreSQL 16)
make db-up

# 5. Run full quality gate suite
make check
```

---

## 3. Makefile Command Reference

| Command | Category | Description |
|---|---|---|
| `make help` | Help | Display all available targets with descriptions |
| `make setup` | Setup | Install all backend (`uv sync`) and frontend (`npm ci`) dependencies |
| `make setup-backend` | Setup | Install backend dependencies (`uv sync --locked`) |
| `make setup-frontend` | Setup | Install frontend dependencies (`npm ci`) |
| `make dev-backend` | Dev | Start FastAPI backend server with hot-reload on `0.0.0.0:8000` |
| `make dev-frontend` | Dev | Start Next.js frontend development server |
| `make db-up` | Database | Start PostgreSQL container in background |
| `make db-down` | Database | Stop PostgreSQL container (preserves named volume) |
| `make db-status` | Database | Show PostgreSQL container status and health check |
| `make db-logs` | Database | Follow live logs from PostgreSQL container |
| `make migrate` | Database | Apply pending Alembic migrations (`alembic upgrade head`) |
| `make migration NAME="..."` | Database | Generate new Alembic migration with autogenerate |
| `make lint` | Quality | Run backend (Ruff) and frontend (ESLint) linters |
| `make format` | Quality | Apply automatic formatting to backend (Ruff format) |
| `make format-check` | Quality | Verify backend formatting without modifying files |
| `make typecheck` | Quality | Run Pyright (backend) and TypeScript tsc (frontend) |
| `make test` | Testing | Run all tests (Pytest + Vitest) |
| `make test-backend` | Testing | Run backend tests via Pytest |
| `make test-frontend` | Testing | Run frontend tests via Vitest |
| `make build` | Build | Build production Next.js frontend package |
| `make check` | Quality | Run full 8-step mandatory quality gate suite |
| `make health` | API | Probe `GET /api/v1/health` (liveness check) |
| `make ready` | API | Probe `GET /api/v1/ready` (database readiness check) |
| `make clean` | Maintenance | Remove temporary build artifacts and test caches |

---

## 4. Backend Architecture & Management

All backend operations use `uv` exclusively. Do not use `pip`, `poetry`, or `conda`.

### Python Version Management
The backend pins Python to `3.12` via `backend/.python-version`. `uv` automatically downloads and uses the required CPython version.

### Environment Configuration
Copy the example environment configuration:
```bash
cp backend/.env.example backend/.env
```
Default configuration values:
| Variable | Default Value | Description |
|---|---|---|
| `APP_NAME` | `AnalytIQ API` | Service display name |
| `ENVIRONMENT` | `development` | Runtime environment |
| `DEBUG` | `true` | Enable debug mode and Swagger docs |
| `API_HOST` | `0.0.0.0` | Bind address for Uvicorn |
| `API_PORT` | `8000` | Port for the API server |
| `POSTGRES_HOST` | `127.0.0.1` | PostgreSQL host |
| `POSTGRES_PORT` | `5433` | PostgreSQL host port (mapped to container 5432) |
| `POSTGRES_DB` | `analytiq_db` | Application database |
| `POSTGRES_USER` | `analytiq` | Database user |
| `POSTGRES_PASSWORD` | `changeme_local_only` | Development password |
| `CORS_ORIGINS` | `["http://localhost:3000","http://127.0.0.1:3000"]` | Allowed web origins |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `SESSION_COOKIE_NAME` | `analytiq_session` | Name of the HTTP-only session cookie |
| `SESSION_EXPIRE_DAYS` | `7` | Session lifetime in days |
| `COOKIE_SECURE` | `false` | Enable Secure flag on cookies (set true in production) |
| `COOKIE_SAMESITE` | `lax` | SameSite cookie policy (`lax`, `strict`, `none`) |
| `MAX_LOGIN_ATTEMPTS` | `5` | Maximum failed attempts before account lockout |
| `LOCKOUT_DURATION_MINUTES` | `15` | Account lockout duration in minutes |

*Never commit the `.env` file to version control.*

### Starting the Backend
```bash
make dev-backend
```
- API Base URL: `http://localhost:8000`
- Interactive API Documentation (Swagger): `http://localhost:8000/api/docs`
- Alternative API Documentation (ReDoc): `http://localhost:8000/api/redoc`

---

## 5. Frontend Architecture & Management

All frontend dependencies are managed using `npm` exclusively.

### Environment Configuration
```bash
cp frontend/.env.example frontend/.env.local
```
Key configuration:
- `NEXT_PUBLIC_API_BASE_URL`: Base URL for the FastAPI backend (default: `http://localhost:8000`). Private credentials must never be prefixed with `NEXT_PUBLIC_`.

### Starting the Frontend
```bash
make dev-frontend
```
- Frontend Application: `http://localhost:3000`

---

## 6. Local Database Infrastructure (PostgreSQL 16)

PostgreSQL 16 runs in a dedicated Docker container defined in `docker-compose.yml`.

### Start PostgreSQL
```bash
make db-up
```

### Inspect Container Status & Logs
```bash
make db-status
make db-logs
```

### Database Migrations (Alembic)
Database migrations run asynchronously with SQLAlchemy 2.x and asyncpg.
```bash
# Generate a new migration (requires NAME parameter)
make migration NAME="create_initial_schema"

# Apply pending migrations
make migrate
```

Alembic automatically reads `settings.database_url` (`postgresql+asyncpg://...`) from `app.core.config.get_settings()`, ensuring credentials are never hardcoded in `alembic.ini`.

---

## 7. Health and Readiness Verification

Verify service endpoints using `make` or `curl`:

### Liveness Probe (Does not require PostgreSQL)
```bash
make health
```
Expected HTTP 200 Response:
```json
{
  "status": "ok",
  "service": "analytiq-api"
}
```

### Readiness Probe (Requires PostgreSQL)
```bash
make ready
```
- When PostgreSQL is reachable: HTTP 200 with `{"status": "ready", "checks": {"database": "ok"}}`
- When PostgreSQL is unreachable: HTTP 503 with `{"status": "not_ready", "checks": {"database": "unavailable"}}`

---

## 8. Milestone M1: Authentication & Session Architecture

Milestone M1 introduces secure user registration, authentication, opaque hashed session management, CSRF protection, and an authenticated dashboard shell.

### Security Foundations

1. **Password Hashing (Argon2id)**:
   - Implemented via `argon2-cffi`. Plaintext passwords are never logged, persisted, or returned.
   - Non-existent user logins execute dummy verification against a constant precomputed hash to prevent user enumeration through timing side channels.
2. **Opaque Session Tokens**:
   - High-entropy 32-byte tokens (`secrets.token_urlsafe(32)`) are issued upon successful login.
   - Only the SHA-256 hash of the token is stored in the PostgreSQL `sessions` table. A database leak cannot compromise active session tokens.
3. **Cookie Security**:
   - Tokens are delivered via an HTTP-only cookie (`analytiq_session`) with `SameSite=Lax` and configurable `Secure` flag (`false` in dev, `true` in production).
   - Prevents client-side script access (mitigating XSS token theft).
4. **Brute-Force & Lockout Protection**:
   - Accounts track consecutive failed login attempts.
   - Reaching 5 consecutive failures triggers an automatic 15-minute account lockout (`HTTP 423 Locked`). Successful authentication resets failed attempts.
5. **CSRF Origin Verification**:
   - State-changing requests (`POST`, `PUT`, `PATCH`, `DELETE`) carrying a session cookie must present a valid `Origin` or `Referer` matching allowed CORS origins or host.

### API Contract Reference

| Endpoint | Method | Status | Description |
|---|---|---|---|
| `/api/v1/auth/register` | `POST` | `201` | Register a new user (`email`, `password`, `display_name`) |
| `/api/v1/auth/login` | `POST` | `200` | Authenticate user, issue opaque token, set session cookie |
| `/api/v1/auth/logout` | `POST` | `200` | Revoke session in database and delete cookie |
| `/api/v1/auth/me` | `GET` | `200` | Return profile of currently authenticated user |
| `/api/v1/users/me` | `GET` | `200` | Return user profile for ownership validation |

### Frontend Experience

- **Landing Page (`/`)**: Dynamic call-to-actions based on authentication state.
- **Sign In (`/login`)**: Accessible card with email/password validation, redirect handling (`?redirect=...`), and lockout error presentation.
- **Sign Up (`/register`)**: Account creation with client validation (minimum 8 characters, password confirmation).
- **Dashboard (`/dashboard`)**: Protected route verifying session credentials with loading skeletons, user ownership card, milestone status, and live dataset counters with shortcuts to explore and upload datasets.

---

## 9. Milestone M2: Dataset Ingestion & Exploration Architecture

Milestone M2 introduces deterministic dataset ingestion, Parquet normalization, high-performance in-memory DuckDB analytical querying, data profiling, data quality findings, and user-owned dataset exploration.

### Architectural Principles

1. **Deterministic Processing ("AI plans and interprets. Deterministic tools calculate. Evidence validates. AnalytIQ explains.")**:
   - Ingestion and profiling are strictly deterministic: no probabilistic LLM calls are involved in calculating row counts, null distributions, distinct counts, or schema types.
2. **Dual-Engine Storage Design**:
   - **PostgreSQL 16**: System of record for user accounts, sessions, and dataset metadata (`datasets` table with `owner_id` FK to `users.id` with `CASCADE` deletion).
   - **Parquet Storage**: Analytical engine target stored under `storage/parquet/<dataset_id>/data.parquet`.
   - **Source Archive**: Exact uploaded binary file preserved under `storage/uploads/<dataset_id>/source.<ext>`.
3. **DuckDB Query Engine**:
   - In-memory execution pinned to configurable boundaries (`DUCKDB_MEMORY_LIMIT="512MB"`, `threads=2`).
   - Direct read of Parquet files via `SELECT ... FROM read_parquet(...)`. Fast columnar queries for paginated preview, column statistics, distinct counts, and quality metrics.
4. **Ingestion Boundaries & Safety**:
   - Maximum file size: **25 MiB** (streaming validation aborts transfers that exceed limit).
   - Maximum row count: **250,000 rows**.
   - Maximum column count: **200 columns**.
   - Path traversal prevention: UUIDv4 subdirectories and strictly validated canonical path resolution within `storage_path`.
   - Thread isolation: CPU/IO-bound parsing and DuckDB workloads run in worker threads via `asyncio.to_thread`.
5. **Deterministic Schema Inference**:
   - Analyzes non-null values with strict precedence: `integer` -> `float` -> `date` -> `timestamp` -> `boolean` -> `string`.
   - Numeric identifiers with leading zeros (e.g. `'01234'`, postal codes, IDs) are strictly classified as `string` to prevent destructive loss of leading digits.

### API Contract Reference

| Endpoint | Method | Status | Description |
|---|---|---|---|
| `/api/v1/datasets/upload` | `POST` | `201` | Upload and normalize CSV/XLSX file (`multipart/form-data`) |
| `/api/v1/datasets` | `GET` | `200` | List user-owned datasets with pagination (`page`, `page_size`) |
| `/api/v1/datasets/{id}` | `GET` | `200` | Retrieve dataset metadata and inferred schema |
| `/api/v1/datasets/{id}/preview` | `GET` | `200` | Paginated tabular row preview via DuckDB (`offset`, `limit`) |
| `/api/v1/datasets/{id}/profile` | `GET` | `200` | Comprehensive column statistics and top 5 frequent values |
| `/api/v1/datasets/{id}/quality` | `GET` | `200` | Deterministic data quality findings and alerts |
| `/api/v1/datasets/{id}` | `DELETE` | `200` | Delete dataset record and associated storage files |

### Dataset Exploration Commands via cURL

```bash
# 1. Login and obtain session cookie
curl -s -c cookies.txt -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"ValidPassword123!"}'

# 2. Upload a CSV dataset
curl -s -b cookies.txt -X POST http://localhost:8000/api/v1/datasets/upload \
  -F "file=@sample.csv" \
  -F "name=Sales Data Q1"

# 3. List datasets
curl -s -b cookies.txt http://localhost:8000/api/v1/datasets

# 4. Preview dataset rows (page 1, 20 rows)
curl -s -b cookies.txt "http://localhost:8000/api/v1/datasets/<DATASET_ID>/preview?offset=0&limit=20"

# 5. Fetch column profiling
curl -s -b cookies.txt http://localhost:8000/api/v1/datasets/<DATASET_ID>/profile

# 6. Fetch data quality findings
curl -s -b cookies.txt http://localhost:8000/api/v1/datasets/<DATASET_ID>/quality
```

### Frontend Experience

- **Datasets Management (`/datasets`)**: Paginated list of user-owned datasets with format badges, row/column counts, file sizes, creation timestamps, and safe delete confirmation modals.
- **Dataset Upload (`/datasets/upload`)**: Drag-and-drop file upload zone, client validation (25 MiB limit, `.csv` or `.xlsx` extension), optional custom dataset name, upload progress indicator, and error banners.
- **Dataset Exploration (`/datasets/[id]`)**:
  - **Overview Strip**: Key metrics (rows, columns, format, size, status, timestamp) and quick actions.
  - **Data Preview Tab**: Paginated grid powered by DuckDB, displaying distinct visual null styling (`NULL`), column types, and horizontal scroll for wide schemas.
  - **Schema Definition Tab**: Full list of columns with physical types, inferred logical types, nullable indicators, and sample values.
  - **Column Profiling Tab**: Deep statistical cards per column displaying null percentage bars, distinct counts, numeric min/mean/max, date min/max, and top 5 frequent value distributions.
  - **Data Quality Tab**: Deterministic quality findings cards (missing values, high cardinality, duplicate rows, constant columns) with severity indicators (`info`, `warning`, `critical`).

---

## 10. Quality Gates & Continuous Integration

Run the comprehensive quality gate check locally before committing changes:
```bash
make check
```
This executes all 8 mandatory checks in sequence and fails immediately on any error:
1. Backend Lint (`uv run --locked ruff check .`)
2. Backend Format Check (`uv run --locked ruff format --check .`)
3. Backend Typecheck (`uv run --locked pyright`)
4. Backend Tests (`uv run --locked pytest`)
5. Frontend Lint (`npm run lint`)
6. Frontend Typecheck (`npx tsc --noEmit`)
7. Frontend Tests (`npm run test`)
8. Frontend Production Build (`npm run build`)

GitHub Actions CI (`.github/workflows/ci.yml`) executes these identical checks against pull requests and pushes targeting `dev` and `main`.

---

## 11. Troubleshooting

### Port Conflict Configuration
AnalytIQ maps PostgreSQL to host port `5433` by default to avoid conflicts with existing PostgreSQL instances running on port `5432` in WSL2 Ubuntu. If port 5433 is also occupied:
1. In `docker-compose.yml` or via root `.env`, override `POSTGRES_PORT=5434`.
2. In `backend/.env`, set `POSTGRES_PORT=5434`.

### Docker Daemon Not Accessible in WSL2
If `docker: command not found` or `Cannot connect to the Docker daemon`:
1. Open Docker Desktop on Windows.
2. Navigate to **Settings > Resources > WSL Integration**.
3. Toggle ON integration for your Ubuntu distribution and click **Apply & Restart**.

### Lockfile Discrepancies
- Backend: Do not manually edit `uv.lock`. Run `uv lock` followed by `uv sync --locked`.
- Frontend: Do not manually edit `package-lock.json`. Run `npm install` followed by `npm ci` to verify.

---

## 12. Safe Shutdown

To stop all local processes and clean temporary caches:
1. Stop the Next.js process: `Ctrl + C` in the frontend terminal.
2. Stop the FastAPI process: `Ctrl + C` in the backend terminal.
3. Stop PostgreSQL (preserves data):
   ```bash
   make db-down
   ```
4. Clean temporary build caches (safe; does not remove `.venv`, `node_modules`, or volumes):
   ```bash
   make clean
   ```
