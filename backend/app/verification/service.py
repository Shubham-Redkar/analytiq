"""High-level verification service coordinating claim validation and response assembly."""

import time
from typing import Any

from app.analysis.contracts import (
    AnalyticalResultColumn,
    ExecutionEvidence,
    StructuredAnalyticalPlan,
)
from app.verification.claim_validator import ClaimValidator
from app.verification.contracts import (
    AnalyticalClaim,
    ClaimVerificationResult,
    IntentConsistencyStatus,
    VerificationStatus,
    VerificationSummary,
)
from app.verification.intent_consistency import verify_intent_consistency
from app.verification.response_builder import assemble_verified_explanation


class EvidenceVerificationService:
    """Service executing deterministic verification on analytical claims and intent."""

    def __init__(self, validator: ClaimValidator | None = None) -> None:
        self.validator = validator or ClaimValidator()

    def verify_analysis(
        self,
        question: str,
        plan: StructuredAnalyticalPlan | None,
        executed_sql: str | None,
        evidence: ExecutionEvidence,
        columns: list[AnalyticalResultColumn],
        rows: list[list[Any]],
        claims: list[AnalyticalClaim],
        request_id: str | None = None,
    ) -> VerificationSummary:
        """Execute complete verification across analytical intent and structured claims."""
        t0 = time.monotonic()
        col_names = [c.name for c in columns]

        # 1. Intent consistency
        intent_res = verify_intent_consistency(
            question=question,
            plan=plan,
            executed_sql=executed_sql,
            columns=col_names,
        )

        limitations: list[str] = []
        if evidence.truncated:
            limitations.append("Result truncated by system limits; population claims restricted.")

        # 2. Claim-by-claim verification
        verified_claims: list[ClaimVerificationResult] = []
        rejected_claims: list[ClaimVerificationResult] = []

        for claim in claims:
            res = self.validator.verify_claim(
                claim=claim,
                evidence=evidence,
                columns=col_names,
                rows=rows,
                current_request_id=request_id,
            )
            if res.status == VerificationStatus.VERIFIED:
                verified_claims.append(res)
            else:
                rejected_claims.append(res)

        # 3. Calculate status counts
        verified_count = len(verified_claims)
        contradicted_count = sum(
            1 for c in rejected_claims if c.status == VerificationStatus.CONTRADICTED
        )
        insufficient_count = sum(
            1 for c in rejected_claims if c.status == VerificationStatus.INSUFFICIENT_EVIDENCE
        )
        unsupported_count = sum(
            1 for c in rejected_claims if c.status == VerificationStatus.UNSUPPORTED
        )
        invalid_ref_count = sum(
            1 for c in rejected_claims if c.status == VerificationStatus.INVALID_REFERENCE
        )

        # Determine overall verification status
        if intent_res.status == IntentConsistencyStatus.CONTRADICTED:
            overall_status = VerificationStatus.CONTRADICTED
            limitations.append(f"Intent contradiction detected: {intent_res.details}")
        elif len(claims) == 0:
            overall_status = VerificationStatus.INSUFFICIENT_EVIDENCE
        elif verified_count == len(claims):
            overall_status = VerificationStatus.VERIFIED
        elif verified_count > 0:
            overall_status = VerificationStatus.VERIFIED  # Partially verified
        else:
            if contradicted_count > 0:
                overall_status = VerificationStatus.CONTRADICTED
            else:
                overall_status = VerificationStatus.INSUFFICIENT_EVIDENCE

        duration_ms = (time.monotonic() - t0) * 1000.0

        summary = VerificationSummary(
            status=overall_status,
            total_claims=len(claims),
            verified_claims_count=verified_count,
            contradicted_claims_count=contradicted_count,
            insufficient_evidence_count=insufficient_count,
            unsupported_claims_count=unsupported_count,
            invalid_references_count=invalid_ref_count,
            intent_consistency=intent_res,
            verified_claims=verified_claims,
            rejected_claims=rejected_claims,
            verification_duration_ms=duration_ms,
            limitations=limitations,
        )

        # Render deterministic verified prose
        summary.verified_explanation = assemble_verified_explanation(
            summary=summary,
            columns=columns,
            rows=rows,
        )

        return summary
