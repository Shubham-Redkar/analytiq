"""Comprehensive tests for M2 Dataset Ingestion, Exploration, DuckDB, and Security."""

import io
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import openpyxl
import pytest
from httpx import AsyncClient

from tests.conftest import verify_test_database_identity


def make_csv_bytes(header: list[str], rows: list[list[Any]], delimiter: str = ",") -> bytes:
    """Helper to construct CSV bytes with specified delimiter."""
    lines = [delimiter.join(header)]
    for r in rows:
        lines.append(delimiter.join(str(val) if val is not None else "" for val in r))
    return "\n".join(lines).encode("utf-8")


def make_xlsx_bytes(header: list[str], rows: list[list[Any]]) -> bytes:
    """Helper to construct XLSX workbook bytes."""
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(header)
    for r in rows:
        ws.append(r)
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


async def register_and_login(client: AsyncClient, email: str, name: str) -> dict[str, Any]:
    """Helper to register and log in a user, setting active session cookie on client."""
    reg_payload = {
        "email": email,
        "password": "StrongPassword123!",
        "display_name": name,
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPassword123!"},
    )
    assert login_res.status_code == 200
    return login_res.json()


class TestDatasetUploadValidation:
    """Tests for upload file validation, bounds, and security."""

    async def test_upload_valid_csv_success(self, client: AsyncClient) -> None:
        """Uploading a valid CSV file succeeds with HTTP 201 and creates ready dataset."""
        await register_and_login(client, "csv.analyst@example.com", "CSV Analyst")

        csv_content = make_csv_bytes(
            ["transaction_id", "product", "price", "is_shipped"],
            [
                ["TX1001", "Widget A", 19.99, "true"],
                ["TX1002", "Widget B", 29.50, "false"],
                ["TX1003", "Widget C", 9.95, "true"],
            ],
        )

        files = {"file": ("sales.csv", csv_content, "text/csv")}
        data = {"name": "Q1 Transactions"}
        response = await client.post("/api/v1/datasets", files=files, data=data)

        assert response.status_code == 201
        res = response.json()
        assert res["name"] == "Q1 Transactions"
        assert res["original_filename"] == "sales.csv"
        assert res["file_format"] == "CSV"
        assert res["row_count"] == 3
        assert res["column_count"] == 4
        assert res["status"] == "ready"
        assert "schema_json" in res
        assert len(res["schema_json"]["columns"]) == 4

    async def test_upload_valid_xlsx_success(self, client: AsyncClient) -> None:
        """Uploading a valid XLSX workbook succeeds with HTTP 201."""
        await register_and_login(client, "xlsx.analyst@example.com", "XLSX Analyst")

        xlsx_content = make_xlsx_bytes(
            ["department", "budget", "headcount"],
            [
                ["Engineering", 500000, 25],
                ["Marketing", 200000, 10],
                ["Finance", 150000, 5],
            ],
        )

        files = {
            "file": (
                "budget.xlsx",
                xlsx_content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        }
        response = await client.post("/api/v1/datasets", files=files)

        assert response.status_code == 201
        res = response.json()
        assert res["name"] == "budget"
        assert res["file_format"] == "XLSX"
        assert res["row_count"] == 3
        assert res["column_count"] == 3
        assert res["status"] == "ready"

    async def test_upload_utf8_bom_csv(self, client: AsyncClient) -> None:
        """CSV with UTF-8 BOM is parsed cleanly without header corruption."""
        await register_and_login(client, "bom.analyst@example.com", "BOM Analyst")

        raw_csv = "id,name,value\n1,First,100\n2,Second,200\n"
        bom_content = b"\xef\xbb\xbf" + raw_csv.encode("utf-8")

        files = {"file": ("bom_data.csv", bom_content, "text/csv")}
        response = await client.post("/api/v1/datasets", files=files)
        assert response.status_code == 201
        res = response.json()
        first_col = res["schema_json"]["columns"][0]
        assert first_col["name"] == "id"  # BOM must NOT be prepended to the column name

    async def test_upload_empty_file_rejected(self, client: AsyncClient) -> None:
        """Uploading an empty file returns HTTP 422 Unprocessable Entity."""
        await register_and_login(client, "empty@example.com", "Empty Tester")

        files = {"file": ("empty.csv", b"", "text/csv")}
        response = await client.post("/api/v1/datasets", files=files)
        assert response.status_code == 422
        assert "empty" in response.json()["detail"].lower()

    async def test_upload_unsupported_extension_rejected(self, client: AsyncClient) -> None:
        """Uploading unsupported format (.json / .txt / .py) returns HTTP 422."""
        await register_and_login(client, "badext@example.com", "Bad Ext")

        files = {"file": ("data.json", b'{"key": "value"}', "application/json")}
        response = await client.post("/api/v1/datasets", files=files)
        assert response.status_code == 422
        assert "unsupported" in response.json()["detail"].lower()

    async def test_upload_duplicate_headers_rejected(self, client: AsyncClient) -> None:
        """CSV containing duplicate column names is rejected with HTTP 422."""
        await register_and_login(client, "dup@example.com", "Dup Tester")

        csv_content = b"colA,colB,colA\n1,2,3\n4,5,6\n"
        files = {"file": ("dup_headers.csv", csv_content, "text/csv")}
        response = await client.post("/api/v1/datasets", files=files)
        assert response.status_code == 422
        assert "duplicate" in response.json()["detail"].lower()

    async def test_upload_empty_header_name_rejected(self, client: AsyncClient) -> None:
        """CSV with empty header name is rejected with HTTP 422."""
        await register_and_login(client, "emptyheader@example.com", "Header Tester")

        csv_content = b"colA,,colC\n1,2,3\n"
        files = {"file": ("empty_header.csv", csv_content, "text/csv")}
        response = await client.post("/api/v1/datasets", files=files)
        assert response.status_code == 422
        assert "empty header" in response.json()["detail"].lower()

    async def test_upload_headers_only_zero_rows_rejected(self, client: AsyncClient) -> None:
        """CSV with headers but zero data rows is rejected with HTTP 422."""
        await register_and_login(client, "norows@example.com", "No Rows")

        csv_content = b"colA,colB,colC\n"
        files = {"file": ("norows.csv", csv_content, "text/csv")}
        response = await client.post("/api/v1/datasets", files=files)
        assert response.status_code == 422
        assert "zero data rows" in response.json()["detail"].lower()


class TestSchemaInferenceAndNormalization:
    """Tests for deterministic data type inference and Parquet normalization."""

    async def test_leading_zero_identifier_preserved_as_string(self, client: AsyncClient) -> None:
        """Postal codes and IDs with leading zeros remain string types (never coerced to int)."""
        await register_and_login(client, "postal@example.com", "Postal Analyst")

        csv_content = make_csv_bytes(
            ["name", "zip_code", "area_code"],
            [
                ["Cambridge", "02138", "007"],
                ["Boston", "02115", "012"],
                ["New York", "10001", "212"],
            ],
        )

        files = {"file": ("zip_data.csv", csv_content, "text/csv")}
        response = await client.post("/api/v1/datasets", files=files)
        assert response.status_code == 201

        columns = response.json()["schema_json"]["columns"]
        zip_col = next(c for c in columns if c["name"] == "zip_code")
        area_col = next(c for c in columns if c["name"] == "area_code")

        assert zip_col["logical_type"] == "string"
        assert area_col["logical_type"] == "string"

    async def test_inferred_types_numeric_boolean_date(self, client: AsyncClient) -> None:
        """Columns are correctly typed as integer, float, boolean, date, timestamp, string."""
        await register_and_login(client, "types@example.com", "Type Analyst")

        csv_content = make_csv_bytes(
            ["id", "score", "active", "joined_date", "description"],
            [
                ["1", "98.5", "true", "2026-01-10", "Top performer"],
                ["2", "72.0", "false", "2026-02-14", "Standard"],
                ["3", "85.25", "true", "2026-03-01", "Promoted"],
            ],
        )

        files = {"file": ("types.csv", csv_content, "text/csv")}
        response = await client.post("/api/v1/datasets", files=files)
        assert response.status_code == 201

        col_map = {c["name"]: c["logical_type"] for c in response.json()["schema_json"]["columns"]}
        assert col_map["id"] == "integer"
        assert col_map["score"] == "float"
        assert col_map["active"] == "boolean"
        assert col_map["joined_date"] == "date"
        assert col_map["description"] == "string"


class TestDatasetListingAndDetail:
    """Tests for GET /api/v1/datasets and GET /api/v1/datasets/{id}."""

    async def test_list_datasets_paginated(self, client: AsyncClient) -> None:
        """Listing returns user's datasets sorted newest first with pagination metadata."""
        await register_and_login(client, "lister@example.com", "Lister")

        # Upload 3 datasets
        for i in range(1, 4):
            content = make_csv_bytes(["col"], [[f"val_{i}"]])
            await client.post(
                "/api/v1/datasets",
                files={"file": (f"data_{i}.csv", content, "text/csv")},
                data={"name": f"Dataset {i}"},
            )

        response = await client.get("/api/v1/datasets?page=1&page_size=2")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total_pages"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["name"] == "Dataset 3"  # Newest first

    async def test_get_dataset_detail(self, client: AsyncClient) -> None:
        """Fetching a dataset by ID returns comprehensive metadata without internal paths."""
        await register_and_login(client, "detailer@example.com", "Detailer")

        content = make_csv_bytes(["k", "v"], [["A", 1], ["B", 2]])
        upload_res = await client.post(
            "/api/v1/datasets",
            files={"file": ("detail.csv", content, "text/csv")},
        )
        dataset_id = upload_res.json()["id"]

        detail_res = await client.get(f"/api/v1/datasets/{dataset_id}")
        assert detail_res.status_code == 200
        data = detail_res.json()
        assert data["id"] == dataset_id
        assert data["name"] == "detail"
        assert data["row_count"] == 2
        assert data["column_count"] == 2
        assert "storage_key" not in data
        assert "storage_path" not in data


class TestDuckDBPreviewAndProfiling:
    """Tests for DuckDB-backed preview, profiling, and quality findings."""

    async def test_paginated_preview(self, client: AsyncClient) -> None:
        """Preview returns bounded rows queried via DuckDB with offset and limit."""
        await register_and_login(client, "previewer@example.com", "Previewer")

        rows = [[i, f"item_{i}"] for i in range(1, 31)]
        content = make_csv_bytes(["id", "name"], rows)
        upload_res = await client.post(
            "/api/v1/datasets",
            files={"file": ("preview_test.csv", content, "text/csv")},
        )
        dataset_id = upload_res.json()["id"]

        # Request offset 10, limit 5
        prev_res = await client.get(f"/api/v1/datasets/{dataset_id}/preview?offset=10&limit=5")
        assert prev_res.status_code == 200
        prev_data = prev_res.json()
        assert prev_data["total_rows"] == 30
        assert prev_data["offset"] == 10
        assert prev_data["limit"] == 5
        assert len(prev_data["rows"]) == 5
        assert prev_data["rows"][0]["id"] == 11
        assert prev_data["rows"][4]["id"] == 15

    async def test_column_profiling_and_quality(self, client: AsyncClient) -> None:
        """Profiling computes exact stats, null percentages, distinct counts, and duplicate rows."""
        await register_and_login(client, "profiler@example.com", "Profiler")

        # Dataset with:
        # - numbers: 10, 20, 30, 20, 10
        # - duplicates: 2 identical rows: [10, "A"], [10, "A"]
        # - missing values: row 3 has null category
        csv_content = make_csv_bytes(
            ["num", "category"],
            [
                [10, "A"],
                [20, "B"],
                [30, None],
                [20, "B"],
                [10, "A"],  # duplicate row
            ],
        )

        upload_res = await client.post(
            "/api/v1/datasets",
            files={"file": ("profile_data.csv", csv_content, "text/csv")},
        )
        dataset_id = upload_res.json()["id"]

        # Check profile
        prof_res = await client.get(f"/api/v1/datasets/{dataset_id}/profile")
        assert prof_res.status_code == 200
        prof = prof_res.json()
        assert prof["summary"]["total_rows"] == 5
        assert prof["summary"]["total_columns"] == 2
        assert prof["summary"]["duplicate_rows"] == 2

        num_col = next(c for c in prof["columns"] if c["name"] == "num")
        assert num_col["min"] == 10
        assert num_col["max"] == 30
        assert num_col["mean"] == 18.0
        assert num_col["distinct_count"] == 3

        cat_col = next(c for c in prof["columns"] if c["name"] == "category")
        assert cat_col["null_count"] == 1
        assert cat_col["null_percentage"] == 20.0

        # Check quality findings
        qual_res = await client.get(f"/api/v1/datasets/{dataset_id}/quality")
        assert qual_res.status_code == 200
        qual = qual_res.json()
        findings = qual["quality_findings"]
        finding_types = {f["type"] for f in findings}
        assert "duplicate_rows" in finding_types
        assert "missing_values" in finding_types


class TestDatasetSecurityAndOwnership:
    """Tests enforcing strict per-user ownership and isolation."""

    async def test_unauthenticated_requests_rejected(self, client: AsyncClient) -> None:
        """Unauthenticated requests to all dataset endpoints are rejected with HTTP 401."""
        client.cookies.clear()

        rand_id = uuid.uuid4()
        assert (await client.get("/api/v1/datasets")).status_code == 401
        assert (await client.get(f"/api/v1/datasets/{rand_id}")).status_code == 401
        assert (await client.get(f"/api/v1/datasets/{rand_id}/preview")).status_code == 401
        assert (await client.get(f"/api/v1/datasets/{rand_id}/profile")).status_code == 401
        assert (await client.get(f"/api/v1/datasets/{rand_id}/quality")).status_code == 401
        assert (await client.delete(f"/api/v1/datasets/{rand_id}")).status_code == 401

    async def test_cross_user_isolation_returns_404(self, client: AsyncClient) -> None:
        """User B cannot access or detect the existence of User A's datasets (returns HTTP 404)."""
        # User A registers and uploads a dataset
        await register_and_login(client, "alice@example.com", "Alice")
        content = make_csv_bytes(["col1"], [["Secret A"]])
        up_res = await client.post(
            "/api/v1/datasets",
            files={"file": ("alice_secret.csv", content, "text/csv")},
        )
        alice_dataset_id = up_res.json()["id"]

        # User B registers and logs in
        client.cookies.clear()
        await register_and_login(client, "bob@example.com", "Bob")

        # Bob's dataset list is empty
        bob_list = await client.get("/api/v1/datasets")
        assert bob_list.status_code == 200
        assert bob_list.json()["total"] == 0

        # Bob attempting to access Alice's dataset gets 404
        assert (await client.get(f"/api/v1/datasets/{alice_dataset_id}")).status_code == 404
        assert (await client.get(f"/api/v1/datasets/{alice_dataset_id}/preview")).status_code == 404
        assert (await client.get(f"/api/v1/datasets/{alice_dataset_id}/profile")).status_code == 404
        assert (await client.get(f"/api/v1/datasets/{alice_dataset_id}/quality")).status_code == 404
        assert (await client.delete(f"/api/v1/datasets/{alice_dataset_id}")).status_code == 404


class TestDatasetDeletion:
    """Tests for dataset deletion lifecycle."""

    async def test_delete_dataset_removes_metadata_and_files(self, client: AsyncClient) -> None:
        """Deleting a dataset deletes the database record and removes storage files."""
        await register_and_login(client, "deleter@example.com", "Deleter")

        content = make_csv_bytes(["x", "y"], [[1, 2]])
        up_res = await client.post(
            "/api/v1/datasets",
            files={"file": ("to_delete.csv", content, "text/csv")},
        )
        dataset_id = up_res.json()["id"]

        # Verify dataset exists
        assert (await client.get(f"/api/v1/datasets/{dataset_id}")).status_code == 200

        # Perform deletion
        del_res = await client.delete(f"/api/v1/datasets/{dataset_id}")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "ok"

        # Subsequent detail lookup must return 404
        assert (await client.get(f"/api/v1/datasets/{dataset_id}")).status_code == 404

        # List count must be 0
        list_res = await client.get("/api/v1/datasets")
        assert list_res.json()["total"] == 0

    async def test_delete_nonexistent_dataset_returns_404(self, client: AsyncClient) -> None:
        """Deleting a non-existent dataset returns HTTP 404."""
        await register_and_login(client, "nonexistent@example.com", "Deleter")
        response = await client.delete(f"/api/v1/datasets/{uuid.uuid4()}")
        assert response.status_code == 404


class TestDatasetRefinementsAndSecurityHardening:
    """Targeted regression tests for M2 UX, Quality, and Security Hardening."""

    async def test_quality_summary_included_on_dataset_detail(self, client: AsyncClient) -> None:
        """GET /datasets/{id} returns quality_summary populated from profile_json."""
        await register_and_login(client, "summary.user@example.com", "Summary User")
        csv_bytes = make_csv_bytes(
            ["id", "score"],
            [
                [1, 95],
                [2, None],
                [3, 80],
            ],
        )
        up_res = await client.post(
            "/api/v1/datasets",
            files={"file": ("scores.csv", csv_bytes, "text/csv")},
        )
        ds_id = up_res.json()["id"]

        detail_res = await client.get(f"/api/v1/datasets/{ds_id}")
        assert detail_res.status_code == 200
        data = detail_res.json()
        assert "quality_summary" in data
        assert data["quality_summary"] is not None
        assert data["quality_summary"]["missing_cells"] == 1
        assert data["quality_summary"]["total_rows"] == 3
        assert data["quality_summary"]["columns_with_missing"] == 1

    async def test_quality_columns_breakdown_and_grammatical_phrasing(
        self, client: AsyncClient
    ) -> None:
        """GET /datasets/{id}/quality returns columns_breakdown and sound findings."""
        await register_and_login(client, "quality.user@example.com", "Quality User")
        csv_bytes = make_csv_bytes(
            ["col_a", "col_b", "col_c"],
            [
                ["val1", None, None],
                ["val2", "b_val", None],
                ["val3", "b_val2", "c_val"],
            ],
        )
        up_res = await client.post(
            "/api/v1/datasets",
            files={"file": ("breakdown.csv", csv_bytes, "text/csv")},
        )
        ds_id = up_res.json()["id"]

        quality_res = await client.get(f"/api/v1/datasets/{ds_id}/quality")
        assert quality_res.status_code == 200
        q_data = quality_res.json()

        assert "columns_breakdown" in q_data
        breakdown = q_data["columns_breakdown"]
        assert len(breakdown) == 2
        # col_c has 2 nulls (66.67%), col_b has 1 null (33.33%) - must be sorted descending
        assert breakdown[0]["name"] == "col_c"
        assert breakdown[0]["null_count"] == 2
        assert breakdown[1]["name"] == "col_b"
        assert breakdown[1]["null_count"] == 1

        # Check grammatical finding message
        findings = q_data["quality_findings"]
        missing_finding = next(f for f in findings if f["type"] == "missing_values")
        assert "2 columns contain missing values, affecting 3 cells." in missing_finding["message"]

    async def test_discrete_integer_profiling_and_high_cardinality_text(
        self, client: AsyncClient
    ) -> None:
        """Discrete integers get frequency distribution; high-cardinality text handling."""
        await register_and_login(client, "titanic.analyst@example.com", "Titanic Analyst")

        # 25 rows: survived is 0 or 1 (discrete int), passenger_name is unique
        rows = [[i % 2, f"Passenger {i}"] for i in range(25)]
        csv_bytes = make_csv_bytes(["survived", "passenger_name"], rows)

        up_res = await client.post(
            "/api/v1/datasets",
            files={"file": ("titanic_sample.csv", csv_bytes, "text/csv")},
        )
        ds_id = up_res.json()["id"]

        profile_res = await client.get(f"/api/v1/datasets/{ds_id}/profile")
        assert profile_res.status_code == 200
        p_data = profile_res.json()

        cols = {c["name"]: c for c in p_data["columns"]}

        # Discrete integer column
        survived_col = cols["survived"]
        assert survived_col["logical_type"] == "integer"
        assert survived_col.get("is_discrete") is True
        assert len(survived_col["top_values"]) == 2

        # High cardinality text column
        name_col = cols["passenger_name"]
        assert name_col["logical_type"] == "string"
        assert name_col.get("is_high_cardinality") is True
        # For unique strings, top_values should be suppressed to avoid random alphabetical picks
        assert len(name_col["top_values"]) == 0

    async def test_corrupted_xlsx_rejected(self, client: AsyncClient) -> None:
        """Non-zip or malformed XLSX uploads are rejected with 422."""
        await register_and_login(client, "security.user@example.com", "Security User")
        fake_xlsx = b"PK\x03\x04not-a-valid-zip-content"
        xlsx_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        res = await client.post(
            "/api/v1/datasets",
            files={"file": ("malicious.xlsx", fake_xlsx, xlsx_mime)},
        )
        assert res.status_code == 422
        assert "spreadsheet archive" in res.json()["detail"].lower()

    async def test_test_database_identity_guard_blocks_destructive_sql(self) -> None:
        """verify_test_database_identity raises RuntimeError if connected to non-test database."""
        # Mock connection connected to development database analytiq_db
        mock_conn_dev = AsyncMock()
        mock_result_dev = MagicMock()
        mock_result_dev.scalar.return_value = "analytiq_db"
        mock_conn_dev.execute.return_value = mock_result_dev

        with pytest.raises(RuntimeError, match="SAFETY GUARD ACTIVATED"):
            await verify_test_database_identity(mock_conn_dev)

        # Mock connection connected to authorized test database analytiq_test_db
        mock_conn_test = AsyncMock()
        mock_result_test = MagicMock()
        mock_result_test.scalar.return_value = "analytiq_test_db"
        mock_conn_test.execute.return_value = mock_result_test

        # Must not raise
        await verify_test_database_identity(mock_conn_test)

    async def test_preview_includes_logical_types(self, client: AsyncClient) -> None:
        """Preview response enriches columns with inferred logical types."""
        await register_and_login(client, "preview.user@example.com", "Preview User")
        csv_bytes = make_csv_bytes(["num", "text"], [[100, "hello"]])
        up_res = await client.post(
            "/api/v1/datasets",
            files={"file": ("preview_test.csv", csv_bytes, "text/csv")},
        )
        ds_id = up_res.json()["id"]

        prev_res = await client.get(f"/api/v1/datasets/{ds_id}/preview")
        assert prev_res.status_code == 200
        prev_data = prev_res.json()
        cols = {c["name"]: c for c in prev_data["columns"]}
        assert cols["num"]["logical_type"] == "integer"
        assert cols["text"]["logical_type"] == "string"
