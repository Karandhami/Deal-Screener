"""Narrative synthesis for the IC memo.

Hard architectural rule for this project: the language model NEVER produces
a number. It receives the already-computed ThesisFit (all figures
deterministic) and writes only the prose around them. This is what lets us
claim the memos are free of hallucinated financials.

The Synthesizer protocol has two implementations:
  - TemplateSynthesizer: deterministic, offline, zero-credential. Good enough
    to run the whole pipeline and demo it. Also the test target.
  - LLMSynthesizer: wraps a chat model for richer prose. It is given ONLY the
    structured fit object and is instructed to never introduce new figures.

Swapping between them is a one-line change at the call site, which is the
point of the abstraction.
"""

from __future__ import annotations

from typing import Protocol

from dealscreener.models.results import ThesisFit


class Synthesizer(Protocol):
    def write_memo(self, fit: ThesisFit, company_description: str) -> str: ...


class TemplateSynthesizer:
    """Deterministic memo prose. No network, no model, fully testable."""

    def write_memo(self, fit: ThesisFit, company_description: str) -> str:
        if fit.hard_failed:
            reasons = "; ".join(fit.notes) or "fails thesis exclusions"
            return (
                f"{fit.company_name} is screened OUT against the "
                f"'{fit.thesis_name}' mandate. Rationale: {reasons}."
            )

        strengths = [c for c in fit.criteria if c.verdict.value == "pass"]
        weaknesses = [c for c in fit.criteria if c.verdict.value == "fail"]

        parts: list[str] = []
        parts.append(
            f"{fit.company_name} screens at {fit.overall_score}/100 against "
            f"the '{fit.thesis_name}' mandate — {fit.recommendation}."
        )
        if company_description:
            parts.append(f"Business: {company_description}.")
        if strengths:
            s = "; ".join(f"{c.name.replace('_', ' ')} ({c.reason})" for c in strengths)
            parts.append(f"Supporting the thesis: {s}.")
        if weaknesses:
            w = "; ".join(f"{c.name.replace('_', ' ')} ({c.reason})" for c in weaknesses)
            parts.append(f"Against the thesis: {w}.")
        if fit.notes:
            parts.append("Data caveats: " + " ".join(fit.notes))
        return " ".join(parts)


_LLM_SYSTEM_PROMPT = (
    "You are an investment analyst drafting the narrative of an IC screening "
    "memo. You will be given a structured screening result with all figures "
    "already computed. Write a concise, balanced memo. STRICT RULE: do not "
    "introduce, alter, or estimate any number, ratio, or figure that is not "
    "already present in the structured result. Prose only."
)


class LLMSynthesizer:
    """Wraps a chat model. Falls back to the template if no client is wired.

    Kept intentionally thin: the value is the prompt discipline and the
    structured input, not provider-specific plumbing.
    """

    def __init__(self, client=None, model: str = "claude-3-5-sonnet") -> None:
        self._client = client
        self._model = model
        self._fallback = TemplateSynthesizer()

    def write_memo(self, fit: ThesisFit, company_description: str) -> str:
        if self._client is None:
            return self._fallback.write_memo(fit, company_description)
        user_payload = fit.model_dump_json(indent=2)
        # Provider-agnostic call signature; adapt to the concrete SDK in use.
        response = self._client.create(
            model=self._model,
            system=_LLM_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_payload}],
        )
        return response
