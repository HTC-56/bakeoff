"""Freeze tests.

One test class per public name in :mod:`bakeoff.freeze`, in the order the module
declares them. New classes are appended below; mirror :class:`TestBarHash` for the
shape (a class per function, one plain assertion per behaviour).

The helpers at the top build a bar (and a whole manifest) from a plain mapping, so a
test names only the fields it cares about.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bakeoff.freeze import (
    HASH_PREFIX,
    LOCKFILE_VERSION,
    FreezeCheck,
    FreezeError,
    FreezeStatus,
    Lockfile,
    bar_hash,
    canonical_bar,
    check_freeze,
    find_lockfile,
    freeze_bar,
    lockfile_path,
    read_lockfile,
    require_freeze,
    write_lockfile,
)
from bakeoff.manifest import Bar, Manifest, parse_manifest

# --- helpers ----------------------------------------------------------------

FROZEN_AT = "2026-01-01T00:00:00+00:00"


def make_bar(
    *,
    min_pass_rate: float = 0.8,
    max_p95_latency_ms: float = 2000.0,
    max_tokens_per_case: int = 200,
    overrides: list[dict[str, Any]] | None = None,
) -> Bar:
    """A Bar with everything defaulted, so a test names only what it varies."""
    return Bar.model_validate(
        {
            "defaults": {
                "min_pass_rate": min_pass_rate,
                "max_p95_latency_ms": max_p95_latency_ms,
                "max_tokens_per_case": max_tokens_per_case,
            },
            "overrides": overrides or [],
        }
    )


def make_manifest(*, bar: dict[str, Any] | None = None) -> Manifest:
    """A one-candidate, one-suite manifest — enough to freeze a bar."""
    return parse_manifest(
        {
            "version": 1,
            "candidates": [
                {"name": "stub", "base_url": "http://localhost:8000", "model": "stub-model"}
            ],
            "suites": [{"name": "smoke", "path": "suites/smoke"}],
            "bar": bar
            or {
                "defaults": {
                    "min_pass_rate": 0.8,
                    "max_p95_latency_ms": 2000.0,
                    "max_tokens_per_case": 200,
                }
            },
        },
        source="test",
    )


def make_lockfile(**overrides: Any) -> Lockfile:
    """A valid Lockfile for the default bar, fields overridable by keyword."""
    fields: dict[str, Any] = {
        "version": LOCKFILE_VERSION,
        "bar_hash": bar_hash(make_bar()),
        "frozen_at": FROZEN_AT,
        "manifest": "audition.yaml",
    }
    fields.update(overrides)
    return Lockfile.model_validate(fields)


# --- tests ------------------------------------------------------------------


class TestCanonicalBar:
    def test_it_is_one_line_of_json(self) -> None:
        text = canonical_bar(make_bar())
        assert "\n" not in text
        assert text.startswith("{") and text.endswith("}")

    def test_it_carries_the_lockfile_version(self) -> None:
        assert f'"version":{LOCKFILE_VERSION}' in canonical_bar(make_bar())

    def test_equal_bars_declared_differently_canonicalise_the_same(self) -> None:
        # 1 and 1.0 are the same threshold; the bar model coerces both to a float.
        one = Bar.model_validate(
            {
                "defaults": {
                    "min_pass_rate": 1,
                    "max_p95_latency_ms": 2000,
                    "max_tokens_per_case": 200,
                }
            }
        )
        other = make_bar(min_pass_rate=1.0)
        assert canonical_bar(one) == canonical_bar(other)


class TestBarHash:
    def test_it_is_a_prefixed_sha256_digest(self) -> None:
        value = bar_hash(make_bar())
        digest = value.removeprefix(HASH_PREFIX)
        assert value.startswith(HASH_PREFIX)
        assert len(digest) == 64
        assert all(character in "0123456789abcdef" for character in digest)

    def test_the_same_bar_hashes_the_same_every_time(self) -> None:
        assert bar_hash(make_bar()) == bar_hash(make_bar())

    def test_moving_a_threshold_changes_the_hash(self) -> None:
        assert bar_hash(make_bar()) != bar_hash(make_bar(min_pass_rate=0.7))

    def test_adding_an_override_changes_the_hash(self) -> None:
        rebarred = make_bar(overrides=[{"suite": "smoke", "min_pass_rate": 1.0}])
        assert bar_hash(make_bar()) != bar_hash(rebarred)

    def test_override_order_is_part_of_the_bar(self) -> None:
        first = make_bar(
            overrides=[
                {"suite": "smoke", "min_pass_rate": 1.0},
                {"candidate": "stub", "min_pass_rate": 0.5},
            ]
        )
        second = make_bar(
            overrides=[
                {"candidate": "stub", "min_pass_rate": 0.5},
                {"suite": "smoke", "min_pass_rate": 1.0},
            ]
        )
        assert bar_hash(first) != bar_hash(second)


class TestLockfileModel:
    def test_a_digest_without_the_prefix_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="hex characters"):
            make_lockfile(bar_hash="a" * 64)

    def test_a_short_digest_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="hex characters"):
            make_lockfile(bar_hash=f"{HASH_PREFIX}abc")

    def test_an_uppercase_digest_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="lowercase hexadecimal"):
            make_lockfile(bar_hash=f"{HASH_PREFIX}{'A' * 64}")

    def test_an_unknown_version_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="unsupported lockfile version"):
            make_lockfile(version=99)

    def test_an_unknown_key_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            make_lockfile(note="hand-written")


class TestLockfilePath:
    def test_it_sits_beside_the_manifest(self) -> None:
        assert lockfile_path("examples/quickstart/audition.yaml") == Path(
            "examples/quickstart/audition.lock"
        )

    def test_a_manifest_without_a_suffix_still_gets_one(self) -> None:
        assert lockfile_path("audition") == Path("audition.lock")


class TestFreezeBar:
    def test_it_records_the_hash_of_the_manifests_bar(self) -> None:
        manifest = make_manifest()
        lock = freeze_bar(manifest, manifest_path="audition.yaml", now=FROZEN_AT)
        assert lock.bar_hash == bar_hash(manifest.bar)

    def test_it_records_the_manifest_name_not_its_path(self) -> None:
        lock = freeze_bar(make_manifest(), manifest_path="/tmp/deep/audition.yaml", now=FROZEN_AT)
        assert lock.manifest == "audition.yaml"

    def test_it_stamps_the_time_it_was_given(self) -> None:
        lock = freeze_bar(make_manifest(), manifest_path="audition.yaml", now=FROZEN_AT)
        assert lock.frozen_at == FROZEN_AT

    def test_a_real_freeze_stamps_an_iso_utc_time(self) -> None:
        lock = freeze_bar(make_manifest(), manifest_path="audition.yaml")
        assert lock.frozen_at.endswith("+00:00")


class TestWriteAndReadLockfile:
    def test_a_written_lockfile_reads_back_identical(self, tmp_path: Path) -> None:
        path = tmp_path / "audition.lock"
        lock = make_lockfile()
        write_lockfile(path, lock)
        assert read_lockfile(path) == lock

    def test_the_written_file_explains_itself(self, tmp_path: Path) -> None:
        path = tmp_path / "audition.lock"
        write_lockfile(path, make_lockfile())
        assert path.read_text().startswith("# bakeoff lockfile")

    def test_it_creates_the_parent_directory(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "audition.lock"
        write_lockfile(path, make_lockfile())
        assert path.exists()

    def test_a_missing_lockfile_says_to_freeze_first(self, tmp_path: Path) -> None:
        with pytest.raises(FreezeError, match="run bakeoff freeze first"):
            read_lockfile(tmp_path / "nope.lock")

    def test_a_lockfile_that_is_not_a_mapping_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "audition.lock"
        path.write_text("- just a list\n")
        with pytest.raises(FreezeError, match="must be a YAML mapping"):
            read_lockfile(path)

    def test_a_hand_edited_digest_is_rejected_by_name(self, tmp_path: Path) -> None:
        path = tmp_path / "audition.lock"
        path.write_text(
            f"bar_hash: nonsense\nfrozen_at: {FROZEN_AT}\nmanifest: audition.yaml\nversion: 1\n"
        )
        with pytest.raises(FreezeError, match="bar_hash"):
            read_lockfile(path)


class TestFindLockfile:
    def test_no_lockfile_beside_the_manifest_is_not_an_error(self, tmp_path: Path) -> None:
        assert find_lockfile(tmp_path / "audition.yaml") is None

    def test_it_finds_the_lockfile_written_for_that_manifest(self, tmp_path: Path) -> None:
        manifest_path = tmp_path / "audition.yaml"
        lock = make_lockfile()
        write_lockfile(lockfile_path(manifest_path), lock)
        assert find_lockfile(manifest_path) == lock

    def test_a_corrupt_lockfile_is_an_error_not_a_missing_freeze(self, tmp_path: Path) -> None:
        manifest_path = tmp_path / "audition.yaml"
        (tmp_path / "audition.lock").write_text("bar_hash: 3\n")
        with pytest.raises(FreezeError):
            find_lockfile(manifest_path)


class TestCheckFreeze:
    def test_no_lockfile_is_unfrozen(self) -> None:
        bar = make_bar()
        check = check_freeze(bar, lock=None)
        assert check.status == FreezeStatus.UNFROZEN
        assert check.frozen_hash is None

    def test_unfrozen_still_reports_current_hash(self) -> None:
        bar = make_bar()
        check = check_freeze(bar, lock=None)
        assert check.current_hash == bar_hash(bar)

    def test_same_manifest_gives_frozen(self) -> None:
        manifest = make_manifest()
        bar = manifest.bar
        lock = freeze_bar(manifest, manifest_path="audition.yaml", now=FROZEN_AT)
        check = check_freeze(bar, lock)
        assert check.status == FreezeStatus.FROZEN
        assert check.current_hash == check.frozen_hash

    def test_different_bar_gives_rebarred(self) -> None:
        manifest = make_manifest()
        original_hash = bar_hash(manifest.bar)
        different_bar = make_bar(min_pass_rate=0.5)
        lock = freeze_bar(manifest, manifest_path="audition.yaml", now=FROZEN_AT)
        check = check_freeze(different_bar, lock)
        assert check.status == FreezeStatus.REBARRED
        assert check.current_hash != check.frozen_hash
        assert check.current_hash == bar_hash(different_bar)
        assert check.frozen_hash == original_hash

    def test_rebarred_keeps_frozen_hash(self) -> None:
        lock = make_lockfile()
        different_bar = make_bar(min_pass_rate=0.5)
        check = check_freeze(different_bar, lock)
        assert check.status == FreezeStatus.REBARRED
        assert check.frozen_hash == lock.bar_hash


class TestRequireFreeze:
    def test_frozen_with_rebar_false_returns_none(self) -> None:
        bar = make_bar()
        check = FreezeCheck(
            status=FreezeStatus.FROZEN,
            current_hash=bar_hash(bar),
            frozen_hash=bar_hash(bar),
        )
        require_freeze(check, rebar=False)

    def test_frozen_with_rebar_true_returns_none(self) -> None:
        bar = make_bar()
        check = FreezeCheck(
            status=FreezeStatus.FROZEN,
            current_hash=bar_hash(bar),
            frozen_hash=bar_hash(bar),
        )
        require_freeze(check, rebar=True)

    def test_unfrozen_raises_freeze_error(self) -> None:
        check = FreezeCheck(
            status=FreezeStatus.UNFROZEN,
            current_hash=bar_hash(make_bar()),
            frozen_hash=None,
        )
        with pytest.raises(FreezeError, match="bakeoff freeze"):
            require_freeze(check, rebar=False)

    def test_rebarred_without_rebar_raises_and_shows_both_hashes(self) -> None:
        check = FreezeCheck(
            status=FreezeStatus.REBARRED,
            current_hash="sha256:aaa" + "b" * 61,
            frozen_hash="sha256:ccc" + "d" * 61,
        )
        with pytest.raises(FreezeError) as excinfo:
            require_freeze(check, rebar=False)
        msg = str(excinfo.value)
        assert "sha256:ccc" + "d" * 61 in msg
        assert "sha256:aaa" + "b" * 61 in msg

    def test_rebarred_with_rebar_true_returns_none(self) -> None:
        check = FreezeCheck(
            status=FreezeStatus.REBARRED,
            current_hash="sha256:aaa" + "b" * 61,
            frozen_hash="sha256:ccc" + "d" * 61,
        )
        require_freeze(check, rebar=True)
