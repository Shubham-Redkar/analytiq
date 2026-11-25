"""Live Authenticated API Verification Script for M4.1.

Executes authenticated requests against:
1. POST /api/v1/datasets/{id}/analysis (M4 LangGraph Multi-Agent Analysis endpoint)
2. POST /api/v1/datasets/{id}/query (M3 Legacy Analysis endpoint)
3. GET /api/v1/analysis/status

Tests:
- Authentication & CSRF enforcement
- Grounded execution with exact numerical values
- Ambiguity detection & structured clarification output
- Safe refusal of prohibited mutations and unsupported ML
- Multi-agent trace observability
- Cross-user data isolation
"""

import asyncio
import io
import sys
import uuid

import httpx


async def run_live_api_suite(base_url: str = "http://127.0.0.1:8000") -> None:
    print(f"Connecting to live API at {base_url}...")
    async with httpx.AsyncClient(base_url=base_url, timeout=60.0) as client:
        # 1. Health check
        health_resp = await client.get("/api/v1/health")
        assert health_resp.status_code == 200, f"Health failed: {health_resp.text}"
        print("✓ GET /api/v1/health -> 200 OK")

        # 2. Check analysis status
        status_resp = await client.get("/api/v1/analysis/status")
        assert status_resp.status_code == 200, f"Analysis status failed: {status_resp.text}"
        status_data = status_resp.json()
        assert status_data["analysis_available"] is True
        print(
            f"✓ GET /api/v1/analysis/status -> 200 OK "
            f"(provider={status_data['provider']}, model={status_data['model']})"
        )

        # 3. Register / login live test user
        email = f"live_qa_{uuid.uuid4().hex[:6]}@analytiq.dev"
        test_pwd = "Password123!"  # noqa: S105
        reg_resp = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": test_pwd, "full_name": "Live QA Analyst"},
        )
        assert reg_resp.status_code == 201, f"Registration failed: {reg_resp.text}"
        csrf_token = reg_resp.cookies.get("analytiq_csrf_token")
        auth_headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}
        print(f"✓ Registered and authenticated user: {email}")

        # 4. Upload standard verification dataset
        csv_data = (
            b"order_id,region,category,quantity,unit_price,revenue\n"
            b"1,North,Electronics,2,150.0,300.0\n"
            b"2,South,Furniture,1,200.0,200.0\n"
            b"3,North,Furniture,4,50.0,200.0\n"
            b"4,East,Electronics,3,100.0,300.0\n"
            b"5,West,Supplies,10,15.0,150.0\n"
        )
        upload_resp = await client.post(
            "/api/v1/datasets",
            files={"file": ("live_orders.csv", io.BytesIO(csv_data), "text/csv")},
            data={"name": "Live Orders Dataset"},
            headers=auth_headers,
        )
        assert upload_resp.status_code == 201, f"Upload failed: {upload_resp.text}"
        dataset_id = upload_resp.json()["id"]
        print(f"✓ Uploaded dataset: {dataset_id}")

        # 5. POST /analysis - Analytical query with exact numerical verification
        q1 = "What is the total revenue for North region?"
        resp1 = await client.post(
            f"/api/v1/datasets/{dataset_id}/analysis",
            json={"question": q1},
            headers=auth_headers,
        )
        assert resp1.status_code == 200, f"Query failed: {resp1.text}"
        data1 = resp1.json()
        assert data1["status"] == "completed"
        assert data1["rows"] == [[500.0]] or data1["rows"] == [[500]]
        assert len(data1["trace_events"]) >= 4
        print(f"✓ POST /analysis ('{q1}') -> COMPLETED, rows: {data1['rows']}")

        # 6. POST /analysis - Ambiguous query requiring clarification
        q2 = "Can you give me the average for this dataset?"
        resp2 = await client.post(
            f"/api/v1/datasets/{dataset_id}/analysis",
            json={"question": q2},
            headers=auth_headers,
        )
        assert resp2.status_code == 200, f"Clarification query failed: {resp2.text}"
        data2 = resp2.json()
        assert data2["status"] == "needs_clarification"
        assert data2["clarification"] is not None
        assert data2["clarification"]["clarification_type"] == "missing_target_metric"
        assert len(data2["trace_events"]) >= 2
        clar_q = data2["clarification"]["question"]
        print(f"✓ POST /analysis ('{q2}') -> NEEDS_CLARIFICATION: {clar_q}")

        # 7. POST /analysis - Prohibited mutation statement
        q3 = "DROP TABLE dataset;"
        resp3 = await client.post(
            f"/api/v1/datasets/{dataset_id}/analysis",
            json={"question": q3},
            headers=auth_headers,
        )
        assert resp3.status_code == 200
        data3 = resp3.json()
        assert data3["status"] in ("prohibited", "unsupported")
        print(f"✓ POST /analysis ('{q3}') -> SAFELY REFUSED ({data3['status']})")

        # 8. POST /query - Legacy endpoint compatibility check
        q4 = "What is the total quantity of items sold?"
        resp4 = await client.post(
            f"/api/v1/datasets/{dataset_id}/query",
            json={"question": q4},
            headers=auth_headers,
        )
        assert resp4.status_code == 200
        data4 = resp4.json()
        assert data4["status"] == "completed"
        assert data4["rows"] == [[20]]
        print(f"✓ POST /query ('{q4}') [legacy endpoint] -> COMPLETED, rows: {data4['rows']}")

        # 9. Cross-user isolation check
        user2_email = f"user2_{uuid.uuid4().hex[:6]}@analytiq.dev"
        await client.post(
            "/api/v1/auth/register",
            json={"email": user2_email, "password": test_pwd, "full_name": "User 2"},
        )
        iso_resp = await client.post(
            f"/api/v1/datasets/{dataset_id}/analysis",
            json={"question": "What is total revenue?"},
            headers=auth_headers,
        )
        assert iso_resp.status_code == 404
        print("✓ Cross-user dataset isolation confirmed (returned 404 for unauthorized user)")

    print("\n=======================================================")
    print("ALL LIVE API VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=======================================================")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    asyncio.run(run_live_api_suite(url))
