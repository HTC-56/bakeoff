"""Shared configuration-error plumbing.

Two files describe an audition — the manifest (:mod:`bakeoff.manifest`) and the case
files of a suite (:mod:`bakeoff.suite`) — and both are validated by pydantic. When
either is wrong the user needs the same thing: the file it was in, the field that is
wrong, and what would make it right. :func:`format_validation_error` is that message,
so the two loaders cannot drift apart.

This module imports nothing from the rest of the package: it is the bottom of the
import graph (``errors`` <- ``graders``/``suite`` <- ``manifest``).
"""

from __future__ import annotations

from pydantic import ValidationError


class ConfigError(ValueError):
    """An audition's configuration is unusable — bad YAML, bad path, or bad fields.

    Every loader in bakeoff raises a subclass of this instead of leaking
    :exc:`pydantic.ValidationError`, so a caller (and later the CLI) can catch one
    type and print its message verbatim.
    """


def format_validation_error(source: str, exc: ValidationError) -> str:
    """Render a :exc:`pydantic.ValidationError` as a message that names field and fix.

    ``source`` is what the user typed or the file being read. Each error becomes one
    ``  <dotted.field.path>: <what is wrong>`` line, with the offending value shown
    when pydantic captured one.
    """
    lines = [f"{source}: {exc.error_count()} problem(s):"]
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "(top level)"
        line = f"  {location}: {error['msg']}"
        given = error.get("input")
        if given is not None and not isinstance(given, dict | list):
            line += f" (got {given!r})"
        lines.append(line)
    return "\n".join(lines)
