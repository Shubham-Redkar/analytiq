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
    ) -> tuple[list[str], list[str], list[list[Any]], float, bool]:
        """Execute approved SQL query against the specified Parquet file.

        Returns: (column_names, column_types, rows, duration_ms, truncated)
        """
        deadline = timeout_seconds or self.query_timeout_seconds
        loop = asyncio.get_running_loop()

        # Shared reference to allow async cancellation to interrupt synchronous DuckDB execution
        con_holder: list[duckdb.DuckDBPyConnection | None] = [None]

        def _run_worker() -> tuple[list[str], list[str], list[list[Any]], float, bool]:
            return self._sync_execute_worker(
                parquet_path,
                approved_sql,
                deadline,
                con_holder,
            )

        worker_future = loop.run_in_executor(None, _run_worker)
        try:
            return await asyncio.shield(worker_future)
        except asyncio.CancelledError:
            # Active cancellation from asyncio task: trigger DuckDB connection interrupt immediately
            con = con_holder[0]
            if con is not None:
                try:
                    con.interrupt()
                except Exception as ex:
                    logger.debug("Failed to interrupt DuckDB connection upon cancellation: %s", ex)
            # Await worker termination so background thread does not outlive task or leak
            try:
                await worker_future
            except Exception:  # noqa: S110
                pass
            raise

    def _sync_execute_worker(
        self,
        parquet_path: Path,
        approved_sql: str,
        deadline_seconds: float,
        con_holder: list[duckdb.DuckDBPyConnection | None] | None = None,
    ) -> tuple[list[str], list[str], list[list[Any]], float, bool]:
        """Synchronous worker thread that executes the query and handles interruption."""
        if not parquet_path.exists():
            raise QueryExecutionError(f"Dataset Parquet storage not found at {parquet_path}.")

        # 1. Dedicated in-memory connection per query execution
        con = duckdb.connect(database=":memory:")
        if con_holder is not None:
            con_holder[0] = con
        start_time = time.perf_counter()

        # 2. Timer-based interrupt mechanism covering the entire execution lifecycle
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
            # 4. Execute approved analytical query
            try:
                # 3. Strict Defense-in-Depth configuration & Table materialization
                con.execute(f"SET max_memory = '{self.memory_limit}';")
                con.execute(f"SET threads = {self.threads};")

                escaped_path = str(parquet_path.resolve()).replace("'", "''")
                view_sql = f"CREATE TABLE dataset AS SELECT * FROM read_parquet('{escaped_path}');"  # noqa: S608
                con.execute(view_sql)

                # Lock external access so the query cannot read other files or network
                con.execute("SET enable_external_access = false;")
                con.execute("SET lock_configuration = true;")

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

            duration_ms = (time.perf_counter() - start_time) * 1000.0

            # 5. Result serialization, N+1 truncation handling, and payload limits
            # If executor fetched max_result_rows + 1 rows, query is truncated
            is_truncated = len(raw_rows) > self.max_result_rows
            capped_raw_rows = raw_rows[: self.max_result_rows] if is_truncated else raw_rows

            rows: list[list[Any]] = []
            total_bytes = 0

            for raw_row in capped_raw_rows:
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

            return col_names, col_types, rows, duration_ms, is_truncated

        finally:
            timer.cancel()
            try:
                con.close()
            except Exception as ce:
                logger.debug("Error closing DuckDB connection: %s", ce)
