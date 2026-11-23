"""Tests for authentication API endpoints, session management, and CSRF protection."""

from app.core.config import get_settings
from httpx import AsyncClient


class TestAuthRegistration:
    """Tests for POST /api/v1/auth/register."""

    async def test_register_success(self, client: AsyncClient) -> None:
        """User registration succeeds with valid payload."""
        payload = {
            "email": "analyst@example.com",
            "password": "StrongPassword123!",
            "display_name": "Data Analyst",
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert data["email"] == "analyst@example.com"
        assert data["display_name"] == "Data Analyst"
        assert data["is_active"] is True
        assert "password" not in data
        assert "password_hash" not in data
        assert "id" in data

    async def test_register_duplicate_email(self, client: AsyncClient) -> None:
        """Duplicate registration attempts return HTTP 409 Conflict."""
        payload = {
            "email": "duplicate@example.com",
            "password": "StrongPassword123!",
            "display_name": "First User",
        }
        res1 = await client.post("/api/v1/auth/register", json=payload)
        assert res1.status_code == 201

        # Attempt to register with uppercase variant of same email
        payload_dup = {
            "email": "DUPLICATE@example.com",
            "password": "AnotherPassword123!",
            "display_name": "Second User",
        }
        res2 = await client.post("/api/v1/auth/register", json=payload_dup)
        assert res2.status_code == 409
        assert "already exists" in res2.json()["detail"]

    async def test_register_invalid_email_format(self, client: AsyncClient) -> None:
        """Registration rejects malformed email addresses with HTTP 422."""
        payload = {
            "email": "not-an-email",
            "password": "StrongPassword123!",
            "display_name": "Bad Email",
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422

    async def test_register_short_password(self, client: AsyncClient) -> None:
        """Registration rejects passwords shorter than 8 characters."""
        payload = {
            "email": "short@example.com",
            "password": "short",
            "display_name": "Short Pass",
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422


class TestAuthLogin:
    """Tests for POST /api/v1/auth/login."""

    async def test_login_success(self, client: AsyncClient) -> None:
        """Login succeeds with valid credentials and sets HTTP-only session cookie."""
        settings = get_settings()
        reg_payload = {
            "email": "loginuser@example.com",
            "password": "Password123!",
            "display_name": "Login User",
        }
        await client.post("/api/v1/auth/register", json=reg_payload)

        login_payload = {
            "email": "loginuser@example.com",
            "password": "Password123!",
        }
        response = await client.post("/api/v1/auth/login", json=login_payload)
        assert response.status_code == 200

        data = response.json()
        assert data["email"] == "loginuser@example.com"
        assert settings.session_cookie_name in response.cookies

    async def test_login_invalid_password(self, client: AsyncClient) -> None:
        """Login returns HTTP 401 for incorrect password."""
        reg_payload = {
            "email": "wrongpass@example.com",
            "password": "CorrectPassword123!",
            "display_name": "User",
        }
        await client.post("/api/v1/auth/register", json=reg_payload)

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "wrongpass@example.com", "password": "WrongPassword!"},
        )
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    async def test_login_nonexistent_user(self, client: AsyncClient) -> None:
        """Login returns HTTP 401 for non-existent email."""
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@example.com", "password": "AnyPassword123!"},
        )
        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    async def test_login_lockout_after_max_failed_attempts(self, client: AsyncClient) -> None:
        """Account is locked (HTTP 423) after exceeding maximum failed login attempts."""
        reg_payload = {
            "email": "lockout@example.com",
            "password": "RealPassword123!",
            "display_name": "Lockout Target",
        }
        await client.post("/api/v1/auth/register", json=reg_payload)

        # 5 failed attempts
        for _ in range(5):
            res = await client.post(
                "/api/v1/auth/login",
                json={"email": "lockout@example.com", "password": "BadPassword"},
            )
            assert res.status_code == 401

        # 6th attempt must be locked
        res_locked = await client.post(
            "/api/v1/auth/login",
            json={"email": "lockout@example.com", "password": "BadPassword"},
        )
        assert res_locked.status_code == 423
        assert "locked" in res_locked.json()["detail"].lower()


class TestAuthSessionAndProfile:
    """Tests for authenticated session validation and profile retrieval."""

    async def test_get_me_with_cookie(self, client: AsyncClient) -> None:
        """Authenticated GET /api/v1/auth/me returns current user profile via cookie."""
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "me@example.com",
                "password": "Password123!",
                "display_name": "Me User",
            },
        )
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "me@example.com", "password": "Password123!"},
        )
        assert login_res.status_code == 200

        # client retains cookie automatically
        me_res = await client.get("/api/v1/auth/me")
        assert me_res.status_code == 200
        assert me_res.json()["email"] == "me@example.com"
        assert me_res.json()["display_name"] == "Me User"

    async def test_get_users_me_ownership(self, client: AsyncClient) -> None:
        """Authenticated GET /api/v1/users/me returns ownership profile."""
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "owner@example.com",
                "password": "Password123!",
                "display_name": "Owner",
            },
        )
        await client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "Password123!"},
        )

        users_me_res = await client.get("/api/v1/users/me")
        assert users_me_res.status_code == 200
        assert users_me_res.json()["email"] == "owner@example.com"

    async def test_get_me_unauthenticated(self, client: AsyncClient) -> None:
        """Unauthenticated GET /api/v1/auth/me returns HTTP 401."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401


class TestAuthLogout:
    """Tests for POST /api/v1/auth/logout."""

    async def test_logout_revokes_session(self, client: AsyncClient) -> None:
        """Logout revokes active session and invalidates subsequent requests."""
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "logout@example.com",
                "password": "Password123!",
                "display_name": "Logout User",
            },
        )
        await client.post(
            "/api/v1/auth/login",
            json={"email": "logout@example.com", "password": "Password123!"},
        )

        # Confirm session is valid
        res_me = await client.get("/api/v1/auth/me")
        assert res_me.status_code == 200

        # Perform logout
        logout_res = await client.post("/api/v1/auth/logout")
        assert logout_res.status_code == 200
        assert logout_res.json()["status"] == "ok"

        # Next /me call must be rejected
        res_after = await client.get("/api/v1/auth/me")
        assert res_after.status_code == 401


class TestCSRFProtection:
    """Tests for cross-origin state-changing CSRF defense."""

    async def test_csrf_cookie_untrusted_origin(self, client: AsyncClient) -> None:
        """State-changing request with session cookie and untrusted origin is rejected with 403."""
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "csrf@example.com",
                "password": "Password123!",
                "display_name": "CSRF User",
            },
        )
        await client.post(
            "/api/v1/auth/login",
            json={"email": "csrf@example.com", "password": "Password123!"},
        )

        # Send POST with attacker origin
        evil_res = await client.post(
            "/api/v1/auth/logout",
            headers={"origin": "http://evil-attacker.com"},
        )
        assert evil_res.status_code == 403
        assert "CSRF validation failed" in evil_res.json()["detail"]


class TestUserPersistenceAndRestart:
    """Regression tests for user persistence across restarts and test DB isolation."""

    async def test_user_persists_across_fresh_client_connections(self, client: AsyncClient) -> None:
        """A registered user remains persistent and can log in across separate client sessions."""
        email = "persisted.analyst@example.com"
        password = "SecurePassword123!"

        # Step 1: Register user
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "display_name": "Persistent Analyst"},
        )
        assert reg_res.status_code == 201

        # Step 2: Simulate service restart / fresh client session by clearing cookies
        client.cookies.clear()

        # Step 3: Log in as the existing user
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login_res.status_code == 200
        data = login_res.json()
        assert data["email"] == email
        assert data["display_name"] == "Persistent Analyst"

        # Step 4: Verify profile is accessible
        me_res = await client.get("/api/v1/auth/me")
        assert me_res.status_code == 200
        assert me_res.json()["email"] == email

    async def test_password_hash_remains_verifiable_multiple_logins(
        self, client: AsyncClient
    ) -> None:
        """Argon2id password verification succeeds consistently across repeated logins."""
        email = "multilogin@example.com"
        password = "MultiLoginPassword123!"

        reg_res = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password, "display_name": "Multi Login"},
        )
        assert reg_res.status_code == 201

        for _ in range(3):
            client.cookies.clear()
            login_res = await client.post(
                "/api/v1/auth/login",
                json={"email": email, "password": password},
            )
            assert login_res.status_code == 200
