"""Core domain models for the deal screening engine.

The two central concepts:
  - InvestmentThesis: the mandate a fund screens against (sector focus,
    size band, growth thresholds, exclusions).
  - Company: a normalised target the engine evaluates.

Design choices worth noting:
  - Money is modelled in a single reporting currency (USD) as Decimal to
    avoid float drift on financial figures. Conversion is a caller concern.
  - Optional financial fields are genuinely optional — real filings have
    gaps, and the scoring engine must degrade gracefully rather than crash.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class Sector(str, Enum):
    technology = "technology"
    financials = "financials"
    healthcare = "healthcare"
    industrials = "industrials"
    consumer = "consumer"
    energy = "energy"
    materials = "materials"
    real_estate = "real_estate"
    utilities = "utilities"
    communication = "communication"


class Financials(BaseModel):
    """A single period of company financials, all in USD.

    Every field is optional because incomplete data is the norm, not the
    exception. Downstream scoring inspects which fields are present.
    """

    revenue: Decimal | None = Field(default=None, ge=0)
    ebitda: Decimal | None = Field(default=None)
    net_income: Decimal | None = Field(default=None)
    total_debt: Decimal | None = Field(default=None, ge=0)
    cash: Decimal | None = Field(default=None, ge=0)

    # Year-over-year growth, expressed as a fraction (0.25 == 25%).
    revenue_growth: Decimal | None = Field(default=None)
    ebitda_growth: Decimal | None = Field(default=None)

    @property
    def ebitda_margin(self) -> Decimal | None:
        if self.revenue and self.revenue > 0 and self.ebitda is not None:
            return self.ebitda / self.revenue
        return None

    @property
    def net_leverage(self) -> Decimal | None:
        """Net debt / EBITDA. None when it cannot be computed meaningfully."""
        if self.ebitda is None or self.ebitda <= 0:
            return None
        if self.total_debt is None:
            return None
        net_debt = self.total_debt - (self.cash or Decimal(0))
        return net_debt / self.ebitda


class Company(BaseModel):
    name: str
    sector: Sector
    country: str = Field(min_length=2)
    description: str = ""
    financials: Financials = Field(default_factory=Financials)
    enterprise_value: Decimal | None = Field(default=None, ge=0)
    source_urls: list[str] = Field(default_factory=list)

    @property
    def ev_to_ebitda(self) -> Decimal | None:
        f = self.financials
        if self.enterprise_value is None or f.ebitda is None or f.ebitda <= 0:
            return None
        return self.enterprise_value / f.ebitda


class InvestmentThesis(BaseModel):
    """A fund's screening mandate. Authored by the user, not generated.

    Thresholds are intentionally explicit so the scoring engine stays a
    pure, auditable function of (Company, Thesis).
    """

    name: str
    target_sectors: list[Sector] = Field(min_length=1)
    excluded_countries: list[str] = Field(default_factory=list)
    excluded_keywords: list[str] = Field(
        default_factory=list,
        description="Business-description terms that hard-fail a target "
        "(e.g. 'tobacco', 'gambling').",
    )

    min_revenue: Decimal | None = Field(default=None, ge=0)
    max_revenue: Decimal | None = Field(default=None, ge=0)
    min_revenue_growth: Decimal | None = Field(default=None)
    min_ebitda_margin: Decimal | None = Field(default=None)
    max_net_leverage: Decimal | None = Field(default=None)
    max_ev_ebitda: Decimal | None = Field(default=None)

    @field_validator("excluded_countries", "target_sectors", mode="before")
    @classmethod
    def _dedupe(cls, v: list) -> list:
        # Preserve order while removing duplicates — readable diffs in tests.
        seen, out = set(), []
        for item in v or []:
            if item not in seen:
                seen.add(item)
                out.append(item)
        return out

    @model_validator(mode="after")
    def _check_revenue_band(self) -> InvestmentThesis:
        if (
            self.min_revenue is not None
            and self.max_revenue is not None
            and self.min_revenue > self.max_revenue
        ):
            raise ValueError("min_revenue cannot exceed max_revenue")
        return self
