"""FastAPI service exposing the screening engine to the frontend.

Endpoints:
  GET  /api/health           liveness
  GET  /api/thesis/default   the example mandate (seeds the UI form)
  POST /api/screen/mock      screen the bundled mock universe
  POST /api/screen/tickers   screen real SEC EDGAR filers by ticker
  POST /api/screen/upload    screen an uploaded CSV/XLSX deal list

Every endpoint runs the same deterministic pipeline; only the DataSource
differs. Responses are plain JSON the React app renders into charts + memos.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from dealscreener.agents.synthesizer import TemplateSynthesizer
from dealscreener.ingestion.base import MockDataSource
from dealscreener.ingestion.file_upload import parse_deal_file
from dealscreener.ingestion.sec_edgar import SecEdgarDataSource
from dealscreener.models.domain import Company, InvestmentThesis
from dealscreener.models.results import ThesisFit
from dealscreener.pipeline import ScreenedDeal
from dealscreener.scoring.engine import score

DATA_DIR = Path(__file__).resolve().parents[3] / "data"

app = FastAPI(title="Deal Screening Engine", version="0.1.0")

# Allowed origins come from an env var in production (your Vercel URL), and
# fall back to "*" for local development convenience.
_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
_allow_origins = [o.strip() for o in _origins_env.split(",")] if _origins_env != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

_synth = TemplateSynthesizer()


class DealOut(BaseModel):
    fit: ThesisFit
    memo: str
    company: Company

    @classmethod
    def from_deal(cls, deal: ScreenedDeal, company: Company) -> DealOut:
        return cls(fit=deal.fit, memo=deal.memo, company=company)


class ScreenResponse(BaseModel):
    thesis_name: str
    deals: list[DealOut]
    summary: dict


def _run(thesis: InvestmentThesis, companies: list[Company]) -> ScreenResponse:
    """Score an explicit company list (so we can return the company alongside)."""
    deals: list[DealOut] = []
    for c in companies:
        fit = score(c, thesis)
        memo = _synth.write_memo(fit, c.description)
        deals.append(DealOut(fit=fit, memo=memo, company=c))
    deals.sort(key=lambda d: (not d.fit.hard_failed, d.fit.overall_score), reverse=True)

    advanced = sum(1 for d in deals if d.fit.recommendation.startswith("ADVANCE"))
    review = sum(1 for d in deals if d.fit.recommendation.startswith("REVIEW"))
    passed = len(deals) - advanced - review
    return ScreenResponse(
        thesis_name=thesis.name,
        deals=deals,
        summary={
            "total": len(deals),
            "advance": advanced,
            "review": review,
            "pass": passed,
        },
    )


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/thesis/default")
def default_thesis() -> InvestmentThesis:
    return InvestmentThesis.model_validate_json((DATA_DIR / "example_thesis.json").read_text())


@app.post("/api/screen/mock")
def screen_mock(thesis: InvestmentThesis) -> ScreenResponse:
    companies = MockDataSource(DATA_DIR / "mock" / "companies.json").fetch("")
    return _run(thesis, companies)


class TickerRequest(BaseModel):
    thesis: InvestmentThesis
    tickers: str  # comma-separated, e.g. "MSFT, CRM, NOW"


@app.post("/api/screen/tickers")
def screen_tickers(req: TickerRequest) -> ScreenResponse:
    companies = SecEdgarDataSource().fetch(req.tickers)
    return _run(req.thesis, companies)


@app.post("/api/screen/upload")
async def screen_upload(
    file: UploadFile = File(...),  # noqa: B008 - idiomatic FastAPI dependency default
    thesis_json: str = Form(...),
) -> ScreenResponse:
    thesis = InvestmentThesis.model_validate_json(thesis_json)
    content = await file.read()
    companies = parse_deal_file(content, file.filename or "deals.csv")
    return _run(thesis, companies)
