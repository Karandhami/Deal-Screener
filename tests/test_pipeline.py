"""End-to-end pipeline test.

Exercises ingestion -> scoring -> synthesis -> ranking against the bundled
mock dataset, so the wiring (not just the scoring core) is covered.
"""

from pathlib import Path

from dealscreener.agents.synthesizer import TemplateSynthesizer
from dealscreener.ingestion.base import MockDataSource
from dealscreener.models.domain import InvestmentThesis, Sector
from dealscreener.pipeline import ScreeningPipeline

DATA = Path(__file__).resolve().parents[1] / "data"


def _pipeline() -> ScreeningPipeline:
    return ScreeningPipeline(
        MockDataSource(DATA / "mock" / "companies.json"),
        TemplateSynthesizer(),
    )


def _thesis() -> InvestmentThesis:
    return InvestmentThesis.model_validate_json((DATA / "example_thesis.json").read_text())


def test_pipeline_runs_and_ranks():
    deals = _pipeline().run(_thesis())
    assert deals, "pipeline returned no deals"
    # Ranking invariant: scores are non-increasing once hard-fails sink.
    clean = [d for d in deals if not d.fit.hard_failed]
    scores = [d.fit.overall_score for d in clean]
    assert scores == sorted(scores, reverse=True)


def test_hard_fails_sink_to_bottom():
    deals = _pipeline().run(_thesis())
    # Every hard-failed deal must appear after every clean one.
    seen_fail = False
    for d in deals:
        if d.fit.hard_failed:
            seen_fail = True
        elif seen_fail:
            raise AssertionError("a clean deal ranked below a hard-failed one")


def test_memos_are_generated_for_every_deal():
    deals = _pipeline().run(_thesis())
    assert all(d.memo for d in deals)


def test_gambling_target_is_excluded():
    deals = _pipeline().run(_thesis())
    red = next(d for d in deals if d.fit.company_name == "RedStar Gaming")
    assert red.fit.hard_failed
    assert "gambling" in red.memo.lower()


def test_query_filter_narrows_results():
    deals = _pipeline().run(_thesis(), query="health")
    names = {d.fit.company_name for d in deals}
    assert "Cobalt Health" in names
    assert "Northwind Software" not in names


def test_thesis_sectors_respected():
    t = InvestmentThesis(name="tech only", target_sectors=[Sector.technology])
    deals = _pipeline().run(t)
    health = next(d for d in deals if d.fit.company_name == "Cobalt Health")
    assert health.fit.hard_failed  # healthcare outside a tech-only mandate
