"""The audition manifest.

SPEC.md feature 1: one YAML file declares the candidates, the task suites, and the
bar — everything about an audition that must exist *before* any model runs. It is
validated by pydantic, and a bad field produces a message that names the field and
the fix rather than a traceback.

Manifest shape (``examples/quickstart/audition.yaml``)::

    version: 1
    candidates:
      - name: stub
        base_url: http://localhost:8000
        model: stub-model
        profile:
          system: "Answer with the bare value."
          temperature: 0.0
          max_tokens: 64
          concurrency: 4
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

Suite paths are relative to the manifest file — see :func:`suite_dir`. The bar is
declared here but frozen elsewhere: hashing it into a lockfile is SPEC.md feature 4
and is not built yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .errors import ConfigError, format_validation_error
from .suite import Suite, SuiteError, load_suite

MANIFEST_VERSION = 1
THRESHOLD_FIELDS = ("min_pass_rate", "max_p95_latency_ms", "max_tokens_per_case")


class ManifestError(ConfigError):
    """The manifest is missing, is not YAML, or has a field that cannot be used."""


class _Model(BaseModel):
    """Base for every manifest model. Unknown keys are errors, never silently ignored."""

    model_config = ConfigDict(extra="forbid")


class Profile(_Model):
    """How one candidate is asked: its system prompt and sampling/limit settings."""

    system: str | None = None
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    concurrency: int = Field(default=4, ge=1)


class Candidate(_Model):
    """One model in the audition: where it lives, what it is called, how it is asked."""

    name: str = Field(min_length=1)
    base_url: str
    model: str = Field(min_length=1)
    profile: Profile = Field(default_factory=Profile)

    @field_validator("base_url")
    @classmethod
    def _must_be_an_http_root(cls, value: str) -> str:
        """The endpoint root only — the client appends ``/v1/chat/completions``."""
        if not value.startswith(("http://", "https://")):
            raise ValueError(
                "must be an endpoint root starting with http:// or https:// "
                "(for example http://localhost:8000)"
            )
        trimmed = value.rstrip("/")
        if trimmed.endswith("/v1/chat/completions"):
            raise ValueError(
                "must be the endpoint root, not the completions path — "
                "drop the trailing /v1/chat/completions"
            )
        return trimmed


class SuiteRef(_Model):
    """A suite named by the manifest: its label, and its directory relative to this file."""

    name: str = Field(min_length=1)
    path: str = Field(min_length=1)


class Thresholds(_Model):
    """What "good enough" means for one suite x candidate pair. All three are required."""

    min_pass_rate: float = Field(ge=0.0, le=1.0)
    max_p95_latency_ms: float = Field(gt=0.0)
    max_tokens_per_case: int = Field(ge=1)


class BarOverride(_Model):
    """A narrower bar for some pairs. Omitted thresholds keep the default value.

    ``suite`` and ``candidate`` are filters: omit one to match every suite (or every
    candidate). Overrides are applied in file order, so a later entry wins — put the
    most specific ones last.
    """

    suite: str | None = None
    candidate: str | None = None
    min_pass_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    max_p95_latency_ms: float | None = Field(default=None, gt=0.0)
    max_tokens_per_case: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _must_narrow_something(self) -> BarOverride:
        if self.suite is None and self.candidate is None:
            raise ValueError(
                "must name a suite, a candidate, or both — an override that matches "
                "everything belongs in bar.defaults"
            )
        if all(getattr(self, field) is None for field in THRESHOLD_FIELDS):
            raise ValueError(f"must set at least one of {', '.join(THRESHOLD_FIELDS)}")
        return self

    def matches(self, suite: str, candidate: str) -> bool:
        """True when this override applies to the given suite x candidate pair."""
        return (self.suite is None or self.suite == suite) and (
            self.candidate is None or self.candidate == candidate
        )


class Bar(_Model):
    """The pre-registered bar: one default triple plus any per-pair overrides."""

    defaults: Thresholds
    overrides: list[BarOverride] = Field(default_factory=list)

    def for_pair(self, suite: str, candidate: str) -> Thresholds:
        """The thresholds that apply to one suite x candidate pair, overrides merged in."""
        merged: dict[str, Any] = self.defaults.model_dump()
        for override in self.overrides:
            if not override.matches(suite, candidate):
                continue
            for field in THRESHOLD_FIELDS:
                value = getattr(override, field)
                if value is not None:
                    merged[field] = value
        return Thresholds(**merged)


class Manifest(_Model):
    """A whole audition, validated: candidates, suites, and the bar they are judged by."""

    version: int = MANIFEST_VERSION
    candidates: list[Candidate] = Field(min_length=1)
    suites: list[SuiteRef] = Field(min_length=1)
    bar: Bar

    @field_validator("version")
    @classmethod
    def _known_version(cls, value: int) -> int:
        if value != MANIFEST_VERSION:
            raise ValueError(f"unsupported manifest version — set version: {MANIFEST_VERSION}")
        return value

    @model_validator(mode="after")
    def _names_are_unique_and_overrides_resolve(self) -> Manifest:
        candidate_names = [candidate.name for candidate in self.candidates]
        suite_names = [suite.name for suite in self.suites]
        for label, names in (("candidates", candidate_names), ("suites", suite_names)):
            duplicates = sorted({name for name in names if names.count(name) > 1})
            if duplicates:
                raise ValueError(
                    f"{label}: duplicate name(s) {', '.join(duplicates)} — names must be unique"
                )
        for index, override in enumerate(self.bar.overrides):
            if override.suite is not None and override.suite not in suite_names:
                raise ValueError(
                    f"bar.overrides.{index}.suite: no suite named {override.suite!r} — "
                    f"known suites: {', '.join(suite_names)}"
                )
            if override.candidate is not None and override.candidate not in candidate_names:
                raise ValueError(
                    f"bar.overrides.{index}.candidate: no candidate named {override.candidate!r} — "
                    f"known candidates: {', '.join(candidate_names)}"
                )
        return self

    def candidate(self, name: str) -> Candidate:
        """The candidate with this name, or :exc:`KeyError`."""
        for candidate in self.candidates:
            if candidate.name == name:
                return candidate
        raise KeyError(name)


def suite_dir(manifest_path: str | Path, ref: SuiteRef) -> Path:
    """Resolve one suite's directory relative to the manifest file that named it."""
    return Path(manifest_path).resolve().parent / ref.path


def parse_manifest(data: object, *, source: str) -> Manifest:
    """Validate an already-decoded manifest. Pure — tests build the mapping inline."""
    if not isinstance(data, dict):
        raise ManifestError(
            f"{source}: a manifest must be a YAML mapping, got {type(data).__name__}"
        )
    try:
        return Manifest.model_validate(data)
    except ValidationError as exc:
        raise ManifestError(format_validation_error(source, exc)) from exc


def load_manifest(path: str | Path) -> Manifest:
    """Read and validate a manifest file. Raises :exc:`ManifestError` with a fixable message."""
    manifest_path = Path(path)
    try:
        text = manifest_path.read_text()
    except OSError as exc:
        raise ManifestError(f"cannot read manifest {str(manifest_path)!r}: {exc}") from exc
    try:
        decoded: object = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ManifestError(f"{manifest_path}: not valid YAML: {exc}") from exc
    return parse_manifest(decoded, source=str(manifest_path))


@dataclass(frozen=True)
class Audition:
    """A loaded audition: the manifest and every suite it names, in manifest order.

    Use :meth:`suite` to look up a suite by name — it raises :exc:`KeyError`
    when there is no such suite.
    """

    manifest: Manifest
    suites: tuple[Suite, ...]

    def suite(self, name: str) -> Suite:
        """The suite with this name, or :exc:`KeyError`."""
        for suite in self.suites:
            if suite.name == name:
                return suite
        raise KeyError(name)


def load_audition(path: str | Path) -> Audition:
    """Load a manifest and every suite it references.

    Raises :exc:`ManifestError` when the manifest is unreadable, is not valid
    YAML, fails validation, or when one of the named suite directories cannot
    be loaded (the error names the manifest path, the suite name, and the
    resolved directory).
    """
    manifest = load_manifest(path)
    suites: list[Suite] = []
    for ref in manifest.suites:
        directory = suite_dir(path, ref)
        try:
            suites.append(load_suite(directory, name=ref.name))
        except SuiteError as exc:
            raise ManifestError(f"{path}: suite {ref.name!r} at {str(directory)!r}: {exc}") from exc
    return Audition(manifest=manifest, suites=tuple(suites))
