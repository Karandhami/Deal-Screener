# Deal Screening Engine

Thesis-driven screening for PE / M&A sourcing. You author an investment
mandate; the engine screens a pipeline of targets against it, ranks them, and
drafts an Investment Committee (IC) screening memo for each — compressing the
first-pass work an analyst would otherwise do by hand.

> **Scope note.** This is a portfolio-grade, production-*minded* system: clean
> architecture, deterministic core, tests, containerised, runnable offline with
> zero credentials. It is **not** a production deployment — see
> [Production hardening path](#production-hardening-path) for the honest gap.

---

## The one design decision that matters

**The language model never produces a number.**

Every financial figure — revenue band checks, growth, EBITDA margin, leverage,
EV/EBITDA — is computed in a pure, deterministic scoring function. The LLM
receives the already-scored result and writes *only the narrative around it*.

This is deliberate. Screening output that drives capital allocation cannot
contain hallucinated figures. Separating the deterministic scoring from the
generative prose is what lets the memos be trustworthy, and what makes the core
logic unit-testable.

---

## Architecture

```
                author-defined
                     │
        InvestmentThesis (typed, validated)
                     │
   DataSource ──▶ Company ──▶ scoring.engine ──▶ ThesisFit ──▶ Synthesizer ──▶ memo
   (pluggable)    (normalised)  (pure, tested)   (structured)  (prose only)
                                       │
                              ScreeningPipeline (ranks)
                                       │
                     ┌─────────────────┼─────────────────┐
                   CLI             Streamlit UI        (FastAPI)
```

- **`models/`** — `InvestmentThesis`, `Company`, `Financials` and the scoring
  result types. Money is `Decimal`; optional fields are genuinely optional.
- **`ingestion/`** — a `DataSource` protocol plus three adapters:
  `MockDataSource` (offline sample), `SecEdgarDataSource` (real filings via
  the SEC's free `companyfacts` API), and `parse_deal_file` (CSV/XLSX upload).
  Swapping a licensed feed in later touches nothing downstream.
- **`scoring/engine.py`** — the analytical core. Pure `(Company, Thesis) -> ThesisFit`.
  No LLM, no I/O. Missing data is scored neutrally, never as a failure.
- **`agents/synthesizer.py`** — narrative synthesis. `TemplateSynthesizer`
  (deterministic, offline) and `LLMSynthesizer` (wraps a chat model, instructed
  never to introduce a figure).
- **`pipeline.py`** — a thin coordinator that ranks screened deals.

---

## Quickstart

### Backend (the engine + API)

```bash
pip install -e ".[api,dev]"
pytest                       # deterministic core + pipeline tests

# Start the API (serves the React app)
uvicorn dealscreener.api.main:app --reload --port 8000
```

### Frontend (the investor dashboard)

```bash
cd frontend
npm install
npm run dev                  # opens http://localhost:5173
```

With both running, open the dashboard. Three data modes:

- **Sample** — the bundled mock universe (works offline, instant).
- **SEC Live** — enter tickers (e.g. `MSFT, CRM, NOW`); pulls real filings
  from SEC EDGAR. No API key needed.
- **Upload** — drop a CSV/XLSX deal list and screen your own pipeline.

### CLI (headless)

```bash
python -m dealscreener.cli \
    --thesis data/example_thesis.json \
    --data data/mock/companies.json --memo
```

### Docker

```bash
docker build -t deal-screener .
docker run -p 8501:8501 deal-screener
```

---

## Scoring model

1. **Hard exclusions** (sector / country / keyword) are checked first. Any hit
   short-circuits to a hard fail — no point scoring a target that violates the
   mandate outright.
2. Each remaining criterion produces a `0..1` score with a documented weight
   and a human-readable reason.
3. **Missing data → neutral `0.5`**, not zero. Absent information should neither
   reward nor unfairly penalise a target; it should be flagged as a caveat.
4. `overall_score` is the weighted average, rescaled to `0..100`, with a
   recommendation band (`ADVANCE` ≥ 70, `REVIEW` ≥ 50, else `PASS`).

Weights live in one place (`_WEIGHTS`) and are documented so the behaviour is
explainable — important when the output informs a real decision.

---

## Testing

The deterministic core is the test target: hard-exclusion short-circuiting,
neutral handling of missing data, boundary behaviour on thresholds, and the
`0..100` invariant. Run `pytest --cov=dealscreener`.

---

## Production hardening path

What a genuine production deployment at a fund would add, and why each is out
of scope here:

| Area | Production requirement |
|---|---|
| Data | Licensed feeds (CapitalIQ / PitchBook) under contract, with lineage |
| Access | SSO + role-based access control |
| Audit | Immutable run log meeting compliance review |
| Safety | Human-in-the-loop sign-off before any memo circulates |
| LLM risk | Numeric facts pulled deterministically — already enforced here |

Knowing where these seams are is the point: the architecture is built so each
can be added without rewriting the core.

---

## Project layout

```
src/dealscreener/
  models/        domain + result types
  ingestion/     DataSource protocol + mock adapter
  scoring/       deterministic engine (the core)
  agents/        narrative synthesis (template + LLM)
  ui/            Streamlit review app
  pipeline.py    orchestrator
  cli.py         command-line entry point
tests/           scoring engine tests
data/            example thesis + mock companies
```
