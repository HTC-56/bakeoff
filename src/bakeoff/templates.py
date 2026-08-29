"""Scaffold templates for ``bakeoff init``.

The quickstart manifest and five case files live here as string constants so that
``bakeoff init`` works from an installed wheel — the ``examples/`` directory is not
inside the package and would be missing for strangers who ran ``uv tool install
bakeoff``.
"""

from __future__ import annotations

from pathlib import Path

from .errors import ConfigError


class TemplateError(ConfigError):
    """A scaffold file already exists and ``force`` was not set."""


QUICKSTART_MANIFEST: str = """\
version: 1
candidates:
  - name: stub
    base_url: http://localhost:8000
    model: stub-model
    profile:
      system: "Answer with the bare value."
      temperature: 0.0
      max_tokens: 64
suites:
  - name: smoke
    path: suites/smoke
bar:
  defaults:
    min_pass_rate: 0.8
    max_p95_latency_ms: 2000
    max_tokens_per_case: 200
  overrides:
    - suite: smoke
      candidate: stub
      min_pass_rate: 1.0
"""

QUICKSTART_CASES: dict[str, str] = {
    "01-exact.yaml": """\
prompt: "echo: 4"
grader:
  kind: exact
  expected: "4"
reference: "4"
""",
    "02-contains.yaml": """\
prompt: "echo: The answer is 42"
grader:
  kind: contains
  substring: "42"
reference: "The answer is 42"
""",
    "03-regex.yaml": """\
prompt: "echo: hello world 123"
grader:
  kind: regex
  pattern: "\\\\d+"
reference: "hello world 123"
""",
    "04-numeric.yaml": """\
prompt: "echo: 3.14"
grader:
  kind: numeric_tolerance
  expected: 3.14
  tolerance: 0.01
reference: "3.14"
""",
    "05-json-schema.yaml": """\
prompt: 'json: {"name": "Ada", "age": 36}'
grader:
  kind: json_schema
  schema:
    type: object
    required:
      - name
      - age
reference: '{"name": "Ada", "age": 36}'
""",
}


def write_scaffold(directory: str | Path, *, force: bool = False) -> list[Path]:
    """Write the quickstart scaffold into *directory*.

    Creates ``audition.yaml`` and five case files under ``suites/smoke/``,
    returning the list of paths written (in that order).  Creates parent
    directories as needed.

    Raises :exc:`TemplateError` naming the first file that already exists
    unless *force* is true.  No lockfile is written — freezing is a
    deliberate separate step.
    """
    base = Path(directory)
    paths: list[Path] = []

    # manifest first
    manifest_path = base / "audition.yaml"
    if not force and manifest_path.exists():
        raise TemplateError(f"{manifest_path} already exists")
    manifest_path.write_text(QUICKSTART_MANIFEST)
    paths.append(manifest_path)

    # case files
    smoke_dir = base / "suites" / "smoke"
    smoke_dir.mkdir(parents=True, exist_ok=True)
    for filename in QUICKSTART_CASES:
        case_path = smoke_dir / filename
        if not force and case_path.exists():
            raise TemplateError(f"{case_path} already exists")
        case_path.write_text(QUICKSTART_CASES[filename])
        paths.append(case_path)

    return paths
