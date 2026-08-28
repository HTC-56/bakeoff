"""Task suites as files.

SPEC.md feature 2: a suite is a *directory of cases*, and a case is a YAML file
holding an input prompt, a grader spec, and an optional reference answer. There is no
hidden registry and no code to register a case in — ``ls suites/smoke`` shows the
whole audition, and a reviewer can diff it.

Case file shape (``suites/smoke/01-two-plus-two.yaml``)::

    prompt: "echo: 4"
    grader:
      kind: exact
      expected: "4"
    reference: "4"

``id`` is optional and defaults to the file stem, so the filenames order the suite
and name its cases. The five ``kind`` values are the five graders of
:mod:`bakeoff.graders`; each spec class below carries exactly that grader's
arguments, which is what lets a case file be checked before any model is called.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .errors import ConfigError, format_validation_error
from .graders import (
    GraderConfigError,
    GradeResult,
    grade_contains,
    grade_exact,
    grade_json_schema,
    grade_numeric_tolerance,
    grade_regex,
)

CASE_SUFFIXES = (".yaml", ".yml")


class SuiteError(ConfigError):
    """A suite directory is missing, empty, or holds a case file that is not valid."""


class _Model(BaseModel):
    """Base for every case model: unknown keys are errors, aliases are accepted."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ExactSpec(_Model):
    """``grade_exact``: the completion must equal ``expected``."""

    kind: Literal["exact"]
    expected: str
    strip: bool = True


class ContainsSpec(_Model):
    """``grade_contains``: ``substring`` must appear somewhere in the completion."""

    kind: Literal["contains"]
    substring: str
    case_sensitive: bool = True


class RegexSpec(_Model):
    """``grade_regex``: ``pattern`` must match the completion."""

    kind: Literal["regex"]
    pattern: str
    fullmatch: bool = False


class NumericToleranceSpec(_Model):
    """``grade_numeric_tolerance``: the completion must parse to a number near ``expected``."""

    kind: Literal["numeric_tolerance"]
    expected: float
    tolerance: float = Field(default=0.0, ge=0.0)


class JsonSchemaSpec(_Model):
    """``grade_json_schema``: the completion must be JSON valid against ``schema``.

    The YAML key is ``schema``; the Python attribute is ``json_schema`` because
    ``schema`` is taken on :class:`pydantic.BaseModel`.
    """

    kind: Literal["json_schema"]
    json_schema: dict[str, Any] = Field(alias="schema")


GraderSpec = Annotated[
    ExactSpec | ContainsSpec | RegexSpec | NumericToleranceSpec | JsonSchemaSpec,
    Field(discriminator="kind"),
]
"""Tagged union of every grader spec: ``kind`` picks the class and its fields."""


class Case(_Model):
    """One case of a suite: what to ask, how to grade it, and what a human expects."""

    id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    grader: GraderSpec
    reference: str | None = None


@dataclass(frozen=True)
class Suite:
    """A loaded suite: its name, the directory it came from, and its cases in file order."""

    name: str
    path: Path
    cases: tuple[Case, ...]

    def __len__(self) -> int:
        return len(self.cases)


def case_files(directory: Path) -> list[Path]:
    """Every case file in ``directory``, sorted by filename. Dotfiles are skipped."""
    return sorted(
        entry
        for entry in directory.iterdir()
        if entry.is_file() and entry.suffix in CASE_SUFFIXES and not entry.name.startswith(".")
    )


def parse_case(data: object, *, default_id: str, source: str) -> Case:
    """Validate one decoded case file. Pure — no I/O, so tests can call it directly.

    ``default_id`` is used when the file does not name an ``id`` (in practice the file
    stem). ``source`` only appears in the error message.
    """
    if not isinstance(data, dict):
        raise SuiteError(f"{source}: a case file must be a YAML mapping, got {type(data).__name__}")
    fields: dict[str, Any] = dict(data)
    fields.setdefault("id", default_id)
    try:
        return Case.model_validate(fields)
    except ValidationError as exc:
        raise SuiteError(format_validation_error(source, exc)) from exc


def load_suite(directory: str | Path, *, name: str | None = None) -> Suite:
    """Read every case file in ``directory`` and return the :class:`Suite`.

    The suite's name defaults to the directory name. Raises :exc:`SuiteError` when the
    directory is missing, holds no case files, has a file that is not valid YAML, or
    repeats a case id.
    """
    path = Path(directory)
    if not path.is_dir():
        raise SuiteError(f"suite directory {str(path)!r} does not exist — create it and add cases")
    files = case_files(path)
    if not files:
        raise SuiteError(
            f"suite directory {str(path)!r} has no case files "
            f"(expected one or more {' or '.join(CASE_SUFFIXES)} files)"
        )
    cases: list[Case] = []
    seen: set[str] = set()
    for file in files:
        try:
            decoded: object = yaml.safe_load(file.read_text())
        except yaml.YAMLError as exc:
            raise SuiteError(f"{file}: not valid YAML: {exc}") from exc
        case = parse_case(decoded, default_id=file.stem, source=str(file))
        if case.id in seen:
            raise SuiteError(f"{file}: duplicate case id {case.id!r} — case ids must be unique")
        seen.add(case.id)
        cases.append(case)
    return Suite(name=name or path.name, path=path, cases=tuple(cases))


def run_grader(spec: GraderSpec, completion: str) -> GradeResult:
    """Run one grader against a completion, given its validated spec.

    This is the one place that maps a validated :class:`GraderSpec` onto the
    grader function that implements it. Nothing else in the package is
    allowed to know that mapping.

    Each branch uses ``isinstance`` to dispatch to the matching grader,
    passing the spec's fields through as keyword arguments. After the five
    branches, a ``GraderConfigError`` is raised naming the spec — this makes
    a sixth spec class added without a branch fail loudly instead of silently.
    """
    if isinstance(spec, ExactSpec):
        return grade_exact(completion, spec.expected, strip=spec.strip)
    if isinstance(spec, ContainsSpec):
        return grade_contains(completion, spec.substring, case_sensitive=spec.case_sensitive)
    if isinstance(spec, RegexSpec):
        return grade_regex(completion, spec.pattern, fullmatch=spec.fullmatch)
    if isinstance(spec, NumericToleranceSpec):
        return grade_numeric_tolerance(completion, spec.expected, tolerance=spec.tolerance)
    if isinstance(spec, JsonSchemaSpec):
        return grade_json_schema(completion, spec.json_schema)
    raise GraderConfigError(f"unknown grader spec kind {type(spec).__name__!r}")
