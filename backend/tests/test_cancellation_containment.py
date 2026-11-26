"""Tests for cancellation containment and worker thread interruption in QueryExecutor."""

import asyncio
import tempfile
from pathlib import Path

import duckdb
import pytest
from app.analysis.query_executor import RestrictedQueryExecutor


@pytest.mark.asyncio
async def test_query_executor_cancellation_containment() -> None:
    executor = RestrictedQueryExecutor(memory_limit="512MB", threads=2, query_timeout_seconds=15.0)

    with tempfile.NamedTemporaryFile(suffix=".parquet") as tmp:
        con = duckdb.connect()
        con.execute("CREATE TABLE t AS SELECT range AS id FROM range(1000000);")
        con.execute(f"COPY t TO '{tmp.name}' (FORMAT PARQUET);")
        con.close()

        # Heavy query that takes a long time
        heavy_query = """
        SELECT COUNT(*)
        FROM dataset d1
        CROSS JOIN dataset d2
        WHERE d1.id = d2.id AND d1.id < 500000
        """

        task = asyncio.create_task(
            executor.execute_query(
                parquet_path=Path(tmp.name),
                approved_sql=heavy_query,
                timeout_seconds=30.0,
            )
        )

        # Allow query execution thread to spin up and connect
        await asyncio.sleep(0.05)

        # Cancel the task while in-flight
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task
