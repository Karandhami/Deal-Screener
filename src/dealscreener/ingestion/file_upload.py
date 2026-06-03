"""File-upload ingestion — screen your own deal list from CSV or Excel.

Accepts a tabular file with one company per row. Column names are mapped
flexibly (case-insensitive, common aliases) so a user's existing deal
spreadsheet works without reformatting. Unparseable rows are skipped rather
than aborting the batch — partial data is better than no data in sourcing.
"""

from __future__ import annotations

import io
from decimal import Decimal, InvalidOperation

import pandas as pd

from dealscreener.models.domain import Company, Financials, Sector

# Map many possible header spellings to our canonical field names.
_ALIASES = {
    "name": {"name", "company", "company name", "target"},
    "sector": {"sector", "industry"},
    "country": {"country", "geography", "geo"},
    "description": {"description", "desc", "business", "summary"},
    "revenue": {"revenue", "sales", "turnover"},
    "ebitda": {"ebitda"},
    "net_income": {"net income", "net_income", "earnings"},
    "total_debt": {"total debt", "debt", "total_debt"},
    "cash": {"cash", "cash equivalents"},
    "revenue_growth": {"revenue growth", "rev growth", "growth", "revenue_growth"},
    "enterprise_value": {"enterprise value", "ev", "enterprise_value"},
}


def _resolve_columns(df: pd.DataFrame) -> dict[str, str]:
    """Return {canonical_field: actual_column} for columns we recognise."""
    lower = {c.lower().strip(): c for c in df.columns}
    resolved: dict[str, str] = {}
    for field, names in _ALIASES.items():
        for n in names:
            if n in lower:
                resolved[field] = lower[n]
                break
    return resolved


def _dec(value) -> Decimal | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _to_sector(value) -> Sector | None:
    if not isinstance(value, str):
        return None
    key = value.strip().lower().replace(" ", "_")
    return Sector.__members__.get(key)


def parse_deal_file(content: bytes, filename: str) -> list[Company]:
    """Parse an uploaded CSV/XLSX into Company objects, skipping bad rows."""
    buf = io.BytesIO(content)
    if filename.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(buf)
    else:
        df = pd.read_csv(buf)

    cols = _resolve_columns(df)
    if "name" not in cols:
        raise ValueError("file must contain a company name column")

    companies: list[Company] = []
    for _, row in df.iterrows():
        try:
            sector = _to_sector(row[cols["sector"]]) if "sector" in cols else None
            company = Company(
                name=str(row[cols["name"]]),
                sector=sector or Sector.technology,
                country=str(row[cols["country"]]) if "country" in cols else "US",
                description=str(row[cols["description"]]) if "description" in cols else "",
                enterprise_value=(
                    _dec(row[cols["enterprise_value"]]) if "enterprise_value" in cols else None
                ),
                financials=Financials(
                    revenue=_dec(row[cols["revenue"]]) if "revenue" in cols else None,
                    ebitda=_dec(row[cols["ebitda"]]) if "ebitda" in cols else None,
                    net_income=_dec(row[cols["net_income"]]) if "net_income" in cols else None,
                    total_debt=_dec(row[cols["total_debt"]]) if "total_debt" in cols else None,
                    cash=_dec(row[cols["cash"]]) if "cash" in cols else None,
                    revenue_growth=(
                        _dec(row[cols["revenue_growth"]]) if "revenue_growth" in cols else None
                    ),
                ),
            )
            companies.append(company)
        except Exception:  # noqa: BLE001 - skip a bad row, keep the batch
            continue
    return companies
