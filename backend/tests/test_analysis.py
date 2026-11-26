"""Comprehensive test suite for the Analytical Engine: SQL security, planner, and executor."""

import tempfile
import uuid
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
from app.analysis.service import AnalysisService
from app.analysis.sql_validator import SQLSecurityValidator
from app.core.config import Settings
from app.llm.providers.mock import MockLLMProvider
from app.models.dataset import Dataset


@pytest.fixture
def sample_context() -> DatasetAnalyticalContext:
    """Standard authorized context fixture for testing."""
    return DatasetAnalyticalContext(
        relation_name="dataset",
        dataset_name="Titanic Passengers",
        row_count=891,
        column_count=5,
        columns=[
            ColumnContext(
                name="PassengerId", physical_type="BIGINT", logical_type="integer", nullable=False
            ),
            ColumnContext(
                name="Survived", physical_type="BIGINT", logical_type="integer", nullable=False
            ),
            ColumnContext(
                name="Pclass", physical_type="BIGINT", logical_type="integer", nullable=False
            ),
            ColumnContext(name="Fare", physical_type="DOUBLE", logical_type="float", nullable=True),
            ColumnContext(
                name="Embarked", physical_type="VARCHAR", logical_type="string", nullable=True
            ),
        ],
        dialect="duckdb",
    )


class TestSQLSecurityPolicy:
    """Exhaustive table-driven tests for deny-by-default SQL security validator."""

    def setup_method(self) -> None:
        self.validator = SQLSecurityValidator(max_result_rows=100)

    @pytest.mark.parametrize(
        "sql,expected_columns",
        [
            ("SELECT COUNT(*) FROM dataset", []),
            (
                'SELECT "Pclass", AVG("Fare") AS avg_fare FROM dataset GROUP BY "Pclass"',
                ["Fare", "Pclass"],
            ),
            ('SELECT * FROM dataset WHERE "Fare" > 50.0 ORDER BY "Fare" DESC LIMIT 10', ["Fare"]),
            (
                'SELECT MIN("Fare"), MAX("Fare"), MEDIAN("Fare"), STDDEV("Fare") FROM dataset',
                ["Fare"],
            ),
            (
                'SELECT "Embarked", COUNT(*) AS cnt FROM dataset WHERE "Embarked" IS NOT NULL '
                'GROUP BY "Embarked" HAVING COUNT(*) > 5',
                ["Embarked"],
            ),
            (
                'SELECT "PassengerId", COALESCE("Fare", 0.0) AS fare_clean FROM dataset',
                ["Fare", "PassengerId"],
            ),
            ('SELECT DISTINCT "Pclass" FROM dataset', ["Pclass"]),
            (
                'SELECT "Pclass", ROUND(100.0 * AVG(CASE WHEN "Survived" = 1 THEN 1.0 ELSE 0.0 '
                'END), 2) AS survival_rate FROM dataset GROUP BY "Pclass" ORDER BY "Pclass"',
                ["Pclass", "Survived"],
            ),
            (
                'SELECT "Pclass", SUM(CASE WHEN "Survived" = 1 THEN 1 ELSE 0 END) AS survivors '
                'FROM dataset GROUP BY "Pclass"',
                ["Pclass", "Survived"],
            ),
        ],
    )
    def test_valid_queries_pass(
        self,
        sample_context: DatasetAnalyticalContext,
        sql: str,
        expected_columns: list[str],
    ) -> None:
        res = self.validator.validate(sql, sample_context)
        assert res.is_valid is True
        assert res.category == SQLValidationCategory.VALID
        for col in expected_columns:
            assert col in res.referenced_columns
        assert res.normalized_sql is not None
        assert "dataset" in res.referenced_tables

    @pytest.mark.parametrize(
        "adversarial_sql,expected_category",
        [
            # Multiple statements
            (
                "SELECT * FROM dataset; DROP TABLE dataset;",
                SQLValidationCategory.PROHIBITED_STATEMENT,
            ),
            ("SELECT 1; SELECT 2;", SQLValidationCategory.PROHIBITED_STATEMENT),
            # Forbidden DDL / DML / Admin
            (
                "INSERT INTO dataset VALUES (1, 0, 3, 10.0, 'S')",
                SQLValidationCategory.PROHIBITED_STATEMENT,
            ),
            ('UPDATE dataset SET "Fare" = 100.0', SQLValidationCategory.PROHIBITED_STATEMENT),
            (
                'DELETE FROM dataset WHERE "Survived" = 0',
                SQLValidationCategory.PROHIBITED_STATEMENT,
            ),
            ("DROP TABLE dataset", SQLValidationCategory.PROHIBITED_STATEMENT),
            ("CREATE TABLE evil (id INT)", SQLValidationCategory.PROHIBITED_STATEMENT),
            (
                "ALTER TABLE dataset ADD COLUMN hacked TEXT",
                SQLValidationCategory.PROHIBITED_STATEMENT,
            ),
            ("ATTACH 'other.db' AS evil", SQLValidationCategory.PROHIBITED_STATEMENT),
            ("COPY dataset TO '/tmp/leak.csv'", SQLValidationCategory.PROHIBITED_STATEMENT),
            ("PRAGMA table_info(dataset)", SQLValidationCategory.PROHIBITED_STATEMENT),
            ("SET threads = 8", SQLValidationCategory.PROHIBITED_STATEMENT),
            # Unauthorized relations & file reads
            (
                "SELECT * FROM read_parquet('/etc/passwd')",
                SQLValidationCategory.UNAPPROVED_FUNCTION,
            ),
            (
                "SELECT * FROM read_csv_auto('/etc/passwd')",
                SQLValidationCategory.UNAPPROVED_FUNCTION,
            ),
            ("SELECT * FROM glob('/home/*')", SQLValidationCategory.UNAPPROVED_FUNCTION),
            ("SELECT * FROM users", SQLValidationCategory.UNAUTHORIZED_RELATION),
            (
                "SELECT * FROM information_schema.tables",
                SQLValidationCategory.UNAUTHORIZED_RELATION,
            ),
            ("SELECT * FROM pg_catalog.pg_tables", SQLValidationCategory.UNAUTHORIZED_RELATION),
            # Unknown columns
            ('SELECT "NonExistentColumn" FROM dataset', SQLValidationCategory.UNKNOWN_COLUMN),
            ('SELECT "password_hash" FROM dataset', SQLValidationCategory.UNKNOWN_COLUMN),
            # Unapproved functions
            ('SELECT evil_func("Fare") FROM dataset', SQLValidationCategory.UNAPPROVED_FUNCTION),
            (
                "SELECT current_setting('threads') FROM dataset",
                SQLValidationCategory.UNAPPROVED_FUNCTION,
            ),
            # Recursive CTEs
            (
                "WITH RECURSIVE cnt(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM cnt WHERE x < 10) "
                "SELECT * FROM cnt",
                SQLValidationCategory.RESOURCE_VIOLATION,
            ),
        ],
    )
    def test_adversarial_queries_rejected(
        self,
        sample_context: DatasetAnalyticalContext,
        adversarial_sql: str,
        expected_category: SQLValidationCategory,
    ) -> None:
        res = self.validator.validate(adversarial_sql, sample_context)
        assert res.is_valid is False
        assert res.category == expected_category
        assert res.error_message is not None

    def test_outer_limit_enforcement(self, sample_context: DatasetAnalyticalContext) -> None:
        # User query without limit gets max_result_rows + 1 appended for N+1 truncation detection
        res = self.validator.validate('SELECT "Fare" FROM dataset', sample_context)
        assert res.is_valid is True
        assert "LIMIT 101" in (res.normalized_sql or "")

        # User query with higher limit gets clamped to max_result_rows + 1
        res2 = self.validator.validate('SELECT "Fare" FROM dataset LIMIT 500', sample_context)
        assert res2.is_valid is True
        assert "LIMIT 101" in (res2.normalized_sql or "")

        # User query with smaller limit is preserved exactly
        res3 = self.validator.validate('SELECT "Fare" FROM dataset LIMIT 5', sample_context)
        assert res3.is_valid is True
        assert "LIMIT 5" in (res3.normalized_sql or "")


class TestDuckDBRestrictedExecutor:
    """Verify DuckDB isolation, defense-in-depth, and interruption."""

    @pytest.fixture
    def test_parquet_file(self) -> Path:
        """Create a temporary deterministic parquet file."""
        tbl = pa.Table.from_arrays(
            [
                pa.array([1, 2, 3, 4, 5]),
                pa.array(["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]),
                pa.array([10.5, 20.0, None, 45.2, 50.0]),
            ],
            names=["id", "label", "val"],
        )
        tf = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
        pq.write_table(tbl, tf.name)
        return Path(tf.name)

    @pytest.mark.asyncio
    async def test_successful_query_execution(self, test_parquet_file: Path) -> None:
        executor = RestrictedQueryExecutor(query_timeout_seconds=5.0)
        query = (
            'SELECT "label", AVG("val") AS avg_v FROM dataset WHERE "val" IS NOT NULL '
            'GROUP BY "label" ORDER BY "label"'
        )
        cols, _types, rows, dur, is_truncated = await executor.execute_query(
            parquet_path=test_parquet_file,
            approved_sql=query,
        )
        assert len(cols) == 2
        assert cols == ["label", "avg_v"]
        assert len(rows) == 4
        assert rows[0][0] == "Alpha"
        assert rows[0][1] == 10.5
        assert dur > 0
        assert is_truncated is False

    @pytest.mark.asyncio
    async def test_n_plus_one_truncation_detection(self, test_parquet_file: Path) -> None:
        # If max_result_rows is 2, query requesting all rows should be marked truncated
        executor = RestrictedQueryExecutor(max_result_rows=2, query_timeout_seconds=5.0)
        _cols, _types, rows, _dur, is_truncated = await executor.execute_query(
            parquet_path=test_parquet_file,
            approved_sql="SELECT * FROM dataset",
        )
        assert is_truncated is True
        assert len(rows) == 2

    @pytest.mark.asyncio
    async def test_defense_in_depth_blocks_arbitrary_files(self, test_parquet_file: Path) -> None:
        executor = RestrictedQueryExecutor()
        # Even if a bypass got past SQL validator, DuckDB locked enable_external_access=false
        with pytest.raises(QueryExecutionError):
            await executor.execute_query(
                parquet_path=test_parquet_file,
                approved_sql="SELECT * FROM read_parquet('/tmp/evil.parquet')",
            )

    @pytest.mark.asyncio
    async def test_query_timeout_interruption(self, test_parquet_file: Path) -> None:
        # A runaway query that triggers timeout interruption
        executor = RestrictedQueryExecutor(query_timeout_seconds=0.01)
        # Cartesian cross joins designed to run long enough to trigger interruption
        heavy_query = (
            "SELECT COUNT(*) FROM dataset a, dataset b, dataset c, "
            "dataset d, dataset e, dataset f, dataset g, dataset h, dataset i, dataset j"
        )
        with pytest.raises(QueryTimeoutError):
            await executor.execute_query(
                parquet_path=test_parquet_file,
                approved_sql=heavy_query,
            )


class TestAnalyticalServicePipeline:
    """Verify end-to-end analytical pipeline with Mock provider."""

    @pytest.fixture
    def test_dataset(self, test_parquet_file: Path) -> Dataset:
        ds = Dataset(
            id=uuid.uuid4(),
            owner_id=uuid.uuid4(),
            name="Test Synthetic Dataset",
            original_filename="synthetic.parquet",
            file_format="csv",
            file_size_bytes=1024,
            storage_key="test-storage-key",
            row_count=5,
            column_count=3,
            status="ready",
            schema_json={
                "columns": [
                    {"name": "id", "physical_type": "BIGINT", "logical_type": "integer"},
                    {"name": "label", "physical_type": "VARCHAR", "logical_type": "string"},
                    {"name": "val", "physical_type": "DOUBLE", "logical_type": "float"},
                ]
            },
        )
        return ds

    @pytest.fixture
    def test_parquet_file(self) -> Path:
        tbl = pa.Table.from_arrays(
            [pa.array([1, 2, 3]), pa.array(["A", "B", "C"]), pa.array([10.0, 20.0, 30.0])],
            names=["id", "label", "val"],
        )
        tf = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
        pq.write_table(tbl, tf.name)
        return Path(tf.name)

    @pytest.mark.asyncio
    async def test_pipeline_completed_query(
        self,
        test_dataset: Dataset,
        test_parquet_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_plan = {
            "status": "ready",
            "intent": "Compute total val",
            "operation": "aggregation",
            "referenced_columns": ["val"],
            "sql": 'SELECT SUM("val") AS total_val FROM dataset',
            "assumptions": [],
        }
        mock_provider = MockLLMProvider(canned_responses=[mock_plan])
        cfg = Settings(llm_provider="mock", analysis_max_result_rows=10)
        svc = AnalysisService(llm_provider=mock_provider, settings=cfg)

        # Mock storage get_parquet_file_path to return our fixture
        monkeypatch.setattr(svc.storage, "get_parquet_file_path", lambda did: test_parquet_file)

        res = await svc.run_analysis(test_dataset, "What is the total val?")
        assert res.status == "completed"
        assert res.executed_sql is not None
        assert len(res.rows) == 1
        assert res.rows[0][0] == 60.0
        assert res.evidence is not None
        assert res.evidence.result_fingerprint is not None

    @pytest.mark.asyncio
    async def test_pipeline_clarification(
        self,
        test_dataset: Dataset,
    ) -> None:
        mock_plan = {
            "status": "needs_clarification",
            "intent": "Ambiguous request",
            "clarification_question": "Do you mean sum or average?",
        }
        mock_provider = MockLLMProvider(canned_responses=[mock_plan])
        svc = AnalysisService(llm_provider=mock_provider)
        res = await svc.run_analysis(test_dataset, "Calculate val")
        assert res.status == "needs_clarification"
        assert res.clarification_question == "Do you mean sum or average?"
        assert res.executed_sql is None
        assert res.evidence is None

    @pytest.mark.asyncio
    async def test_pipeline_unsupported_request(
        self,
        test_dataset: Dataset,
    ) -> None:
        mock_plan = {
            "status": "unsupported",
            "intent": "Forecasting sales",
            "unsupported_reason": "Predictive modeling is not supported in M3.",
        }
        mock_provider = MockLLMProvider(canned_responses=[mock_plan])
        svc = AnalysisService(llm_provider=mock_provider)
        res = await svc.run_analysis(test_dataset, "Predict future val for next year")
        assert res.status == "unsupported"
        assert res.unsupported_reason == "Predictive modeling is not supported in M3."
        assert res.executed_sql is None

    @pytest.mark.asyncio
    async def test_pipeline_security_rejection_blocks_execution(
        self,
        test_dataset: Dataset,
    ) -> None:
        mock_plan = {
            "status": "ready",
            "intent": "Malicious attempt",
            "sql": "SELECT * FROM read_parquet('/etc/passwd')",
        }
        mock_provider = MockLLMProvider(canned_responses=[mock_plan])
        svc = AnalysisService(llm_provider=mock_provider)
        res = await svc.run_analysis(test_dataset, "Read system files")
        assert res.status == "query_rejected"
        assert "unapproved_function" in (res.error_message or "").lower()
        assert res.rows == []

    @pytest.mark.asyncio
    async def test_non_ready_dataset_rejected(self, test_dataset: Dataset) -> None:
        test_dataset.status = "processing"
        mock_provider = MockLLMProvider()
        svc = AnalysisService(llm_provider=mock_provider)
        res = await svc.run_analysis(test_dataset, "How many rows?")
        assert res.status == "failed"
        assert "ready" in (res.error_message or "").lower()

    @pytest.mark.asyncio
    async def test_evidence_fingerprints_determinism_and_sensitivity(
        self,
        test_dataset: Dataset,
        test_parquet_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.analysis.evidence import compute_result_fingerprint

        # Identical columns and rows yield identical fingerprint
        cols = ["id", "val"]
        rows1 = [[1, 10.0], [2, 20.0]]
        rows2 = [[1, 10.0], [2, 20.0]]
        fp1 = compute_result_fingerprint(cols, rows1)
        fp2 = compute_result_fingerprint(cols, rows2)
        assert fp1 == fp2

        # Swapped columns or swapped values yield distinct fingerprint
        rows_swapped_val = [[1, 20.0], [2, 10.0]]
        fp3 = compute_result_fingerprint(cols, rows_swapped_val)
        assert fp1 != fp3

        # Swapped column order yields distinct fingerprint
        cols_swapped = ["val", "id"]
        fp4 = compute_result_fingerprint(cols_swapped, rows1)
        assert fp1 != fp4

        # Null vs empty string yields distinct fingerprint
        fp_null = compute_result_fingerprint(["text"], [[None]])
        fp_empty = compute_result_fingerprint(["text"], [[""]])
        assert fp_null != fp_empty

    @pytest.mark.asyncio
    async def test_context_privacy_sample_exclusion_and_boundaries(
        self, test_dataset: Dataset
    ) -> None:
        from app.analysis.context_builder import build_dataset_context

        # Default excludes raw samples
        ctx_default = build_dataset_context(test_dataset)
        for col in ctx_default.columns:
            # High cardinality or non-discrete columns must have 0 samples
            if col.name == "val":
                assert len(col.sample_values) == 0

        # When include_samples=True, samples are populated but bounded
        ctx_samples = build_dataset_context(test_dataset, include_samples=True)
        for col in ctx_samples.columns:
            assert len(col.sample_values) <= 5

    @pytest.mark.asyncio
    async def test_benchmark_numerical_tolerances_and_integrity(self) -> None:
        """Verify that benchmark numerical validators enforce exact tolerances."""
        from app.analysis.benchmark import BENCHMARK_CASES, HOLDOUT_BENCHMARK_CASES

        all_cases = {c.id: c for c in BENCHMARK_CASES + HOLDOUT_BENCHMARK_CASES}

        # TC-15: exact median is 305.0
        tc15 = all_cases["TC-15"]
        assert tc15.result_validator is not None
        assert tc15.result_validator([[305.0]], None) is True
        assert tc15.result_validator([[260.0]], None) is False
        assert tc15.result_validator([[350.0]], None) is False

        # HC-10: exact min non-zero discount is 0.05
        hc10 = all_cases["HC-10"]
        assert hc10.result_validator is not None
        assert hc10.result_validator([[0.05]], None) is True
        assert hc10.result_validator([[0.10]], None) is False
        assert hc10.result_validator([[0.0]], None) is False

        # HC-09: exact distinct combinations is 11
        hc09 = all_cases["HC-09"]
        assert hc09.result_validator is not None
        assert hc09.result_validator([[11]], None) is True
        assert hc09.result_validator([[10]], None) is False
        assert hc09.result_validator([[12]], None) is False

    @pytest.mark.asyncio
    async def test_benchmark_macro_categories_strictly_partition(self) -> None:
        """Verify that macro categories partition all 40 cases without overlap."""
        from app.analysis.benchmark import BENCHMARK_CASES, HOLDOUT_BENCHMARK_CASES

        all_cases = BENCHMARK_CASES + HOLDOUT_BENCHMARK_CASES
        assert len(all_cases) == 40
        ids = [c.id for c in all_cases]
        assert len(set(ids)) == 40

        macros = [c.macro_category for c in all_cases]
        assert all(bool(m) for m in macros)
        assert len(macros) == 40

    @pytest.mark.asyncio
    async def test_select_alias_scope_security(self) -> None:
        """Verify that SELECT alias resolution cannot bypass physical column checks."""
        from app.analysis.contracts import ColumnContext, DatasetAnalyticalContext
        from app.analysis.sql_validator import SQLSecurityValidator

        ctx = DatasetAnalyticalContext(
            dataset_name="Test",
            row_count=100,
            column_count=2,
            columns=[
                ColumnContext(name="region", physical_type="VARCHAR", logical_type="string"),
                ColumnContext(name="revenue", physical_type="DOUBLE", logical_type="float"),
            ],
        )
        validator = SQLSecurityValidator()

        # Valid alias in ORDER BY
        valid_q = (
            "SELECT region, SUM(revenue) AS total_rev "
            "FROM dataset GROUP BY region ORDER BY total_rev DESC"
        )
        r1 = validator.validate(valid_q, ctx)
        assert r1.is_valid is True

        # Invalid column in ORDER BY that is NOT an alias and NOT in schema
        invalid_q = (
            "SELECT region, SUM(revenue) AS total_rev "
            "FROM dataset GROUP BY region ORDER BY fake_col DESC"
        )
        r2 = validator.validate(invalid_q, ctx)
        assert r2.is_valid is False
        assert r2.category == SQLValidationCategory.UNKNOWN_COLUMN
