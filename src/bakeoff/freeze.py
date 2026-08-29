"""The freeze mechanic: a bar is pre-registered, or it is not a bar.

SPEC.md feature 4, and the product's whole point. A pass bar that can be quietly
lowered after the results are in is not a bar, it is a story told afterwards. So the
bar is hashed into a lockfile *before* any model runs (``bakeoff freeze``); every run
records the bar hash it ran under; and a run whose bar no longer matches its freeze
does not silently proceed — it stops unless the caller passes ``--rebar``, and then
the report brands the run REBARRED with both hashes. Honesty is a mechanism here,
not a promise.

Three states, and only three (:class:`FreezeStatus`):

* **FROZEN** — a lockfile exists and the manifest's bar still hashes to it.
* **REBARRED** — a lockfile exists and the bar has changed since. Runnable only
  deliberately; the report says so.
* **UNFROZEN** — there is no lockfile. Nothing has been pre-registered yet.

What is hashed is the *bar*, not the manifest: adding a candidate or a case is
ordinary work and must not invalidate the freeze, whereas moving a threshold is
exactly the edit this module exists to catch. :func:`canonical_bar` fixes the bytes
that get hashed — mapping keys are sorted, so re-ordering YAML keys is a no-op, while
the ``overrides`` list keeps file order, because a later override wins over an earlier
one and swapping two of them really is a different bar.

The lockfile is YAML like everything else a user reads in this repo, and it is meant
to be committed. Hand-editing it is not prevented and does not need to be: the hash
is the check, and a bar hash that does not match the bar is a REBARRED run.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .errors import ConfigError, format_validation_error
from .manifest import Bar, Manifest

LOCKFILE_VERSION = 1
"""Bumped only when the hashed payload changes — every old lockfile then rebars."""

HASH_PREFIX = "sha256:"
DIGEST_LENGTH = 64

_LOCKFILE_HEADER = (
    "# bakeoff lockfile — the pre-registered bar, hashed.\n"
    "# Written by `bakeoff freeze`; commit it. A run whose bar no longer hashes to\n"
    "# bar_hash below needs --rebar, and its report is branded REBARRED.\n"
)


class FreezeError(ConfigError):
    """A lockfile is missing, unreadable, or the bar has moved since it was frozen."""


def canonical_bar(bar: Bar) -> str:
    """The exact bytes that get hashed: one canonical JSON line for this bar.

    Mapping keys are sorted and separators are tight, so two manifests that declare
    the same bar in different key order hash the same. List order is preserved: bar
    overrides are applied in file order, so their order is part of the bar's meaning.
    The payload carries :data:`LOCKFILE_VERSION` so a future change to what is hashed
    cannot be mistaken for an unchanged bar.
    """
    payload = {"version": LOCKFILE_VERSION, "bar": bar.model_dump(mode="json")}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def bar_hash(bar: Bar) -> str:
    """The bar's identity: ``sha256:`` followed by 64 hex characters."""
    digest = hashlib.sha256(canonical_bar(bar).encode("utf-8")).hexdigest()
    return f"{HASH_PREFIX}{digest}"


class Lockfile(BaseModel):
    """What ``bakeoff freeze`` writes: the bar's hash, when, and for which manifest.

    ``manifest`` is the manifest's file *name*, not a path — a lockfile lives beside
    its manifest, and recording an absolute path would leak one machine's layout into
    a committed file.
    """

    model_config = ConfigDict(extra="forbid")

    version: int = LOCKFILE_VERSION
    bar_hash: str = Field(min_length=1)
    frozen_at: str = Field(min_length=1)
    manifest: str = Field(min_length=1)

    @field_validator("version")
    @classmethod
    def _known_version(cls, value: int) -> int:
        if value != LOCKFILE_VERSION:
            raise ValueError(
                f"unsupported lockfile version — re-run bakeoff freeze to write "
                f"version {LOCKFILE_VERSION}"
            )
        return value

    @field_validator("bar_hash")
    @classmethod
    def _is_a_digest(cls, value: str) -> str:
        digest = value.removeprefix(HASH_PREFIX)
        if not value.startswith(HASH_PREFIX) or len(digest) != DIGEST_LENGTH:
            raise ValueError(
                f"must be {HASH_PREFIX} followed by {DIGEST_LENGTH} hex characters — "
                f"re-run bakeoff freeze rather than editing this by hand"
            )
        if any(character not in "0123456789abcdef" for character in digest):
            raise ValueError("must be lowercase hexadecimal — re-run bakeoff freeze")
        return value


class FreezeStatus(StrEnum):
    """Where a manifest's bar stands relative to its lockfile. Exactly three states."""

    FROZEN = "frozen"
    REBARRED = "rebarred"
    UNFROZEN = "unfrozen"


@dataclass(frozen=True)
class FreezeCheck:
    """The bar as it is now, held against the bar that was pre-registered.

    ``current_hash`` is the hash of the manifest's bar right now. ``frozen_hash`` is
    what the lockfile recorded, or ``None`` when there is no lockfile. Both are kept
    even when they agree, because a REBARRED report has to print the pair.
    """

    status: FreezeStatus
    current_hash: str
    frozen_hash: str | None


def _utc_now() -> str:
    """The current time as an ISO-8601 UTC string, seconds resolution."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def lockfile_path(manifest_path: str | Path) -> Path:
    """Where a manifest's lockfile lives: beside it, same stem, ``.lock`` suffix."""
    return Path(manifest_path).with_suffix(".lock")


def freeze_bar(
    manifest: Manifest,
    *,
    manifest_path: str | Path,
    now: str | None = None,
) -> Lockfile:
    """Pre-register this manifest's bar. ``now`` is injectable so tests are stable."""
    return Lockfile(
        version=LOCKFILE_VERSION,
        bar_hash=bar_hash(manifest.bar),
        frozen_at=now if now is not None else _utc_now(),
        manifest=Path(manifest_path).name,
    )


def write_lockfile(path: str | Path, lock: Lockfile) -> None:
    """Write a lockfile as commented YAML, creating the parent directory if needed."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump(lock.model_dump(mode="json"), sort_keys=True)
    target.write_text(_LOCKFILE_HEADER + body)


def read_lockfile(path: str | Path) -> Lockfile:
    """Read and validate a lockfile. Raises :exc:`FreezeError` with a fixable message."""
    lock_path = Path(path)
    try:
        text = lock_path.read_text()
    except OSError as exc:
        raise FreezeError(
            f"cannot read lockfile {str(lock_path)!r}: {exc} — run bakeoff freeze first"
        ) from exc
    try:
        decoded: object = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise FreezeError(f"{lock_path}: not valid YAML: {exc}") from exc
    if not isinstance(decoded, dict):
        raise FreezeError(
            f"{lock_path}: a lockfile must be a YAML mapping, got {type(decoded).__name__}"
        )
    try:
        return Lockfile.model_validate(decoded)
    except ValidationError as exc:
        raise FreezeError(format_validation_error(str(lock_path), exc)) from exc


def find_lockfile(manifest_path: str | Path) -> Lockfile | None:
    """The lockfile beside this manifest, or ``None`` when the bar was never frozen.

    A lockfile that exists but cannot be read is an error, not a missing freeze — a
    corrupt lockfile must never be mistaken for "not frozen yet".
    """
    path = lockfile_path(manifest_path)
    if not path.exists():
        return None
    return read_lockfile(path)


def check_freeze(bar: Bar, lock: Lockfile | None) -> FreezeCheck:
    """Compare the current bar against a pre-registered lockfile.

    Returns a :class:`FreezeCheck` whose status is one of three values:

    * ``UNFROZEN`` — no lockfile was provided.
    * ``FROZEN`` — the lockfile's bar hash matches the bar's hash.
    * ``REBARRED`` — the lockfile exists but the hash differs.

    ``current_hash`` is always the hash of the bar passed in; ``frozen_hash`` is the
    lockfile's recorded hash when a lockfile is present, or ``None`` otherwise.
    """
    current = bar_hash(bar)
    if lock is None:
        return FreezeCheck(
            status=FreezeStatus.UNFROZEN,
            current_hash=current,
            frozen_hash=None,
        )
    if lock.bar_hash == current:
        return FreezeCheck(
            status=FreezeStatus.FROZEN,
            current_hash=current,
            frozen_hash=lock.bar_hash,
        )
    return FreezeCheck(
        status=FreezeStatus.REBARRED,
        current_hash=current,
        frozen_hash=lock.bar_hash,
    )


def require_freeze(check: FreezeCheck, *, rebar: bool) -> None:
    """Raise :exc:`FreezeError` when this run may not proceed.

    A **FROZEN** bar is always allowed — ``--rebar`` is permission, not a mode.
    **UNFROZEN** runs are blocked until the user pre-registers a bar.
    **REBARRED** runs are blocked unless the caller explicitly passes ``rebar``.
    """
    if check.status == FreezeStatus.FROZEN:
        return
    if check.status == FreezeStatus.UNFROZEN:
        raise FreezeError("the bar has not been pre-registered — run bakeoff freeze first")
    # REBARRED
    if not rebar:
        raise FreezeError(
            f"bar has moved since freeze — frozen: {check.frozen_hash}, "
            f"current: {check.current_hash}; pass --rebar to proceed"
        )
