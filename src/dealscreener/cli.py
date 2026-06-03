"""Command-line entry point for a screening run.

Usage:
    python -m dealscreener.cli --thesis thesis.json --data data/mock/companies.json

Kept small on purpose: it parses inputs, runs the pipeline, prints a ranked
table. The Streamlit UI and FastAPI service are alternative front-ends over
the same `ScreeningPipeline`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from dealscreener.ingestion.base import MockDataSource
from dealscreener.models.domain import InvestmentThesis
from dealscreener.pipeline import ScreeningPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a deal screening pass.")
    parser.add_argument("--thesis", required=True, help="Path to a thesis JSON file")
    parser.add_argument("--data", required=True, help="Path to a companies JSON file")
    parser.add_argument("--query", default="", help="Optional name/description filter")
    parser.add_argument("--memo", action="store_true", help="Print the top memo")
    args = parser.parse_args()

    thesis = InvestmentThesis.model_validate_json(Path(args.thesis).read_text())
    pipeline = ScreeningPipeline(MockDataSource(args.data))
    deals = pipeline.run(thesis, query=args.query)

    print(f"\nScreening against: {thesis.name}\n" + "-" * 60)
    for d in deals:
        print(f"{d.fit.overall_score:>6}  {d.fit.recommendation:<38}  {d.fit.company_name}")

    if args.memo and deals:
        print("\nTop memo\n" + "-" * 60)
        print(deals[0].memo)


if __name__ == "__main__":
    main()
