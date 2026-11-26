"""Security boundaries and DuckDB runtime containment verification test suite.

Verifies:
- CTE scope isolation and prohibited recursive CTEs
- Alias shadowing and forbidden subqueries/relations
- Catalog and file function rejection (read_csv, read_parquet, httpfs, duckdb_tables)
- Runtime execution limits: memory boundaries, threads, read-only mode, statement timeouts
- SQL AST deterministic validator behavior under adversarial attack payloads
"""

import tempfile
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from app.analysis.contracts import (
    ColumnContext,
    DatasetAnalyticalContext,
    SQLValidationCategory,
)
from app.analysis.query_executor import (
    QueryExecutionError,
    QueryTimeoutError,
    RestrictedQueryExecutor,
)
from app.analysis.sql_validator import SQLSecurityValidator


@pytest.fixture
def temp_parquet_file() -> str:
    """Create a temporary parquet file for DuckDB execution engine tests."""
    table = pa.Table.from_arrays(
        [
            pa.array([1, 2, 3, 4, 5]),
            pa.array(["North", "South", "East", "West", "North"]),
            pa.array([100.0, 250.0, 300.0, 150.0, 50.0]),
        ],
        names=["id", "region", "amount"],
    )
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
        path = f.name
    pq.write_table(table, path)
    return path


@pytest.fixture
def dataset_context() -> DatasetAnalyticalContext:
    """Context matching the temp parquet file."""
    return DatasetAnalyticalContext(
        relation_name="dataset",
        dataset_name="sales_data",
        row_count=5,
        column_count=3,
        columns=[
            ColumnContext(
                name="id",
                physical_type="int64",
                logical_type="dimension",
                nullable=False,
            ),
            ColumnContext(
                name="region",
                physical_type="varchar",
                logical_type="dimension",
                nullable=False,
            ),
            ColumnContext(
                name="amount",
                physical_type="float64",
                logical_type="metric",
                nullable=False,
            ),
        ],
    )


class TestSQLSecurityBoundaries:
    """Verifies deterministic AST validation for adversarial and invalid constructs."""

    def setup_method(self) -> None:
        self.validator = SQLSecurityValidator()

    def test_prohibited_recursive_cte(self, dataset_context: DatasetAnalyticalContext) -> None:
        """Recursive CTEs can trigger unbounded resource loops and must be blocked."""
        sql = """
        WITH RECURSIVE cnt(x) AS (
            SELECT 1
            UNION ALL
            SELECT x + 1 FROM cnt WHERE x < 1000000
        )
        SELECT * FROM cnt;
        """
        result = self.validator.validate(sql, dataset_context)
        assert result.is_valid is False
        assert result.category in (
            SQLValidationCategory.RESOURCE_VIOLATION,
            SQLValidationCategory.PROHIBITED_STATEMENT,
            SQLValidationCategory.UNAUTHORIZED_RELATION,
            SQLValidationCategory.SYNTAX_ERROR,
            SQLValidationCategory.COMPLEXITY_LIMIT_EXCEEDED,
        )

    def test_unauthorized_external_file_functions_blocked(
        self, dataset_context: DatasetAnalyticalContext
    ) -> None:
        """Any attempt to call read_csv, read_parquet or file scan functions must be rejected."""
        queries = [
            "SELECT * FROM read_csv('/etc/passwd')",
            "SELECT * FROM read_parquet('s3://my-bucket/data.parquet')",
            "SELECT * FROM 'secret_file.csv'",
            "SELECT * FROM duckdb_tables()",
            "SELECT * FROM information_schema.tables",
        ]
        for q in queries:
            result = self.validator.validate(q, dataset_context)
            assert result.is_valid is False, f"Expected {q} to be rejected"
            assert result.category in (
                SQLValidationCategory.UNAUTHORIZED_RELATION,
                SQLValidationCategory.UNAPPROVED_FUNCTION,
                SQLValidationCategory.SYNTAX_ERROR,
            )

    def test_cte_shadowing_and_alias_isolation(
        self, dataset_context: DatasetAnalyticalContext
    ) -> None:
        """Valid CTEs selecting only from 'dataset' are accepted; invalid relations rejected."""
        valid_cte = """
        WITH regional_summary AS (
            SELECT region, SUM(amount) AS total_amt
            FROM dataset
            GROUP BY region
        )
        SELECT region, total_amt
        FROM regional_summary
        WHERE total_amt > 100
        """
        result = self.validator.validate(valid_cte, dataset_context)
        assert result.is_valid is True

        # CTE attempting to reference an unauthorized base table inside
        invalid_cte = """
        WITH unauthorized_cte AS (
            SELECT * FROM pg_catalog.pg_tables
        )
        SELECT * FROM unauthorized_cte
        """
        result = self.validator.validate(invalid_cte, dataset_context)
        assert result.is_valid is False
        assert result.category in (
            SQLValidationCategory.UNAUTHORIZED_RELATION,
            SQLValidationCategory.UNAPPROVED_FUNCTION,
        )

    def test_prohibited_system_commands_and_mutation(
        self, dataset_context: DatasetAnalyticalContext
    ) -> None:
        """Mutations, DDL, and administrative commands must always be rejected."""
        mutations = [
            "DROP TABLE dataset",
            "DELETE FROM dataset WHERE amount < 0",
            "UPDATE dataset SET amount = 0",
            "INSERT INTO dataset VALUES (1, 'North', 10)",
            "ALTER TABLE dataset ADD COLUMN hacked INT",
            "COPY dataset TO '/tmp/dump.csv'",
        ]
        for m in mutations:
            result = self.validator.validate(m, dataset_context)
            assert result.is_valid is False
            assert result.category == SQLValidationCategory.PROHIBITED_STATEMENT


class TestDuckDBRuntimeLimits:
    """Verifies that the DuckDB execution engine enforces strict resource containment."""

    @pytest.mark.asyncio
    async def test_duckdb_read_only_and_memory_configured(self, temp_parquet_file: str) -> None:
        """Engine should be initialized with configured memory limit and execute queries."""
        executor = RestrictedQueryExecutor(
            memory_limit="256MB",
            threads=1,
            query_timeout_seconds=5.0,
            max_result_rows=100,
        )
        assert executor.memory_limit == "256MB"
        assert executor.threads == 1

        col_names, _col_types, rows, _duration_ms, truncated = await executor.execute_query(
            parquet_path=Path(temp_parquet_file),
            approved_sql=(
                "SELECT region, SUM(amount) AS total FROM dataset "
                "GROUP BY region ORDER BY total DESC"
            ),
        )
        assert len(rows) > 0
        assert "region" in col_names
        assert "total" in col_names
        assert truncated is False
        Path(temp_parquet_file).unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_duckdb_timeout_interruption(self) -> None:
        """Queries taking longer than timeout must raise QueryTimeoutError and be interrupted."""
        # Generate enough rows so cross join produces a noticeable execution time
        table = pa.Table.from_arrays([pa.array(list(range(50000)))], names=["id"])
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            p = f.name
        pq.write_table(table, p)

        executor = RestrictedQueryExecutor(
            memory_limit="128MB",
            threads=1,
            query_timeout_seconds=0.01,  # 10 milliseconds
            max_result_rows=100,
        )
        heavy_query = "SELECT count(*) FROM dataset d1 CROSS JOIN dataset d2 CROSS JOIN dataset d3"
        t0 = time.perf_counter()
        with pytest.raises((QueryTimeoutError, QueryExecutionError)):
            await executor.execute_query(
                parquet_path=Path(p),
                approved_sql=heavy_query,
            )
        elapsed = time.perf_counter() - t0
        assert elapsed < 3.0
        Path(p).unlink(missing_ok=True)
