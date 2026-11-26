"""M6 Verification Suite - Analytical Sessions, History Persistence, Cancellation, and Streaming."""

import uuid

import pytest
from app.models.dataset import Dataset
from app.models.user import User
from app.services.cancellation_registry import cancellation_registry
from app.services.history_service import history_service
from httpx import AsyncClient


@pytest.mark.asyncio
class TestCancellationRegistry:
    """Test cooperative cancellation registry."""

    async def test_register_and_cancel(self):
        req_id = "test-req-123"
        user_id = uuid.uuid4()
        dataset_id = uuid.uuid4()

        event = await cancellation_registry.register(req_id, user_id, dataset_id)
        assert not event.is_set()
        assert not await cancellation_registry.is_cancelled(req_id)

        # Unauthorized user cancel attempt
        unauthorized_cancel = await cancellation_registry.cancel(req_id, uuid.uuid4())
        assert not unauthorized_cancel
        assert not event.is_set()

        # Authorized cancel attempt
        authorized_cancel = await cancellation_registry.cancel(req_id, user_id)
        assert authorized_cancel
        assert event.is_set()
        assert await cancellation_registry.is_cancelled(req_id)

        await cancellation_registry.unregister(req_id)
        assert not await cancellation_registry.is_cancelled(req_id)


@pytest.mark.asyncio
class TestHistoryPersistenceService:
    """Test HistoryService database operations and ownership enforcement."""

    async def test_get_or_create_and_update_session(self, db_session):
        user = User(
            id=uuid.uuid4(),
            email=f"user_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="fakehash",
            display_name="Tester",
        )
        db_session.add(user)

        dataset = Dataset(
            id=uuid.uuid4(),
            owner_id=user.id,
            name="Sales Data",
            original_filename="sales.csv",
            file_format="csv",
            file_size_bytes=1024,
            status="ready",
            storage_key=f"sales_{uuid.uuid4().hex[:6]}",
        )
        db_session.add(dataset)
        await db_session.commit()

        # Create session
        session = await history_service.get_or_create_session(
            db=db_session,
            user_id=user.id,
            dataset_id=dataset.id,
            initial_question="What is total revenue by region?",
        )
        assert session.id is not None
        assert session.title == "What is total revenue by region?"
        assert session.dataset_id == dataset.id
        assert session.user_id == user.id

        # Update title
        updated = await history_service.update_session_title(
            db=db_session,
            session_id=session.id,
            user_id=user.id,
            title="Q3 Regional Performance",
        )
        assert updated is not None
        assert updated.title == "Q3 Regional Performance"

        # List sessions
        listed = await history_service.list_sessions(
            db=db_session,
            user_id=user.id,
        )
        assert listed.total == 1
        assert listed.items[0].title == "Q3 Regional Performance"
        assert listed.items[0].dataset_name == "Sales Data"

        # Cross-user isolation: other user cannot get or delete
        other_user_id = uuid.uuid4()
        other_session = await history_service.get_session(
            db=db_session,
            session_id=session.id,
            user_id=other_user_id,
        )
        assert other_session is None

        delete_fail = await history_service.delete_session(
            db=db_session,
            session_id=session.id,
            user_id=other_user_id,
        )
        assert not delete_fail

        # Delete session authorized
        delete_success = await history_service.delete_session(
            db=db_session,
            session_id=session.id,
            user_id=user.id,
        )
        assert delete_success

        check_deleted = await history_service.get_session(
            db=db_session,
            session_id=session.id,
            user_id=user.id,
        )
        assert check_deleted is None


@pytest.mark.asyncio
class TestAnalysisSessionsAPI:
    """Test authenticated REST endpoints for sessions, runs, and cancellation."""

    async def test_session_lifecycle_api(self, client: AsyncClient, db_session):
        # 1. Register & login user
        reg_payload = {
            "email": "session_user@example.com",
            "password": "Password123!",
            "display_name": "Session Tester",
        }
        reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
        assert reg_res.status_code == 201
        user_id = uuid.UUID(reg_res.json()["id"])

        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "session_user@example.com", "password": "Password123!"},
        )
        assert login_res.status_code == 200

        dataset = Dataset(
            id=uuid.uuid4(),
            owner_id=user_id,
            name="Revenue Metrics",
            original_filename="revenue.csv",
            file_format="csv",
            file_size_bytes=2048,
            status="ready",
            storage_key=f"revenue_{uuid.uuid4().hex[:6]}",
        )
        db_session.add(dataset)
        await db_session.commit()

        # 2. Create session via POST /api/v1/sessions
        create_res = await client.post(
            "/api/v1/sessions",
            json={"dataset_id": str(dataset.id), "title": "Quarterly Analysis"},
        )
        assert create_res.status_code == 201
        session_data = create_res.json()
        session_id = session_data["id"]
        assert session_data["title"] == "Quarterly Analysis"
        assert session_data["dataset_id"] == str(dataset.id)

        # 3. List sessions via GET /api/v1/sessions
        list_res = await client.get("/api/v1/sessions")
        assert list_res.status_code == 200
        list_data = list_res.json()
        assert list_data["total"] >= 1
        assert any(s["id"] == session_id for s in list_data["items"])

        # 4. Update session via PATCH /api/v1/sessions/{session_id}
        patch_res = await client.patch(
            f"/api/v1/sessions/{session_id}",
            json={"title": "Updated Quarterly Revenue"},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["title"] == "Updated Quarterly Revenue"

        # 5. Get session details via GET /api/v1/sessions/{session_id}
        get_res = await client.get(
            f"/api/v1/sessions/{session_id}",
        )
        assert get_res.status_code == 200
        assert get_res.json()["title"] == "Updated Quarterly Revenue"

        # 6. Delete session via DELETE /api/v1/sessions/{session_id}
        del_res = await client.delete(
            f"/api/v1/sessions/{session_id}",
        )
        assert del_res.status_code == 204

        # 7. Verify 404 after deletion
        get_after_del = await client.get(
            f"/api/v1/sessions/{session_id}",
        )
        assert get_after_del.status_code == 404

    async def test_cancellation_endpoint(self, client: AsyncClient, db_session):
        reg_payload = {
            "email": "cancel_user@example.com",
            "password": "Password123!",
            "display_name": "Cancel Tester",
        }
        reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
        assert reg_res.status_code == 201
        user_id = uuid.UUID(reg_res.json()["id"])

        await client.post(
            "/api/v1/auth/login",
            json={"email": "cancel_user@example.com", "password": "Password123!"},
        )

        dataset = Dataset(
            id=uuid.uuid4(),
            owner_id=user_id,
            name="Cancel Test Data",
            original_filename="cancel.csv",
            file_format="csv",
            file_size_bytes=512,
            status="ready",
            storage_key=f"cancel_{uuid.uuid4().hex[:6]}",
        )
        db_session.add(dataset)
        await db_session.commit()

        req_id = "stream-req-cancel-1"
        await cancellation_registry.register(req_id, user_id, dataset.id)

        # Cancel endpoint
        cancel_res = await client.post(
            f"/api/v1/datasets/{dataset.id}/analysis/{req_id}/cancel",
        )
        assert cancel_res.status_code == 200
        cancel_data = cancel_res.json()
        assert cancel_data["status"] == "cancelled"

        await cancellation_registry.unregister(req_id)
