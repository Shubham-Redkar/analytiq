"""Deterministic SQL Security Policy & AST Validation using SQLGlot.

CRITICAL SECURITY BOUNDARY:
All SQL produced by an LLM is untrusted by default.
This validator implements an explicit, deny-by-default security policy:
- Parsed strictly using DuckDB dialect.
- Rejects multiple statements (semicolon splitting / statement lists).
- Rejects all database mutations, DDL, DML, administrative commands, PRAGMAs, and transactions.
- Allows only the authorized logical relation 'dataset' (and nonrecursive CTE aliases).
- Validates all column references against authorized schema (quoted, case-insensitive).
- Allows only an explicit allowlist of deterministic analytical functions.
- Forbids file reads (read_parquet, read_csv, etc.), network calls, shell/extension execution.
- Enforces AST depth and node limits to prevent denial-of-service / parser exhaustion.
- Enforces an application-controlled outer LIMIT constraint without corrupting aggregations.
"""

import logging

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

from app.analysis.contracts import (
    DatasetAnalyticalContext,
    SQLValidationCategory,
    SQLValidationResult,
)

logger = logging.getLogger(__name__)

# Complexity & Resource limits
MAX_SQL_LENGTH = 4000
MAX_AST_NODES = 250
MAX_EXPRESSION_DEPTH = 15
MAX_SELECT_COLUMNS = 50
MAX_ALLOWED_LIMIT = 1000

# Function allowlist: canonical upper-case names
ALLOWED_FUNCTIONS = {
    # Aggregates
    "COUNT",
    "SUM",
    "AVG",
    "MIN",
    "MAX",
    "MEDIAN",
    "STDDEV",
    "STDDEV_SAMP",
    "STDDEV_POP",
    "VARIANCE",
    "VAR_SAMP",
    "VAR_POP",
    # Math
    "ROUND",
    "CEIL",
    "FLOOR",
    "ABS",
    "POWER",
    "SQRT",
    # Strings
    "LOWER",
    "UPPER",
    "TRIM",
    "LTRIM",
    "RTRIM",
    "LENGTH",
    "SUBSTRING",
    "CONCAT",
    "REPLACE",
    # Null handling & logic
    "COALESCE",
    "NULLIF",
    "IFNULL",
    # Date & time
    "DATE_TRUNC",
    "EXTRACT",
    "YEAR",
    "MONTH",
    "DAY",
    "STRFTIME",
    "DATE_DIFF",
    # Type conversion
    "CAST",
    "TRY_CAST",
}

# Explicitly forbidden AST node types
FORBIDDEN_EXPRESSION_TYPES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.Command,
    exp.Set,
    exp.Pragma,
    exp.Copy,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Attach,
    exp.Detach,
    exp.Install,
)


class SQLSecurityValidator:
    """Deterministic AST validator enforcing strict read-only analytical SQL policies."""

    def __init__(
        self,
        max_result_rows: int = 1000,
        max_sql_length: int = MAX_SQL_LENGTH,
    ) -> None:
        self.max_result_rows = max_result_rows
        self.max_sql_length = max_sql_length

    def validate(
        self,
        sql: str,
        context: DatasetAnalyticalContext,
    ) -> SQLValidationResult:
        """Validate proposed SQL against the dataset context and return a strongly typed result."""
        # 1. Length validation
        if not sql or not sql.strip():
            return SQLValidationResult(
                is_valid=False,
                category=SQLValidationCategory.SYNTAX_ERROR,
                error_message="SQL query cannot be empty.",
            )

        trimmed = sql.strip()
        if len(trimmed) > self.max_sql_length:
            return SQLValidationResult(
                is_valid=False,
                category=SQLValidationCategory.COMPLEXITY_LIMIT_EXCEEDED,
                error_message=(
                    f"SQL length ({len(trimmed)}) exceeds maximum allowed ({self.max_sql_length})."
                ),
            )

        # 2. Parse using DuckDB dialect
        try:
            parsed_expressions = sqlglot.parse(trimmed, read="duckdb")
        except ParseError as pe:
            return SQLValidationResult(
                is_valid=False,
                category=SQLValidationCategory.SYNTAX_ERROR,
                error_message=f"SQL syntax error: {pe}",
            )
        except Exception as e:
            return SQLValidationResult(
                is_valid=False,
                category=SQLValidationCategory.SYNTAX_ERROR,
                error_message=f"Malformed SQL query: {e}",
            )

        if not parsed_expressions or parsed_expressions[0] is None:
            return SQLValidationResult(
                is_valid=False,
                category=SQLValidationCategory.SYNTAX_ERROR,
                error_message="No valid SQL statements found.",
            )

        # 3. Reject multiple statements
        if len(parsed_expressions) > 1:
            return SQLValidationResult(
                is_valid=False,
                category=SQLValidationCategory.PROHIBITED_STATEMENT,
                error_message="Multiple SQL statements are strictly forbidden.",
            )

        root = parsed_expressions[0]

        # 4. Root must be a SELECT or a top-level UNION/CTE ending in SELECT
        if not isinstance(root, (exp.Select, exp.Union)):
            return SQLValidationResult(
                is_valid=False,
                category=SQLValidationCategory.PROHIBITED_STATEMENT,
                error_message=(
                    f"Root statement must be a SELECT expression (received {type(root).__name__})."
                ),
            )

        # 5. Check AST complexity and forbidden expressions
        node_count = 0
        max_depth = 0

        for node in root.walk():
            node_count += 1
            if node_count > MAX_AST_NODES:
                return SQLValidationResult(
                    is_valid=False,
                    category=SQLValidationCategory.COMPLEXITY_LIMIT_EXCEEDED,
                    error_message=(
                        f"Query AST node count ({node_count}) exceeds limit ({MAX_AST_NODES})."
                    ),
                )

            # Check depth
            depth = node.depth
            if depth > max_depth:
                max_depth = depth
            if max_depth > MAX_EXPRESSION_DEPTH:
                return SQLValidationResult(
                    is_valid=False,
                    category=SQLValidationCategory.COMPLEXITY_LIMIT_EXCEEDED,
                    error_message=(
                        f"Query expression nesting depth ({max_depth}) exceeds "
                        f"limit ({MAX_EXPRESSION_DEPTH})."
                    ),
                )

            # Check forbidden AST types
            if isinstance(node, FORBIDDEN_EXPRESSION_TYPES):
                return SQLValidationResult(
                    is_valid=False,
                    category=SQLValidationCategory.PROHIBITED_STATEMENT,
                    error_message=f"Operation '{type(node).__name__}' is strictly prohibited.",
                )

        # 6. Function validation (run first so file/system functions are identified)
        for func in root.find_all(exp.Func):
            # In SQLGlot AST, binary connectors like exp.And / exp.Or inherit from exp.Func
            if isinstance(func, (exp.Connector, exp.Binary)):
                continue

            func_name = func.key.upper() if func.key else ""
            if not func_name:
                continue

            # Check for file reading or extension functions
            if any(f in func_name for f in ("READ_", "PARQUET", "CSV", "GLOB", "ATTACH", "PRAGMA")):
                return SQLValidationResult(
                    is_valid=False,
                    category=SQLValidationCategory.UNAPPROVED_FUNCTION,
                    error_message=f"Prohibited file/system function '{func_name}'.",
                )

            if func_name not in ALLOWED_FUNCTIONS:
                return SQLValidationResult(
                    is_valid=False,
                    category=SQLValidationCategory.UNAPPROVED_FUNCTION,
                    error_message=(
                        f"Function '{func_name}' is not in the approved analytical function "
                        "allowlist."
                    ),
                )

        # 7. Scope and Table/Relation validation
        valid_cte_names: set[str] = set()
        with_exp = root.find(exp.With)
        if with_exp and isinstance(with_exp, exp.With):
            # Check for recursive CTE
            if with_exp.args.get("recursive"):
                return SQLValidationResult(
                    is_valid=False,
                    category=SQLValidationCategory.RESOURCE_VIOLATION,
                    error_message="Recursive CTEs are strictly prohibited.",
                )
            for cte in with_exp.expressions:
                if isinstance(cte, exp.CTE):
                    alias = cte.alias_or_name
                    if alias:
                        valid_cte_names.add(alias.lower())

        referenced_tables: set[str] = set()
        for table_node in root.find_all(exp.Table):
            # Check for catalog or schema qualification (e.g. pg_catalog.pg_tables or db.tbl)
            if table_node.db or table_node.catalog:
                return SQLValidationResult(
                    is_valid=False,
                    category=SQLValidationCategory.UNAUTHORIZED_RELATION,
                    error_message=(
                        f"Qualified relation '{table_node.sql()}' is strictly prohibited. "
                        "Queries may only access 'dataset'."
                    ),
                )

            t_name = table_node.name.lower()
            referenced_tables.add(t_name)
            if t_name != "dataset" and t_name not in valid_cte_names:
                return SQLValidationResult(
                    is_valid=False,
                    category=SQLValidationCategory.UNAUTHORIZED_RELATION,
                    error_message=(
                        f"Unauthorized relation '{table_node.name}'. Queries may only access "
                        "'dataset'."
                    ),
                )

        # 8. Column validation against dataset context and SELECT aliases
        valid_columns_case_map: dict[str, str] = {
            col.name.lower(): col.name for col in context.columns
        }
        # Collect SELECT aliases defined in query expressions (e.g. SELECT AVG(x) AS avg_x)
        select_aliases: set[str] = {
            alias_node.alias_or_name.lower()
            for alias_node in root.find_all(exp.Alias)
            if alias_node.alias_or_name
        }
        referenced_columns: set[str] = set()

        for col_node in root.find_all(exp.Column):
            col_name = col_node.name
            if not col_name:
                continue

            # Skip wildcard / star expansions
            if col_name == "*":
                continue

            col_lower = col_name.lower()
            if col_lower not in valid_columns_case_map:
                # 1. Could be an alias introduced in SELECT and used in ORDER BY or HAVING
                if col_lower in select_aliases:
                    continue

                # 2. Could be a column introduced in CTE; check if qualifier matches CTE
                table_qualifier = col_node.table.lower() if col_node.table else ""
                if table_qualifier and table_qualifier in valid_cte_names:
                    continue

                return SQLValidationResult(
                    is_valid=False,
                    category=SQLValidationCategory.UNKNOWN_COLUMN,
                    error_message=f"Column '{col_name}' does not exist in dataset schema.",
                )
            referenced_columns.add(valid_columns_case_map[col_lower])

        # 9. Result limit inspection & safe outer constraint
        has_user_limit = False
        requested_limit: int | None = None
        limit_node = root.args.get("limit")
        if limit_node and isinstance(limit_node, exp.Limit):
            has_user_limit = True
            try:
                val = int(limit_node.expression.this)  # type: ignore[attr-defined]
                requested_limit = val
            except (ValueError, TypeError, AttributeError):
                requested_limit = None

        # Apply safe limit enforcement without modifying subqueries/aggregations
        # If user did not supply LIMIT or supplied > max_result_rows, enforce max_result_rows + 1
        # for deterministic N+1 truncation detection by the executor.
        # If user explicitly supplied limit <= max_result_rows, preserve user limit exactly.
        enforced_root = root.copy()
        fetch_limit = self.max_result_rows + 1
        if not has_user_limit:
            enforced_root = enforced_root.limit(fetch_limit)
        elif requested_limit is not None and requested_limit > self.max_result_rows:
            enforced_root.set("limit", exp.Limit(expression=exp.Literal.number(fetch_limit)))

        normalized_sql = enforced_root.sql(dialect="duckdb")

        return SQLValidationResult(
            is_valid=True,
            category=SQLValidationCategory.VALID,
            normalized_sql=normalized_sql,
            referenced_columns=sorted(referenced_columns),
            referenced_tables=sorted(referenced_tables),
            has_user_limit=has_user_limit,
            requested_limit=requested_limit,
        )
