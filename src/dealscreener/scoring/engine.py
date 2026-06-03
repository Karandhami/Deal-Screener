"""Deterministic thesis-fit scoring.

This module is the analytical core. It is deliberately free of any LLM,
network, or I/O: a pure function of (Company, InvestmentThesis) -> ThesisFit.
That purity is what makes it unit-testable and what lets us promise, in an
interview, that *no screening number is ever hallucinated*.

Scoring model
-------------
1. Hard exclusions are checked first (sector / country / keyword). Any hit
   short-circuits to a hard fail with overall_score = 0.
2. Each remaining criterion yields a CriterionResult with a 0..1 score and
   a weight. Missing data -> Verdict.unknown, which is scored as a neutral
   0.5 rather than a zero, so absent information neither rewards nor unfairly
   punishes a target.
3. overall_score is the weighted average of present + unknown criteria,
   rescaled to 0..100.
"""

from __future__ import annotations

from decimal import Decimal

from dealscreener.models.domain import Company, InvestmentThesis
from dealscreener.models.results import CriterionResult, ThesisFit, Verdict

# Relative weights. Tunable, but documented so the behaviour is explainable.
_WEIGHTS = {
    "revenue_band": Decimal("1.0"),
    "revenue_growth": Decimal("1.5"),
    "ebitda_margin": Decimal("1.25"),
    "net_leverage": Decimal("1.0"),
    "valuation": Decimal("1.25"),
}

_NEUTRAL = Decimal("0.5")


def _hard_exclusions(company: Company, thesis: InvestmentThesis) -> list[str]:
    """Return the list of tripped exclusions (empty == clean)."""
    hits: list[str] = []
    if company.sector not in thesis.target_sectors:
        hits.append(f"sector '{company.sector.value}' outside thesis focus")
    if company.country.upper() in {c.upper() for c in thesis.excluded_countries}:
        hits.append(f"country '{company.country}' is excluded")
    desc = company.description.lower()
    for kw in thesis.excluded_keywords:
        if kw.lower() in desc:
            hits.append(f"excluded keyword '{kw}' present in description")
    return hits


def _score_revenue_band(c: Company, t: InvestmentThesis) -> CriterionResult:
    rev = c.financials.revenue
    w = _WEIGHTS["revenue_band"]
    if t.min_revenue is None and t.max_revenue is None:
        return CriterionResult(
            name="revenue_band",
            verdict=Verdict.unknown,
            weight=w,
            score=_NEUTRAL,
            reason="thesis sets no revenue band",
        )
    if rev is None:
        return CriterionResult(
            name="revenue_band",
            verdict=Verdict.unknown,
            weight=w,
            score=_NEUTRAL,
            reason="company revenue unavailable",
        )
    lo_ok = t.min_revenue is None or rev >= t.min_revenue
    hi_ok = t.max_revenue is None or rev <= t.max_revenue
    if lo_ok and hi_ok:
        return CriterionResult(
            name="revenue_band",
            verdict=Verdict.pass_,
            weight=w,
            score=Decimal("1.0"),
            reason=f"revenue {rev:,.0f} within band",
        )
    return CriterionResult(
        name="revenue_band",
        verdict=Verdict.fail,
        weight=w,
        score=Decimal("0.0"),
        reason=f"revenue {rev:,.0f} outside band",
    )


def _score_min_threshold(
    name: str,
    value: Decimal | None,
    minimum: Decimal | None,
    weight: Decimal,
    label: str,
    fmt: str = "{:.1%}",
) -> CriterionResult:
    """Generic 'higher is better, must clear a floor' criterion."""
    if minimum is None:
        return CriterionResult(
            name=name,
            verdict=Verdict.unknown,
            weight=weight,
            score=_NEUTRAL,
            reason=f"thesis sets no {label} floor",
        )
    if value is None:
        return CriterionResult(
            name=name,
            verdict=Verdict.unknown,
            weight=weight,
            score=_NEUTRAL,
            reason=f"{label} unavailable",
        )
    if value >= minimum:
        # Partial credit above the floor, capped — rewards comfortably-clearing
        # targets without letting one metric dominate.
        headroom = min((value - minimum) / (abs(minimum) + Decimal("0.01")), Decimal("1"))
        score = min(Decimal("1.0"), Decimal("0.7") + Decimal("0.3") * headroom)
        return CriterionResult(
            name=name,
            verdict=Verdict.pass_,
            weight=weight,
            score=score,
            reason=f"{label} {fmt.format(value)} clears floor {fmt.format(minimum)}",
        )
    return CriterionResult(
        name=name,
        verdict=Verdict.fail,
        weight=weight,
        score=Decimal("0.0"),
        reason=f"{label} {fmt.format(value)} below floor {fmt.format(minimum)}",
    )


def _score_max_threshold(
    name: str,
    value: Decimal | None,
    maximum: Decimal | None,
    weight: Decimal,
    label: str,
    fmt: str = "{:.2f}",
) -> CriterionResult:
    """Generic 'lower is better, must stay under a ceiling' criterion."""
    if maximum is None:
        return CriterionResult(
            name=name,
            verdict=Verdict.unknown,
            weight=weight,
            score=_NEUTRAL,
            reason=f"thesis sets no {label} ceiling",
        )
    if value is None:
        return CriterionResult(
            name=name,
            verdict=Verdict.unknown,
            weight=weight,
            score=_NEUTRAL,
            reason=f"{label} unavailable",
        )
    if value <= maximum:
        room = min((maximum - value) / (abs(maximum) + Decimal("0.01")), Decimal("1"))
        score = min(Decimal("1.0"), Decimal("0.7") + Decimal("0.3") * room)
        return CriterionResult(
            name=name,
            verdict=Verdict.pass_,
            weight=weight,
            score=score,
            reason=f"{label} {fmt.format(value)} under ceiling {fmt.format(maximum)}",
        )
    return CriterionResult(
        name=name,
        verdict=Verdict.fail,
        weight=weight,
        score=Decimal("0.0"),
        reason=f"{label} {fmt.format(value)} over ceiling {fmt.format(maximum)}",
    )


def score(company: Company, thesis: InvestmentThesis) -> ThesisFit:
    """Score one company against one thesis. Pure and deterministic."""
    exclusions = _hard_exclusions(company, thesis)
    if exclusions:
        return ThesisFit(
            company_name=company.name,
            thesis_name=thesis.name,
            hard_failed=True,
            overall_score=Decimal("0"),
            criteria=[],
            notes=exclusions,
        )

    criteria = [
        _score_revenue_band(company, thesis),
        _score_min_threshold(
            "revenue_growth",
            company.financials.revenue_growth,
            thesis.min_revenue_growth,
            _WEIGHTS["revenue_growth"],
            "revenue growth",
        ),
        _score_min_threshold(
            "ebitda_margin",
            company.financials.ebitda_margin,
            thesis.min_ebitda_margin,
            _WEIGHTS["ebitda_margin"],
            "EBITDA margin",
        ),
        _score_max_threshold(
            "net_leverage",
            company.financials.net_leverage,
            thesis.max_net_leverage,
            _WEIGHTS["net_leverage"],
            "net leverage",
        ),
        _score_max_threshold(
            "valuation",
            company.ev_to_ebitda,
            thesis.max_ev_ebitda,
            _WEIGHTS["valuation"],
            "EV/EBITDA",
        ),
    ]

    total_weight = sum((cr.weight for cr in criteria), Decimal(0))
    weighted = sum((cr.weighted_score for cr in criteria), Decimal(0))
    overall = (weighted / total_weight * Decimal(100)) if total_weight else Decimal(0)

    notes = []
    unknown = [cr.name for cr in criteria if cr.verdict is Verdict.unknown]
    if unknown:
        notes.append("Scored with incomplete data; treated as neutral: " + ", ".join(unknown))

    return ThesisFit(
        company_name=company.name,
        thesis_name=thesis.name,
        hard_failed=False,
        overall_score=overall.quantize(Decimal("0.1")),
        criteria=criteria,
        notes=notes,
    )
