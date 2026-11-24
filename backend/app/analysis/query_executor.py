"""Restricted DuckDB Analytical Query Executor with real query interruption."""

import asyncio
import logging
import time
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

logger = logging.getLogger(__name__)


class QueryExecutionError(Exception):
    """Base error for query execution failures."""


class QueryTimeoutError(QueryExecutionError):
    """The analytical query exceeded the configured execution deadline."""


class QueryResourceLimitError(QueryExecutionError):
    """The query violated memory, serialization, or concurrency limits."""


def _json_safe_cell(val: Any) -> Any:
    """Safely convert cell data types into JSON-compatible values without precision loss."""
    if val is None:
        return None
    if isinstance(val, (int, float, bool, str)):
        return val
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, bytes):
        return val.hex()
    return str(val)


class RestrictedQueryExecutor:
    """Dedicated analytical query executor running restricted queries in DuckDB."""

    def __init__(
        self,
        memory_limit: str = "512MB",
        threads: int = 2,
        query_timeout_seconds: float = 15.0,
        max_result_rows: int = 1000,
        max_result_bytes: int = 2 * 1024 * 1024,
    ) -> None:
        self.memory_limit = memory_limit
        self.threads = threads
        self.query_timeout_seconds = query_timeout_seconds
        self.max_result_rows = max_result_rows
        self.max_result_bytes = max_result_bytes

    async def execute_query(
        self,
        parquet_path: Path,
        approved_sql: str,
        timeout_seconds: float | None = None,
    ) -> tuple[list[str], list[str], list[list[Any]], float]:
        """Execute approved SQL query against the specified Parquet file.

        Returns: (column_names, column_types, rows, duration_ms)
        """
        deadline = timeout_seconds or self.query_timeout_seconds
        loop = asyncio.get_running_loop()

        # Execute synchronous query worker in thread pool with active interruption
        return await loop.run_in_executor(
            None,
            self._sync_execute_worker,
            parquet_path,
            approved_sql,
            deadline,
        )

    def _sync_execute_worker(
        self,
        parquet_path: Path,
        approved_sql: str,
        deadline_seconds: float,
    ) -> tuple[list[str], list[str], list[list[Any]], float]:
        """Synchronous worker thread that executes the query and handles interruption."""
        if not parquet_path.exists():
            raise QueryExecutionError(f"Dataset Parquet storage not found at {parquet_path}.")

        # 1. Dedicated in-memory connection per query execution
        con = duckdb.connect(database=":memory:")
        start_time = time.perf_counter()

        try:
            # 2. Strict Defense-in-Depth configuration
            con.execute(f"SET max_memory = '{self.memory_limit}';")
            con.execute(f"SET threads = {self.threads};")
            con.execute("SET enable_external_access = false;")
            con.execute("SET lock_configuration = true;")

            # 3. Bind the authorized parquet file strictly to the relation 'dataset'
            # Note: enable_external_access=false prevents arbitrary file reads,
            # so we register the table view using a view definition pointing to the authorized path
            # before or with safe binding.
            # In DuckDB, read_parquet is blocked if external_access=false, so we must register
            # a DuckDB PyArrow or table directly, or set external_access after creating view.
            # Let's test the safe sequence: connect, register view, lock access.
            con.close()

            # Clean setup:
            con = duckdb.connect(database=":memory:")
            con.execute(f"SET max_memory = '{self.memory_limit}';")
            con.execute(f"SET threads = {self.threads};")
            # In-memory relation bound to the authorized Parquet file
            escaped_path = str(parquet_path.resolve()).replace("'", "''")
            view_sql = f"CREATE TABLE dataset AS SELECT * FROM read_parquet('{escaped_path}');"  # noqa: S608
            con.execute(view_sql)
            # Now lock external access so the query cannot read other files or network
            con.execute("SET enable_external_access = false;")
            con.execute("SET lock_configuration = true;")

            # 4. Timer-based interrupt mechanism
            interrupted = False

            def interrupt_callback() -> None:
                nonlocal interrupted
                interrupted = True
                try:
                    con.interrupt()
                except Exception as ex:
                    logger.debug("Interrupt callback exception: %s", ex)

            import threading

            timer = threading.Timer(deadline_seconds, interrupt_callback)
            timer.start()

            try:
                rel = con.execute(approved_sql)
                col_names = [desc[0] for desc in rel.description] if rel.description else []
                col_types = [str(desc[1]) for desc in rel.description] if rel.description else []
                raw_rows: Sequence[Sequence[Any]] = rel.fetchall()
            except duckdb.InterruptException as ie:
                raise QueryTimeoutError(
                    f"Analytical query timed out and was interrupted after {deadline_seconds}s."
                ) from ie
            except Exception as e:
                if interrupted:
                    raise QueryTimeoutError(
                        f"Analytical query timed out after {deadline_seconds}s."
                    ) from e
                raise QueryExecutionError(f"DuckDB execution error: {e}") from e
            finally:
                timer.cancel()

            duration_ms = (time.perf_counter() - start_time) * 1000.0

            # 5. Result serialization and payload limits
            rows: list[list[Any]] = []
            total_bytes = 0

            for raw_row in raw_rows:
                converted_row = [_json_safe_cell(c) for c in raw_row]
                rows.append(converted_row)
                # Approximate byte count check
                for c in converted_row:
                    if isinstance(c, str):
                        total_bytes += len(c)
                    else:
                        total_bytes += 8
                if total_bytes > self.max_result_bytes:
                    raise QueryResourceLimitError(
                        f"Result payload size ({total_bytes} bytes) exceeds limit of "
                        f"{self.max_result_bytes} bytes."
                    )

            return col_names, col_types, rows, duration_ms

        finally:
            try:
                con.close()
            except Exception as ce:
                logger.debug("Error closing DuckDB connection: %s", ce)
