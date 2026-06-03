"""Result types produced by the scoring engine.

Kept separate from the domain models so the scoring layer has its own
vocabulary (criteria, verdicts) without polluting Company/Thesis.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, computed_field


class Verdict(str, Enum):
    pass_ = "pass"
    fail = "fail"
    unknown = "unknown"  # data missing — cannot judge this criterion


class CriterionResult(BaseModel):
    """The outcome of evaluating one thesis criterion against a company."""

    name: str
    verdict: Verdict
    weight: Decimal
    score: Decimal = Field(description="0..1 contribution before weighting")
    reason: str

    @property
    def weighted_score(self) -> Decimal:
        return self.weight * self.score


class ThesisFit(BaseModel):
    """Aggregate screening result for one company against one thesis."""

    company_name: str
    thesis_name: str
    hard_failed: bool = Field(
        description="True if any exclusion (sector/country/keyword) tripped. "
        "A hard fail short-circuits scoring."
    )
    overall_score: Decimal = Field(description="0..100 weighted score")
    criteria: list[CriterionResult] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @computed_field  # serialised into JSON, unlike a bare @property
    @property
    def recommendation(self) -> str:
        if self.hard_failed:
            return "PASS — fails a hard exclusion"
        if self.overall_score >= 70:
            return "ADVANCE — strong thesis fit"
        if self.overall_score >= 50:
            return "REVIEW — partial fit, judgment needed"
        return "PASS — weak thesis fit"
