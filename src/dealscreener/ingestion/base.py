"""Ingestion adapters convert an external data source into Company objects.

The design goal is pluggability: the rest of the system depends only on the
DataSource protocol, never on a concrete provider. That is what lets the
"production hardening path" later swap a mock source for a licensed feed
(CapIQ, PitchBook) without touching scoring, agents, or the API.

Two pieces here:
  - DataSource: the protocol every adapter implements.
  - MockDataSource: a deterministic, offline adapter reading bundled JSON,
    so the whole pipeline runs locally with zero credentials.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

from dealscreener.models.domain import Company


@runtime_checkable
class DataSource(Protocol):
    """Any source of candidate companies.

    Implementations should be resilient: a single bad record must not abort
    the whole batch. Return what could be parsed; log the rest.
    """

    def fetch(self, query: str) -> list[Company]: ...


class MockDataSource:
    """Offline adapter backed by a bundled JSON file.

    Deterministic by construction, which makes the end-to-end flow testable
    and the demo reproducible. The `query` is treated as a case-insensitive
    substring filter over company name and description.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def fetch(self, query: str) -> list[Company]:
        raw = json.loads(self._path.read_text())
        companies: list[Company] = []
        for record in raw:
            try:
                companies.append(Company.model_validate(record))
            except Exception:  # noqa: BLE001 - one bad record shouldn't kill the batch
                # In a real adapter this would emit a structured warning log.
                continue
        if not query:
            return companies
        q = query.lower()
        return [c for c in companies if q in c.name.lower() or q in c.description.lower()]
