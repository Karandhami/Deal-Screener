"""End-to-end screening pipeline.

Wires the pieces together while keeping each one swappable:

    DataSource -> scoring.engine -> Synthesizer -> ScreenedDeal

The pipeline itself holds no business logic; it is a thin coordinator. That
separation is deliberate — it keeps the testable logic in `scoring` and the
prose in `agents`, and makes this orchestrator trivial to reason about.
"""

from __future__ import annotations

from dataclasses import dataclass

from dealscreener.agents.synthesizer import Synthesizer, TemplateSynthesizer
from dealscreener.ingestion.base import DataSource
from dealscreener.models.domain import InvestmentThesis
from dealscreener.models.results import ThesisFit
from dealscreener.scoring.engine import score


@dataclass
class ScreenedDeal:
    fit: ThesisFit
    memo: str


class ScreeningPipeline:
    def __init__(
        self,
        source: DataSource,
        synthesizer: Synthesizer | None = None,
    ) -> None:
        self._source = source
        self._synth = synthesizer or TemplateSynthesizer()

    def run(self, thesis: InvestmentThesis, query: str = "") -> list[ScreenedDeal]:
        companies = self._source.fetch(query)
        deals: list[ScreenedDeal] = []
        for company in companies:
            fit = score(company, thesis)
            memo = self._synth.write_memo(fit, company.description)
            deals.append(ScreenedDeal(fit=fit, memo=memo))
        # Rank: clean targets by score desc, hard-failed sink to the bottom.
        deals.sort(
            key=lambda d: (not d.fit.hard_failed, d.fit.overall_score),
            reverse=True,
        )
        return deals
