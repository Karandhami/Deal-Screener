"""Streamlit review UI for screened deals.

A thin front-end over ScreeningPipeline. An analyst loads a thesis, runs the
screen, and reviews ranked candidates with their memos and per-criterion
breakdown. No business logic lives here.

Run:
    streamlit run src/dealscreener/ui/app.py
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from dealscreener.ingestion.base import MockDataSource
from dealscreener.models.domain import InvestmentThesis
from dealscreener.pipeline import ScreeningPipeline

st.set_page_config(page_title="Deal Screening Engine", layout="wide")
st.title("PE / M&A Deal Screening Engine")
st.caption(
    "Thesis-driven screening. All financial figures are computed "
    "deterministically; narrative is synthesised separately."
)

DATA_DIR = Path(__file__).resolve().parents[3] / "data"

with st.sidebar:
    st.header("Mandate")
    thesis_path = st.text_input("Thesis JSON", str(DATA_DIR / "example_thesis.json"))
    data_path = st.text_input("Companies JSON", str(DATA_DIR / "mock" / "companies.json"))
    query = st.text_input("Filter (optional)", "")
    run = st.button("Run screen", type="primary")

if run:
    thesis = InvestmentThesis.model_validate_json(Path(thesis_path).read_text())
    deals = ScreeningPipeline(MockDataSource(data_path)).run(thesis, query=query)

    st.subheader(f"Results — {thesis.name}")
    for d in deals:
        with st.expander(
            f"{d.fit.company_name}  ·  {d.fit.overall_score}/100  ·  {d.fit.recommendation}",
            expanded=not d.fit.hard_failed,
        ):
            st.write(d.memo)
            if d.fit.criteria:
                st.table(
                    [
                        {
                            "Criterion": c.name.replace("_", " "),
                            "Verdict": c.verdict.value,
                            "Reason": c.reason,
                        }
                        for c in d.fit.criteria
                    ]
                )
