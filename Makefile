# =============================================================================
# AnalytIQ — Root Development Makefile
#
# Primary developer command interface for AnalytIQ monorepo.
# =============================================================================

.DEFAULT_GOAL := help
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

# -----------------------------------------------------------------------------
# Phony Targets Declaration
# -----------------------------------------------------------------------------
.PHONY: help setup setup-backend setup-frontend \
        dev-backend dev-frontend \
        db-up db-down db-status db-logs migrate migration \
        lint format format-check typecheck test test-backend test-frontend build check \
        health ready clean

# -----------------------------------------------------------------------------
# Help & Setup
# -----------------------------------------------------------------------------

## help: Display this help message with available targets
help:
	@echo "AnalytIQ — Available Make Targets:"
	@echo ""
	@echo "  Setup:"
	@echo "    make setup           Install backend and frontend dependencies"
	@echo "    make setup-backend   Install backend dependencies (uv sync --locked)"
	@echo "    make setup-frontend  Install frontend dependencies (npm ci)"
	@echo ""
	@echo "  Development:"
	@echo "    make dev-backend     Start FastAPI backend with reload on 0.0.0.0:8000"
	@echo "    make dev-frontend    Start Next.js frontend development server"
	@echo ""
	@echo "  Database (PostgreSQL 16 via Docker Compose):"
	@echo "    make db-up           Start PostgreSQL container in background"
	@echo "    make db-down         Stop PostgreSQL container (preserves data volume)"
	@echo "    make db-status       Show PostgreSQL container status and health"
	@echo "    make db-logs         Follow PostgreSQL container logs"
	@echo "    make migrate         Apply pending database migrations (alembic upgrade head)"
	@echo "    make migration NAME=\"...\"  Generate a new database migration"
	@echo ""
	@echo "  Code Quality & Testing:"
	@echo "    make lint            Run linters (Ruff check + ESLint)"
	@echo "    make format          Apply code formatting (Ruff format)"
	@echo "    make format-check    Check code formatting (Ruff format --check)"
	@echo "    make typecheck       Run type checkers (Pyright + TypeScript tsc)"
	@echo "    make test            Run all test suites (Pytest + Vitest)"
	@echo "    make test-backend    Run backend test suite (Pytest)"
	@echo "    make test-frontend   Run frontend test suite (Vitest)"
	@echo "    make build           Build frontend production package (next build)"
	@echo "    make check           Run full mandatory quality gate suite"
	@echo ""
	@echo "  API Inspection:"
	@echo "    make health          Probe GET /api/v1/health (liveness)"
	@echo "    make ready           Probe GET /api/v1/ready (readiness)"
	@echo "    make llm-status      Probe GET /api/v1/analysis/status (LLM provider)"
	@echo ""
	@echo "  Analytical Engine & Evaluation (M3):"
	@echo "    make test-analysis   Run deterministic analytical engine tests"
	@echo "    make eval-analysis   Run reusable live analytical evaluation benchmark"
	@echo ""
	@echo "  Maintenance:"
	@echo "    make clean           Remove temporary build artifacts and test caches"
	@echo ""

## setup: Install both backend and frontend dependencies
setup: setup-backend setup-frontend

## setup-backend: Synchronize backend dependencies from locked uv.lock
setup-backend:
	cd backend && uv sync --locked

## setup-frontend: Install frontend dependencies from locked package-lock.json
setup-frontend:
	cd frontend && npm ci

# -----------------------------------------------------------------------------
# Development
# -----------------------------------------------------------------------------

## dev-backend: Start FastAPI development server with hot reload
dev-backend:
	cd backend && uv run --locked uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

## dev-frontend: Start Next.js development server
dev-frontend:
	cd frontend && npm run dev

# -----------------------------------------------------------------------------
# Database Management
# -----------------------------------------------------------------------------

## db-up: Start PostgreSQL database container in background
db-up:
	docker compose up -d

## db-down: Stop PostgreSQL container while preserving persistent data volume
db-down:
	docker compose down

## db-status: Inspect PostgreSQL container status and health checks
db-status:
	docker compose ps

## db-logs: Stream PostgreSQL container logs
db-logs:
	docker compose logs -f db

## migrate: Apply all pending Alembic migrations to head
migrate:
	cd backend && uv run --locked alembic upgrade head

## migration: Generate a new Alembic migration (usage: make migration NAME="description")
migration:
	@if [ "$(origin NAME)" != "command line" ] || [ -z "$(NAME)" ]; then \
		echo "Error: Migration NAME is required as a command-line parameter." >&2; \
		echo "Usage: make migration NAME=\"create_example_table\"" >&2; \
		exit 1; \
	fi
	cd backend && uv run --locked alembic revision --autogenerate -m "$(NAME)"

# -----------------------------------------------------------------------------
# Code Quality & Testing
# -----------------------------------------------------------------------------

## lint: Run backend (Ruff) and frontend (ESLint) linters
lint:
	cd backend && uv run --locked ruff check .
	cd frontend && npm run lint

## format: Apply Ruff code formatting to backend
format:
	cd backend && uv run --locked ruff format .

## format-check: Verify backend code formatting without modifications
format-check:
	cd backend && uv run --locked ruff format --check .

## typecheck: Run Pyright (backend) and TypeScript tsc (frontend)
typecheck:
	cd backend && uv run --locked pyright
	cd frontend && npx tsc --noEmit

## test: Run backend and frontend automated test suites
test: test-backend test-frontend

## test-backend: Run backend unit and integration tests via Pytest
test-backend:
	cd backend && uv run --locked pytest

## test-frontend: Run frontend unit and component tests via Vitest
test-frontend:
	cd frontend && npm run test

## build: Verify production Next.js frontend build
build:
	cd frontend && npm run build

## check: Execute all mandatory quality gates in sequence; fail on any error
check:
	@echo "=== 1/9 Backend Lint (Ruff) ==="
	cd backend && uv run --locked ruff check .
	@echo "=== 2/9 Backend Format Check (Ruff) ==="
	cd backend && uv run --locked ruff format --check .
	@echo "=== 3/9 Backend Typecheck (Pyright) ==="
	cd backend && uv run --locked pyright
	@echo "=== 4/9 Backend Tests (Pytest) ==="
	cd backend && uv run --locked pytest
	@echo "=== 5/9 Frontend Lint (ESLint) ==="
	cd frontend && npm run lint
	@echo "=== 6/9 Frontend Format Check ==="
	cd frontend && npm run format:check
	@echo "=== 7/9 Frontend Typecheck (TypeScript) ==="
	cd frontend && npx tsc --noEmit
	@echo "=== 8/9 Frontend Tests (Vitest) ==="
	cd frontend && npm run test
	@echo "=== 9/9 Frontend Build (Next.js) ==="
	cd frontend && npm run build
	@echo ""
	@echo "All 9 quality gates PASSED successfully."

# -----------------------------------------------------------------------------
# API Inspection
# -----------------------------------------------------------------------------

## health: Query backend liveness endpoint (GET /api/v1/health)
health:
	@curl -i -sS --fail-with-body http://localhost:8000/api/v1/health

## ready: Query backend readiness endpoint (GET /api/v1/ready)
ready:
	@curl -i -sS --fail-with-body http://localhost:8000/api/v1/ready

## llm-status: Query LLM provider diagnostic endpoint (GET /api/v1/analysis/status)
llm-status:
	@curl -i -sS --fail-with-body http://localhost:8000/api/v1/analysis/status

## test-analysis: Run deterministic analytical engine tests via pytest
test-analysis:
	cd backend && uv run --locked pytest tests/test_analysis.py tests/test_analysis_api.py tests/test_llm.py

## eval-analysis: Run reusable analytical model evaluation benchmark against Ollama
eval-analysis:
	cd backend && uv run --locked python scripts/eval_benchmark.py ollama

# -----------------------------------------------------------------------------
# Maintenance
# -----------------------------------------------------------------------------

## clean: Remove build artifacts, test caches, and temporary files (preserves .venv and node_modules)
clean:
	rm -rf backend/.pytest_cache backend/.ruff_cache frontend/.next frontend/coverage
	find . -type d -name "__pycache__" -not -path "./backend/.venv/*" -exec rm -rf {} +
	find . -type f -name "*.pyc" -not -path "./backend/.venv/*" -delete
	@echo "Cleaned build caches and temporary files."
