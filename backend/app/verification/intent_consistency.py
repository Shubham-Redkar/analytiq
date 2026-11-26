"""Deterministic verification of analytical intent against executed SQL and schema."""

import sqlglot
from sqlglot import exp

from app.analysis.contracts import StructuredAnalyticalPlan
from app.verification.contracts import IntentConsistencyResult, IntentConsistencyStatus


def verify_intent_consistency(
    question: str,
    plan: StructuredAnalyticalPlan | None,
    executed_sql: str | None,
    columns: list[str],
) -> IntentConsistencyResult:
    """Validate that the executed SQL structure faithfully answers the analytical intent."""
    if not executed_sql or not plan:
        return IntentConsistencyResult(
            status=IntentConsistencyStatus.INSUFFICIENT_INFORMATION,
            reason_code="MISSING_PLAN_OR_SQL",
            details="Analytical plan or executed SQL is missing; cannot verify intent consistency.",
        )

    try:
        ast = sqlglot.parse_one(executed_sql, read="duckdb")
    except Exception as e:
        return IntentConsistencyResult(
            status=IntentConsistencyStatus.INSUFFICIENT_INFORMATION,
            reason_code="SQL_PARSE_ERROR",
            details=f"Could not parse executed SQL for AST inspection: {e}",
        )

    q_lower = question.lower()

    # 1. Check aggregation mismatches: average vs sum
    # If question explicitly asks for "average" or "avg", SQL must not be doing pure SUM without AVG
    aggregations_in_sql = [func.key.upper() for func in ast.find_all(exp.Anonymous)]
    # Also check standard Aggregate expressions
    for agg in (exp.Avg, exp.Sum, exp.Count, exp.Min, exp.Max):
        if list(ast.find_all(agg)):
            aggregations_in_sql.append(agg.key.upper())

    if ("average" in q_lower or "avg " in q_lower) and "AVG" not in aggregations_in_sql:
        if "SUM" in aggregations_in_sql:
            return IntentConsistencyResult(
                status=IntentConsistencyStatus.CONTRADICTED,
                reason_code="AGGREGATION_MISMATCH_AVG_VS_SUM",
                details="Question requested average, but query calculates sum.",
                mismatched_aggregation="AVG vs SUM",
            )

    if ("total" in q_lower or "sum of" in q_lower) and "SUM" not in aggregations_in_sql:
        if "AVG" in aggregations_in_sql:
            return IntentConsistencyResult(
                status=IntentConsistencyStatus.CONTRADICTED,
                reason_code="AGGREGATION_MISMATCH_SUM_VS_AVG",
                details="Question requested total/sum, but query calculates average.",
                mismatched_aggregation="SUM vs AVG",
            )

    # 2. Check COUNT DISTINCT vs ordinary COUNT
    if "distinct" in q_lower and "count" in q_lower:
        has_count_distinct = False
        for count_expr in ast.find_all(exp.Count):
            if count_expr.args.get("distinct"):
                has_count_distinct = True
                break
        if not has_count_distinct:
            return IntentConsistencyResult(
                status=IntentConsistencyStatus.CONTRADICTED,
                reason_code="COUNT_DISTINCT_MISMATCH",
                details="Question requested distinct count, but query used non-distinct COUNT.",
                mismatched_aggregation="COUNT DISTINCT vs COUNT",
            )

    # 3. Check requested top-N limit versus SQL limit
    # e.g., "top 3" or "top 5"
    import re

    top_match = re.search(r"\btop\s+(\d+)\b", q_lower)
    if top_match:
        expected_limit = int(top_match.group(1))
        limit_nodes = list(ast.find_all(exp.Limit))
        if limit_nodes:
            limit_val_expr = limit_nodes[0].expression
            if isinstance(limit_val_expr, exp.Literal) and limit_val_expr.is_int:
                sql_limit = int(limit_val_expr.this)
                if sql_limit != expected_limit:
                    return IntentConsistencyResult(
                        status=IntentConsistencyStatus.CONTRADICTED,
                        reason_code="LIMIT_MISMATCH",
                        details=(
                            f"Question requested top {expected_limit}, "
                            f"but query limited to {sql_limit}."
                        ),
                    )

    # 4. Check sort direction: top vs bottom
    if "top" in q_lower:
        order_nodes = list(ast.find_all(exp.Ordered))
        if order_nodes:
            # By default SQL ORDER BY is ASC unless DESC is present
            is_desc = any(o.args.get("desc") is True for o in order_nodes)
            if not is_desc:
                return IntentConsistencyResult(
                    status=IntentConsistencyStatus.CONTRADICTED,
                    reason_code="ORDER_DIRECTION_MISMATCH",
                    details=(
                        "Question requested top ranking (expected DESC), but query ordered ASC."
                    ),
                )

    if "bottom" in q_lower or "lowest" in q_lower:
        order_nodes = list(ast.find_all(exp.Ordered))
        if order_nodes:
            is_asc = any(o.args.get("desc") is not True for o in order_nodes)
            if not is_asc:
                return IntentConsistencyResult(
                    status=IntentConsistencyStatus.CONTRADICTED,
                    reason_code="ORDER_DIRECTION_MISMATCH",
                    details=(
                        "Question requested lowest ranking (expected ASC), but query ordered DESC."
                    ),
                )

    return IntentConsistencyResult(
        status=IntentConsistencyStatus.CONSISTENT,
        reason_code="INTENT_CONSISTENT",
        details="Executed SQL structure matches analytical question parameters.",
    )
