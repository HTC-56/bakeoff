"""Manifest tests: the happy path, the defaults, and how the bar resolves per pair.

Error-path classes (bad fields, unknown names) live below these; mirror
:class:`TestLoadManifest` when adding one.
"""

from __future__ import annotations

from pathlib import Path

from bakeoff.manifest import (
    Bar,
    BarOverride,
    Manifest,
    SuiteRef,
    Thresholds,
    load_manifest,
    parse_manifest,
    suite_dir,
)

MINIMAL = """
version: 1
candidates:
  - name: stub
    base_url: http://localhost:8000
    model: stub-model
suites:
  - name: smoke
    path: suites/smoke
bar:
  defaults:
    min_pass_rate: 0.8
    max_p95_latency_ms: 2000
    max_tokens_per_case: 200
"""


def write_manifest(tmp_path: Path, text: str = MINIMAL) -> Path:
    """Write a manifest into a temp directory and return its path."""
    path = tmp_path / "audition.yaml"
    path.write_text(text)
    return path


class TestLoadManifest:
    def test_a_minimal_manifest_loads(self, tmp_path: Path) -> None:
        manifest = load_manifest(write_manifest(tmp_path))
        assert isinstance(manifest, Manifest)
        assert [c.name for c in manifest.candidates] == ["stub"]
        assert [s.name for s in manifest.suites] == ["smoke"]

    def test_profile_defaults_are_filled_in(self, tmp_path: Path) -> None:
        profile = load_manifest(write_manifest(tmp_path)).candidates[0].profile
        assert profile.system is None
        assert profile.temperature == 0.0
        assert profile.max_tokens is None
        assert profile.concurrency == 4

    def test_a_declared_profile_wins_over_the_defaults(self) -> None:
        manifest = parse_manifest(
            {
                "candidates": [
                    {
                        "name": "stub",
                        "base_url": "http://localhost:8000",
                        "model": "stub-model",
                        "profile": {"system": "be terse", "temperature": 0.7, "max_tokens": 64},
                    }
                ],
                "suites": [{"name": "smoke", "path": "suites/smoke"}],
                "bar": {
                    "defaults": {
                        "min_pass_rate": 0.5,
                        "max_p95_latency_ms": 1000.0,
                        "max_tokens_per_case": 10,
                    }
                },
            },
            source="inline",
        )
        profile = manifest.candidates[0].profile
        assert profile.system == "be terse"
        assert profile.temperature == 0.7
        assert profile.max_tokens == 64

    def test_a_trailing_slash_is_stripped_from_base_url(self) -> None:
        manifest = parse_manifest(
            {
                "candidates": [
                    {"name": "s", "base_url": "http://localhost:8000/", "model": "m"},
                ],
                "suites": [{"name": "smoke", "path": "suites/smoke"}],
                "bar": {
                    "defaults": {
                        "min_pass_rate": 0.5,
                        "max_p95_latency_ms": 1000.0,
                        "max_tokens_per_case": 10,
                    }
                },
            },
            source="inline",
        )
        assert manifest.candidates[0].base_url == "http://localhost:8000"

    def test_candidate_lookup_by_name(self, tmp_path: Path) -> None:
        manifest = load_manifest(write_manifest(tmp_path))
        assert manifest.candidate("stub").model == "stub-model"


class TestSuiteDir:
    def test_suite_paths_resolve_against_the_manifest_file(self, tmp_path: Path) -> None:
        path = write_manifest(tmp_path)
        resolved = suite_dir(path, SuiteRef(name="smoke", path="suites/smoke"))
        assert resolved == tmp_path.resolve() / "suites" / "smoke"


class TestBarForPair:
    def bar(self) -> Bar:
        return Bar(
            defaults=Thresholds(
                min_pass_rate=0.8, max_p95_latency_ms=2000.0, max_tokens_per_case=200
            ),
            overrides=[
                BarOverride(suite="smoke", max_tokens_per_case=50),
                BarOverride(suite="smoke", candidate="stub", min_pass_rate=1.0),
            ],
        )

    def test_an_unmatched_pair_gets_the_defaults(self) -> None:
        thresholds = self.bar().for_pair("other", "stub")
        assert thresholds.min_pass_rate == 0.8
        assert thresholds.max_tokens_per_case == 200

    def test_a_suite_wide_override_applies_to_every_candidate(self) -> None:
        assert self.bar().for_pair("smoke", "anyone").max_tokens_per_case == 50

    def test_a_pair_override_stacks_on_the_suite_override(self) -> None:
        thresholds = self.bar().for_pair("smoke", "stub")
        assert thresholds.min_pass_rate == 1.0
        assert thresholds.max_tokens_per_case == 50
        assert thresholds.max_p95_latency_ms == 2000.0

    def test_for_pair_does_not_mutate_the_defaults(self) -> None:
        bar = self.bar()
        bar.for_pair("smoke", "stub")
        assert bar.defaults.min_pass_rate == 0.8
        assert bar.defaults.max_tokens_per_case == 200
