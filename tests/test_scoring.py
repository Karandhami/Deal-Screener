"""Tests for the deterministic scoring engine.

These cover the behaviours that matter in a screening context:
  - hard exclusions short-circuit,
  - missing data is treated neutrally (not as a failure),
  - thresholds pass/fail at the right boundaries,
  - the overall score stays in 0..100.
"""

from decimal import Decimal

import pytest

from dealscreener.models.domain import (
    Company,
    Financials,
    InvestmentThesis,
    Sector,
)
from dealscreener.models.results import Verdict
from dealscreener.scoring.engine import score


@pytest.fixture
def thesis() -> InvestmentThesis:
    return InvestmentThesis(
        name="Mid-market software",
        target_sectors=[Sector.technology],
        excluded_countries=["RU"],
        excluded_keywords=["gambling"],
        min_revenue=Decimal("50_000_000"),
        max_revenue=Decimal("500_000_000"),
        min_revenue_growth=Decimal("0.15"),
        min_ebitda_margin=Decimal("0.20"),
        max_net_leverage=Decimal("3.0"),
        max_ev_ebitda=Decimal("15"),
    )


def _good_company() -> Company:
    return Company(
        name="Acme SaaS",
        sector=Sector.technology,
        country="US",
        description="B2B workflow software",
        enterprise_value=Decimal("1_200_000_000"),
        financials=Financials(
            revenue=Decimal("200_000_000"),
            ebitda=Decimal("60_000_000"),
            total_debt=Decimal("100_000_000"),
            cash=Decimal("40_000_000"),
            revenue_growth=Decimal("0.30"),
        ),
    )


def test_strong_fit_advances(thesis):
    result = score(_good_company(), thesis)
    assert not result.hard_failed
    assert result.overall_score >= Decimal("70")
    assert result.recommendation.startswith("ADVANCE")


def test_sector_exclusion_hard_fails(thesis):
    c = _good_company()
    c.sector = Sector.energy
    result = score(c, thesis)
    assert result.hard_failed
    assert result.overall_score == Decimal("0")
    assert any("sector" in n for n in result.notes)


def test_excluded_country_hard_fails(thesis):
    c = _good_company()
    c.country = "ru"  # case-insensitive match expected
    result = score(c, thesis)
    assert result.hard_failed


def test_excluded_keyword_hard_fails(thesis):
    c = _good_company()
    c.description = "Online gambling platform"
    result = score(c, thesis)
    assert result.hard_failed


def test_missing_data_is_neutral_not_failure(thesis):
    """A company with no financials should not score zero — unknowns are neutral."""
    c = Company(name="Opaque Co", sector=Sector.technology, country="US")
    result = score(c, thesis)
    assert not result.hard_failed
    # All real criteria unknown -> neutral 0.5 -> 50/100.
    assert result.overall_score == Decimal("50.0")
    assert all(cr.verdict is Verdict.unknown for cr in result.criteria)


def test_revenue_below_band_fails_that_criterion(thesis):
    c = _good_company()
    c.financials.revenue = Decimal("10_000_000")  # below 50m floor
    result = score(c, thesis)
    band = next(cr for cr in result.criteria if cr.name == "revenue_band")
    assert band.verdict is Verdict.fail


def test_score_bounded(thesis):
    result = score(_good_company(), thesis)
    assert Decimal("0") <= result.overall_score <= Decimal("100")


def test_thesis_rejects_inverted_revenue_band():
    with pytest.raises(ValueError):
        InvestmentThesis(
            name="bad",
            target_sectors=[Sector.technology],
            min_revenue=Decimal("100"),
            max_revenue=Decimal("10"),
        )
