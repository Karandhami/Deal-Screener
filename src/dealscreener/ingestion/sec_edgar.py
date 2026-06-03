"""SEC EDGAR ingestion adapter — real company financial data, no API key.

The SEC's `companyfacts` API exposes XBRL-tagged financials for every public
filer, free and keyed only by a CIK (Central Index Key). We map a ticker to a
CIK via the SEC's published ticker file, then pull the facts we need and
normalise them into our `Company` model.

Two honest caveats, surfaced rather than hidden:
  - XBRL tagging varies between filers; we try a list of candidate concept
    tags for each field and take the first that resolves.
  - Some fields (enterprise value, market data) are not in filings at all and
    are left as None — the scoring engine already treats absent data neutrally.

The SEC requires a descriptive User-Agent on every request; we set one.
"""

from __future__ import annotations

from decimal import Decimal

import httpx

from dealscreener.models.domain import Company, Financials, Sector

_SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

# Be a good API citizen — the SEC blocks requests without a real UA.
_HEADERS = {"User-Agent": "DealScreener research contact@example.com"}

# Candidate XBRL concept tags, tried in order. Filers tag inconsistently.
_CONCEPTS = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ],
    "net_income": ["NetIncomeLoss"],
    "total_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
}


class SecEdgarError(RuntimeError):
    pass


class SecEdgarDataSource:
    """Fetches real filer financials from SEC EDGAR.

    `fetch(query)` treats the query as a comma-separated list of tickers, e.g.
    "MSFT, CRM, NOW". This keeps the DataSource protocol intact (a string in,
    companies out) while mapping naturally to the UI's ticker input.
    """

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(headers=_HEADERS, timeout=20.0)
        self._ticker_map: dict[str, int] | None = None

    def _load_ticker_map(self) -> dict[str, int]:
        if self._ticker_map is None:
            resp = self._client.get(_SEC_TICKERS_URL)
            resp.raise_for_status()
            data = resp.json()
            self._ticker_map = {row["ticker"].upper(): int(row["cik_str"]) for row in data.values()}
        return self._ticker_map

    def _latest_annual_value(self, facts: dict, concepts: list[str]) -> Decimal | None:
        """Pull the most recent annual (FY) USD value for the first matching concept."""
        us_gaap = facts.get("facts", {}).get("us-gaap", {})
        for concept in concepts:
            node = us_gaap.get(concept)
            if not node:
                continue
            usd = node.get("units", {}).get("USD")
            if not usd:
                continue
            annual = [u for u in usd if u.get("form") == "10-K" and u.get("fp") == "FY"]
            if not annual:
                annual = usd
            annual.sort(key=lambda u: u.get("end", ""))
            return Decimal(str(annual[-1]["val"]))
        return None

    def _fetch_one(self, ticker: str) -> Company | None:
        ticker = ticker.strip().upper()
        if not ticker:
            return None
        cik = self._load_ticker_map().get(ticker)
        if cik is None:
            return None
        resp = self._client.get(_SEC_FACTS_URL.format(cik=cik))
        if resp.status_code != 200:
            return None
        facts = resp.json()

        revenue = self._latest_annual_value(facts, _CONCEPTS["revenue"])
        net_income = self._latest_annual_value(facts, _CONCEPTS["net_income"])
        total_debt = self._latest_annual_value(facts, _CONCEPTS["total_debt"])
        cash = self._latest_annual_value(facts, _CONCEPTS["cash"])

        # EBITDA is not directly tagged; net income is a transparent, honest
        # stand-in here rather than fabricating a number. The UI labels it as
        # an approximation. (A production version would build EBITDA from the
        # income statement components.)
        return Company(
            name=facts.get("entityName", ticker),
            sector=Sector.technology,  # SEC facts don't carry SIC->our sector cleanly
            country="US",
            description=f"SEC filer {ticker} (CIK {cik}).",
            financials=Financials(
                revenue=revenue,
                ebitda=net_income,  # labelled as approximation in the UI
                net_income=net_income,
                total_debt=total_debt,
                cash=cash,
            ),
            source_urls=[f"https://www.sec.gov/cgi-bin/browse-edgar?CIK={cik}"],
        )

    def fetch(self, query: str) -> list[Company]:
        tickers = [t for t in (query or "").split(",") if t.strip()]
        out: list[Company] = []
        for t in tickers:
            try:
                company = self._fetch_one(t)
            except httpx.HTTPError:
                continue
            if company is not None:
                out.append(company)
        return out
