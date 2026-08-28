"""JSONL run ledger: one JSON object per line, one line per audition run.

Append forever so a repo accumulates a history of what each model scored.
Nothing calls this module yet — the CLI wires it up in a later phase.
Each record carries the freeze state (bar-hash check) the run was made under.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .freeze import FreezeCheck
from .runner import RunResults
from .scoring import PairVerdict

LEDGER_FILENAME = "ledger.jsonl"


def run_record(
    results: RunResults,
    verdicts: Sequence[PairVerdict],
    *,
    manifest: str,
    freeze: FreezeCheck | None = None,
) -> dict[str, Any]:
    """A JSON-safe dict for one audition run.

    Holds ``started_at``, ``finished_at``, ``manifest``, ``cases``,
    ``met_bar``, ``pairs``, and ``freeze`` — one entry per verdict with the
    summary's fields plus ``met`` and ``reasons``.  The ``freeze`` key records
    the bar-hash check state for this run.
    """
    pairs: list[dict[str, Any]] = []
    for v in verdicts:
        d = asdict(v.summary)
        d["met"] = v.met
        d["reasons"] = list(v.reasons)  # list survives JSON; tuple does not
        pairs.append(d)

    met_bar = all(v.met for v in verdicts)

    freeze_record: dict[str, Any] | None = None
    if freeze is not None:
        freeze_record = {
            "status": freeze.status.value,
            "bar_hash": freeze.current_hash,
            "frozen_hash": freeze.frozen_hash,
        }

    return {
        "started_at": results.started_at,
        "finished_at": results.finished_at,
        "manifest": manifest,
        "cases": len(results.outcomes),
        "met_bar": met_bar,
        "pairs": pairs,
        "freeze": freeze_record,
    }


def append_run(path: str | Path, record: dict[str, Any]) -> None:
    """Append one JSON line to *path*, creating the parent directory if needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def read_ledger(path: str | Path) -> list[dict[str, Any]]:
    """Every line of *path* decoded, in file order.

    A path that does not exist returns ``[]``; blank lines are skipped.
    """
    path = Path(path)
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with open(path) as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            records.append(json.loads(stripped))
    return records
