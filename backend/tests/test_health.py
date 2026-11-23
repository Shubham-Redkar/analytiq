"""Tests for the health and readiness endpoints."""

from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------


class TestRootEndpoint:
    """Tests for GET / (API root endpoint)."""

    async def test_root_returns_200(self, client: AsyncClient) -> None:
        """Root endpoint returns HTTP 200 OK."""
        response = await client.get("/")
        assert response.status_code == 200

    async def test_root_response_contract(self, client: AsyncClient) -> None:
        """Root endpoint returns expected metadata and operational paths."""
        response = await client.get("/")
        body = response.json()
        assert body["name"] == "AnalytIQ API"
        assert "AnalytIQ" in body["description"]
        assert body["version"] == "0.1.0"
        assert body["docs_url"] == "/docs"
        assert body["health_url"] == "/api/v1/health"
        assert body["ready_url"] == "/api/v1/ready"
        assert body["status"] == "running"

    async def test_root_independent_of_database(self, client: AsyncClient) -> None:
        """Root endpoint succeeds even when PostgreSQL is unreachable."""
        with patch(
            "app.db.session.check_database_connectivity",
            new_callable=AsyncMock,
            return_value=False,
        ):
            response = await client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "running"

    async def test_api_docs_redirect(self, client: AsyncClient) -> None:
        """Legacy /api/docs redirects to canonical /docs."""
        response = await client.get("/api/docs", follow_redirects=False)
        assert response.status_code in (307, 308)
        assert response.headers["location"] == "/docs"


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Tests for GET /api/v1/health."""

    async def test_health_returns_200(self, client: AsyncClient) -> None:
        """Health endpoint must return HTTP 200."""
        response = await client.get("/api/v1/health")
        assert response.status_code == 200

    async def test_health_response_body(self, client: AsyncClient) -> None:
        """Health endpoint must return the expected JSON contract."""
        response = await client.get("/api/v1/health")
        body = response.json()
        assert body["status"] == "ok"
        assert body["service"] == "analytiq-api"

    async def test_health_independent_of_database(self, client: AsyncClient) -> None:
        """Health endpoint must succeed even when the database is unreachable."""
        with patch(
            "app.db.session.check_database_connectivity",
            new_callable=AsyncMock,
            return_value=False,
        ):
            response = await client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Readiness endpoint
# ---------------------------------------------------------------------------


class TestReadinessEndpoint:
    """Tests for GET /api/v1/ready."""

    async def test_readiness_success_when_db_available(self, client: AsyncClient) -> None:
        """Readiness endpoint returns 200 when PostgreSQL is reachable."""
        with patch(
            "app.api.v1.health.check_database_connectivity",
            new_callable=AsyncMock,
            return_value=True,
        ):
            response = await client.get("/api/v1/ready")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert body["checks"]["database"] == "ok"

    async def test_readiness_failure_when_db_unavailable(self, client: AsyncClient) -> None:
        """Readiness endpoint returns 503 when PostgreSQL is unreachable."""
        with patch(
            "app.api.v1.health.check_database_connectivity",
            new_callable=AsyncMock,
            return_value=False,
        ):
            response = await client.get("/api/v1/ready")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "not_ready"
        assert body["checks"]["database"] == "unavailable"

    async def test_readiness_response_has_checks_key(self, client: AsyncClient) -> None:
        """Readiness response always includes a 'checks' dictionary."""
        with patch(
            "app.api.v1.health.check_database_connectivity",
            new_callable=AsyncMock,
            return_value=True,
        ):
            response = await client.get("/api/v1/ready")

        body = response.json()
        assert "checks" in body
        assert isinstance(body["checks"], dict)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestConfiguration:
    """Tests for application configuration loading."""

    def test_settings_load_successfully(self) -> None:
        """Settings must load without raising an exception."""
        from app.core.config import get_settings

        settings = get_settings()
        assert settings.app_name is not None
        assert settings.environment in ("development", "staging", "production", "test")
        assert isinstance(settings.cors_origins, list)
        assert len(settings.cors_origins) > 0

    def test_database_url_format(self) -> None:
        """database_url must use the asyncpg driver scheme."""
        from app.core.config import get_settings

        settings = get_settings()
        assert settings.database_url.startswith("postgresql+asyncpg://")

    def test_cors_origins_is_list(self) -> None:
        """CORS origins must be parsed into a list."""
        from app.core.config import Settings

        origins = ["http://localhost:3000", "http://localhost:3001"]
        s = Settings(cors_origins=origins)
        assert isinstance(s.cors_origins, list)
        assert len(s.cors_origins) == 2

    def test_cors_origins_from_comma_separated_string(self) -> None:
        """CORS origins validator parses comma-separated strings."""
        from app.core.config import Settings

        parsed = Settings.parse_cors_origins("http://localhost:3000,http://localhost:3001")
        assert parsed == ["http://localhost:3000", "http://localhost:3001"]

    def test_cors_origins_from_json_string(self) -> None:
        """CORS origins validator parses JSON array strings."""
        from app.core.config import Settings

        parsed = Settings.parse_cors_origins('["http://localhost:3000", "http://localhost:3001"]')
        assert parsed == ["http://localhost:3000", "http://localhost:3001"]
