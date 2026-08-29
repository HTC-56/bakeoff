"""The report: results.json, and one self-contained HTML file.

SPEC.md feature 6. A run produces two artefacts and an exit code. ``results.json`` is
the machine-readable record — every pair, every case, the freeze state, the verdict —
and the HTML report is a *rendering* of exactly that file: nothing is measured here,
nothing is fetched here, and no clock is read while rendering. That is what makes
``bakeoff report`` a re-render rather than a re-run, and what lets the same results
produce the same bytes on any machine.

The pipeline the CLI will wire up::

    run_audition -> summarize -> judge          (runner, scoring)
      -> results_document(...)                  (this module: the JSON payload)
        -> write_results(path, document)        (results.json on disk)
        -> render_report(document)              (report.html, one file, no requests)

Two rules shape everything below.

**Self-contained.** The page has inline CSS, no JavaScript, no ``<link>``, no
``<script>``, no CDN and no web fonts — a report mailed as a single attachment must
render on a machine with no network. Drill-down is ``<details>``, not script.

**Purely a function of the document.** ``generated_at`` is stamped into the document
when it is *built*, never when it is rendered, so re-rendering an old results.json
cannot silently re-date it. The freeze block is carried through untouched, which is
how a REBARRED run stays branded REBARRED in every later re-render.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

from .errors import ConfigError
from .freeze import FreezeCheck
from .runner import CaseOutcome, RunResults
from .scoring import PairVerdict, exit_code

REPORT_VERSION = 1
"""Bumped only when the shape of results.json changes; older files then fail to read."""

RESULTS_FILENAME = "results.json"
REPORT_FILENAME = "report.html"


class ReportError(ConfigError):
    """results.json is missing, is not JSON, or was written by another version."""


# --- the document -----------------------------------------------------------


def _utc_now() -> str:
    """The current time as an ISO-8601 UTC string, seconds resolution."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _pair_entry(verdict: PairVerdict) -> dict[str, Any]:
    """One scoreboard row: the measured summary, the bar it was held to, the verdict."""
    entry: dict[str, Any] = asdict(verdict.summary)
    entry["thresholds"] = verdict.thresholds.model_dump(mode="json")
    entry["met"] = verdict.met
    entry["reasons"] = list(verdict.reasons)  # a list survives JSON; a tuple does not
    return entry


def _case_entry(outcome: CaseOutcome) -> dict[str, Any]:
    """One drill-down row: the whole outcome, with its two properties written out."""
    entry: dict[str, Any] = asdict(outcome)
    entry["total_tokens"] = outcome.total_tokens
    entry["errored"] = outcome.errored
    return entry


def _freeze_entry(freeze: FreezeCheck | None) -> dict[str, Any] | None:
    """The freeze check as plain JSON — ``None`` when the run recorded no check."""
    if freeze is None:
        return None
    return {
        "status": freeze.status.value,
        "bar_hash": freeze.current_hash,
        "frozen_hash": freeze.frozen_hash,
    }


def results_document(
    results: RunResults,
    verdicts: Sequence[PairVerdict],
    *,
    manifest: str,
    freeze: FreezeCheck | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Everything the report needs, as JSON-safe data. Nothing here reads the disk.

    ``manifest`` is the manifest's file *name*, not a path — a committed results.json
    must not leak one machine's layout. ``generated_at`` is injectable so a test (and
    a re-render) can be byte-stable.
    """
    return {
        "version": REPORT_VERSION,
        "generated_at": generated_at if generated_at is not None else _utc_now(),
        "manifest": manifest,
        "started_at": results.started_at,
        "finished_at": results.finished_at,
        "freeze": _freeze_entry(freeze),
        "met_bar": all(verdict.met for verdict in verdicts),
        "exit_code": exit_code(verdicts),
        "pairs": [_pair_entry(verdict) for verdict in verdicts],
        "cases": [_case_entry(outcome) for outcome in results.outcomes],
    }


def write_results(path: str | Path, document: Mapping[str, Any]) -> None:
    """Write ``results.json``: sorted keys, two-space indent, one trailing newline.

    Sorted and indented on purpose — this file gets committed and diffed, and a diff
    that only reorders keys is noise.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(document), indent=2, sort_keys=True) + "\n")


def read_results(path: str | Path) -> dict[str, Any]:
    """Read a results.json back. Raises :exc:`ReportError` with a fixable message."""
    source = Path(path)
    try:
        text = source.read_text()
    except OSError as exc:
        raise ReportError(
            f"cannot read results {str(source)!r}: {exc} — run bakeoff run first"
        ) from exc
    try:
        decoded: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ReportError(f"{source}: not valid JSON: {exc}") from exc
    if not isinstance(decoded, dict):
        raise ReportError(f"{source}: results must be a JSON object, got {type(decoded).__name__}")
    version = decoded.get("version")
    if version != REPORT_VERSION:
        raise ReportError(
            f"{source}: unsupported results version {version!r} — re-run bakeoff run "
            f"to write version {REPORT_VERSION}"
        )
    return decoded


# --- rendering helpers ------------------------------------------------------


def _esc(value: object) -> str:
    """Escape anything for HTML text. Every value from the document goes through this."""
    return escape(str(value), quote=True)


def _percent(fraction: float) -> str:
    """``0.83`` -> ``83%``. Whole percent only; the drill-down carries the detail."""
    return f"{fraction * 100:.0f}%"


def _ms(value: float) -> str:
    """``1234.5`` -> ``1235 ms``."""
    return f"{value:.0f} ms"


def _badge(met: bool) -> str:
    """The green/red pill used for a verdict."""
    label = "MET" if met else "MISSED"
    return f'<span class="badge {"pass" if met else "fail"}">{label}</span>'


def _measure(measured: str, bar: str) -> str:
    """A measurement cell: what was measured, with the bar it was held to beneath it."""
    return f'{measured}<span class="bar">{bar}</span>'


def _table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    cls: str = "",
    row_classes: Sequence[str] | None = None,
) -> str:
    """A ``<table>`` from header labels and rows of cells.

    Cells and headers are inserted **verbatim**, so a caller passes HTML it has
    already escaped with :func:`_esc`. ``row_classes`` (when given) is one class
    string per row, applied to that row's ``<tr>``; an empty string means no class.
    """
    head = "".join(f"<th>{header}</th>" for header in headers)
    body: list[str] = []
    for index, row in enumerate(rows):
        row_class = row_classes[index] if row_classes is not None else ""
        attribute = f' class="{row_class}"' if row_class else ""
        cells = "".join(f"<td>{cell}</td>" for cell in row)
        body.append(f"<tr{attribute}>{cells}</tr>")
    table_class = f' class="{cls}"' if cls else ""
    return (
        f"<table{table_class}>\n<thead><tr>{head}</tr></thead>\n"
        f"<tbody>\n" + "\n".join(body) + "\n</tbody>\n</table>"
    )


def _meta_list(items: Sequence[tuple[str, str]]) -> str:
    """A definition list of label/value pairs. Values are inserted verbatim."""
    entries = "".join(
        f"<div><dt>{_esc(label)}</dt><dd>{value}</dd></div>" for label, value in items
    )
    return f'<dl class="meta">{entries}</dl>'


# --- sections ---------------------------------------------------------------


def _header(document: Mapping[str, Any]) -> str:
    """Title, the one-line verdict, and the run's provenance."""
    met = bool(document["met_bar"])
    headline = "BAR MET" if met else "BAR MISSED"
    pairs = document["pairs"]
    cases = document["cases"]
    meta = _meta_list(
        [
            ("manifest", _esc(document["manifest"])),
            ("started", _esc(document["started_at"])),
            ("finished", _esc(document["finished_at"])),
            ("generated", _esc(document["generated_at"])),
            ("pairs", _esc(len(pairs))),
            ("cases", _esc(len(cases))),
            ("exit code", _esc(document["exit_code"])),
        ]
    )
    return (
        "<header>\n"
        "<h1>bakeoff audition</h1>\n"
        f'<p class="headline {"pass" if met else "fail"}">{headline}</p>\n'
        f"{meta}\n"
        "</header>"
    )


def _freeze_banner(document: Mapping[str, Any]) -> str:
    """The honesty mechanic, printed. A rebarred run says so at the top of its report.

    SPEC.md feature 4: a run whose bar no longer matches its freeze is branded
    REBARRED *with both hashes*, so a reader can see exactly what moved.
    """
    freeze = document["freeze"]
    if freeze is None:
        return (
            '<div class="banner unknown"><strong>FREEZE NOT RECORDED</strong>'
            "<p>This run recorded no freeze check, so the bar it ran under cannot be "
            "verified from this file.</p></div>"
        )
    status = str(freeze["status"])
    current = _esc(freeze["bar_hash"])
    frozen = freeze["frozen_hash"]
    if status == "frozen":
        return (
            '<div class="banner frozen"><strong>FROZEN</strong>'
            "<p>The bar was pre-registered before this run and has not moved since.</p>"
            f'<p class="hash">bar {current}</p></div>'
        )
    if status == "rebarred":
        return (
            '<div class="banner rebarred"><strong>REBARRED</strong>'
            "<p>The bar was edited after it was frozen. This run was made deliberately "
            "with <code>--rebar</code>; both hashes are printed so the change is "
            "visible, not hidden.</p>"
            f'<p class="hash">frozen&nbsp; {_esc(frozen)}</p>'
            f'<p class="hash">current {current}</p></div>'
        )
    return (
        '<div class="banner unfrozen"><strong>UNFROZEN</strong>'
        "<p>No bar was pre-registered before this run — nothing here was measured "
        "against a promise made in advance.</p>"
        f'<p class="hash">bar {current}</p></div>'
    )


def _reasons(reasons: Sequence[str]) -> str:
    """The plain-language breach lines printed under a missed verdict."""
    if not reasons:
        return ""
    items = "".join(f"<li>{_esc(reason)}</li>" for reason in reasons)
    return f'<ul class="reasons">{items}</ul>'


def _scoreboard(document: Mapping[str, Any]) -> str:
    """One row per suite x candidate pair: what it measured, next to what it promised."""
    pairs = document["pairs"]
    if not pairs:
        return '<section><h2>Scoreboard</h2><p class="muted">No pairs were scored.</p></section>'
    rows: list[list[str]] = []
    classes: list[str] = []
    for pair in pairs:
        thresholds = pair["thresholds"]
        met = bool(pair["met"])
        rows.append(
            [
                _esc(pair["suite"]),
                _esc(pair["candidate"]),
                f"{_esc(pair['passed'])} / {_esc(pair['cases'])}",
                _esc(pair["errors"]),
                _measure(
                    _percent(pair["pass_rate"]),
                    "&ge; " + _percent(thresholds["min_pass_rate"]),
                ),
                _measure(
                    _ms(pair["p95_latency_ms"]),
                    "&le; " + _ms(thresholds["max_p95_latency_ms"]),
                ),
                _measure(
                    _esc(pair["max_tokens_per_case"]),
                    "&le; " + _esc(thresholds["max_tokens_per_case"]),
                ),
                _badge(met) + _reasons(pair["reasons"]),
            ]
        )
        classes.append("" if met else "missed")
    table = _table(
        ["suite", "candidate", "passed", "errors", "pass rate", "p95 latency", "max tokens", ""],
        rows,
        cls="scoreboard",
        row_classes=classes,
    )
    return f"<section>\n<h2>Scoreboard</h2>\n{table}\n</section>"


# --- the page ---------------------------------------------------------------

_STYLE = """
:root {
  color-scheme: light dark;
  --paper: #ffffff; --ink: #16181d; --muted: #5b6270; --line: #dce0e8;
  --pass: #0f7b3f; --fail: #b3261e; --warn: #8a5a00; --tint: #f5f6f9;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #14161a; --ink: #e6e8ee; --muted: #99a1b0; --line: #2b303a;
    --pass: #5fd08a; --fail: #ff8f84; --warn: #e2b45c; --tint: #1b1e24;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--paper); color: var(--ink); line-height: 1.45;
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
}
main { max-width: 60rem; margin: 0 auto; padding: 2rem 1.25rem 4rem; }
h1 { font-size: 1.5rem; margin: 0 0 0.4rem; letter-spacing: -0.01em; }
h2 { font-size: 1.05rem; margin: 2rem 0 0.6rem; text-transform: uppercase;
     letter-spacing: 0.08em; color: var(--muted); }
h3 { font-size: 0.95rem; margin: 0; }
p { margin: 0.35rem 0; }
code, .hash, .completion, .mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.85em;
}
.headline { font-size: 1.15rem; font-weight: 700; letter-spacing: 0.04em; }
.headline.pass { color: var(--pass); }
.headline.fail { color: var(--fail); }
.muted { color: var(--muted); }
.meta { display: flex; flex-wrap: wrap; gap: 0.25rem 1.75rem; margin: 1rem 0 0; }
.meta dt { color: var(--muted); font-size: 0.72rem; text-transform: uppercase;
           letter-spacing: 0.06em; }
.meta dd { margin: 0; font-size: 0.9rem; }
.banner { border: 1px solid var(--line); border-left-width: 5px; border-radius: 6px;
          padding: 0.75rem 1rem; margin: 1.5rem 0 0; background: var(--tint); }
.banner strong { letter-spacing: 0.1em; font-size: 0.8rem; }
.banner.frozen { border-left-color: var(--pass); }
.banner.frozen strong { color: var(--pass); }
.banner.rebarred { border-left-color: var(--fail); }
.banner.rebarred strong { color: var(--fail); }
.banner.unfrozen, .banner.unknown { border-left-color: var(--warn); }
.banner.unfrozen strong, .banner.unknown strong { color: var(--warn); }
.hash { color: var(--muted); word-break: break-all; }
table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
th, td { text-align: left; padding: 0.5rem 0.6rem; border-bottom: 1px solid var(--line);
         vertical-align: top; }
th { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em;
     color: var(--muted); border-bottom-width: 2px; }
tbody tr.missed { background: var(--tint); }
.bar { display: block; color: var(--muted); font-size: 0.75rem; }
.badge { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 999px;
         font-size: 0.7rem; font-weight: 700; letter-spacing: 0.06em;
         border: 1px solid currentColor; }
.badge.pass { color: var(--pass); }
.badge.fail { color: var(--fail); }
.reasons { margin: 0.4rem 0 0; padding-left: 1.1rem; color: var(--fail);
           font-size: 0.8rem; }
details { border: 1px solid var(--line); border-radius: 6px; margin: 0.5rem 0;
          background: var(--tint); }
details > summary { cursor: pointer; padding: 0.55rem 0.8rem; font-weight: 600;
                    font-size: 0.9rem; }
details > div, details > table { padding: 0 0.8rem 0.8rem; }
.completion { white-space: pre-wrap; word-break: break-word; display: block;
              max-height: 14rem; overflow: auto; }
.error { color: var(--fail); }
.case-fail td:first-child { border-left: 3px solid var(--fail); }
footer { margin-top: 3rem; color: var(--muted); font-size: 0.78rem; }
""".strip()


def _page(title: str, body: str) -> str:
    """The whole document. Inline style only: no script, no link, no external request."""
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{_esc(title)}</title>\n"
        f"<style>\n{_STYLE}\n</style>\n"
        "</head>\n"
        "<body>\n"
        "<main>\n"
        f"{body}\n"
        "<footer>Generated by bakeoff — model selection by pre-registered audition. "
        "This file is self-contained: no scripts, no network requests.</footer>\n"
        "</main>\n"
        "</body>\n"
        "</html>\n"
    )


def render_report(document: Mapping[str, Any]) -> str:
    """Render a results document as one self-contained HTML page.

    Pure: the same document renders the same bytes, on any machine, at any time.
    Sections are rendered in reading order — the verdict first, then whether the bar
    was pre-registered, then the scoreboard.
    """
    sections = [
        _header(document),
        _freeze_banner(document),
        _scoreboard(document),
    ]
    return _page(f"bakeoff — {document['manifest']}", "\n".join(sections))


def write_report(path: str | Path, document: Mapping[str, Any]) -> None:
    """Render ``document`` and write it to ``path``, creating parents as needed."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_report(document))
