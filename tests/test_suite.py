"""Suite tests: reading a directory of case files, and the five grader specs.

Error-path classes live below these; mirror :class:`TestLoadSuite` when adding one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bakeoff.suite import (
    Case,
    ContainsSpec,
    ExactSpec,
    JsonSchemaSpec,
    NumericToleranceSpec,
    RegexSpec,
    Suite,
    SuiteError,
    load_suite,
    parse_case,
    run_grader,
)

EXACT_CASE = """
prompt: "echo: 4"
grader:
  kind: exact
  expected: "4"
reference: "4"
"""

CONTAINS_CASE = """
prompt: "echo: the capital is Paris"
grader:
  kind: contains
  substring: Paris
  case_sensitive: false
"""


def write_suite(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create a suite directory holding the named case files, and return it."""
    directory = tmp_path / "smoke"
    directory.mkdir()
    for name, text in files.items():
        (directory / name).write_text(text)
    return directory


class TestLoadSuite:
    def test_a_directory_of_cases_loads_in_filename_order(self, tmp_path: Path) -> None:
        directory = write_suite(
            tmp_path, {"02-second.yaml": CONTAINS_CASE, "01-first.yaml": EXACT_CASE}
        )
        suite = load_suite(directory)
        assert isinstance(suite, Suite)
        assert [case.id for case in suite.cases] == ["01-first", "02-second"]

    def test_the_suite_is_named_for_its_directory_and_knows_its_length(
        self, tmp_path: Path
    ) -> None:
        suite = load_suite(write_suite(tmp_path, {"a.yaml": EXACT_CASE}))
        assert suite.name == "smoke"
        assert len(suite) == 1

    def test_an_explicit_name_overrides_the_directory_name(self, tmp_path: Path) -> None:
        suite = load_suite(write_suite(tmp_path, {"a.yaml": EXACT_CASE}), name="arithmetic")
        assert suite.name == "arithmetic"

    def test_a_case_id_defaults_to_the_file_stem(self, tmp_path: Path) -> None:
        suite = load_suite(write_suite(tmp_path, {"two-plus-two.yml": EXACT_CASE}))
        assert suite.cases[0].id == "two-plus-two"

    def test_an_explicit_id_wins_over_the_file_stem(self, tmp_path: Path) -> None:
        suite = load_suite(write_suite(tmp_path, {"a.yaml": "id: named\n" + EXACT_CASE}))
        assert suite.cases[0].id == "named"

    def test_files_that_are_not_case_files_are_ignored(self, tmp_path: Path) -> None:
        directory = write_suite(tmp_path, {"a.yaml": EXACT_CASE, "README.md": "notes"})
        assert len(load_suite(directory)) == 1

    def test_a_reference_answer_is_optional(self, tmp_path: Path) -> None:
        suite = load_suite(write_suite(tmp_path, {"a.yaml": EXACT_CASE, "b.yaml": CONTAINS_CASE}))
        assert suite.cases[0].reference == "4"
        assert suite.cases[1].reference is None


class TestGraderSpecs:
    def parse(self, grader: dict[str, object]) -> Case:
        return parse_case({"prompt": "p", "grader": grader}, default_id="c", source="inline")

    def test_kind_picks_the_exact_spec(self) -> None:
        case = self.parse({"kind": "exact", "expected": "4"})
        assert isinstance(case.grader, ExactSpec)
        assert case.grader.expected == "4"
        assert case.grader.strip is True

    def test_kind_picks_the_contains_spec(self) -> None:
        case = self.parse({"kind": "contains", "substring": "Paris", "case_sensitive": False})
        assert isinstance(case.grader, ContainsSpec)
        assert case.grader.case_sensitive is False

    def test_kind_picks_the_regex_spec(self) -> None:
        case = self.parse({"kind": "regex", "pattern": r"\d+", "fullmatch": True})
        assert isinstance(case.grader, RegexSpec)
        assert case.grader.fullmatch is True

    def test_kind_picks_the_numeric_tolerance_spec(self) -> None:
        case = self.parse({"kind": "numeric_tolerance", "expected": 3.14, "tolerance": 0.05})
        assert isinstance(case.grader, NumericToleranceSpec)
        assert case.grader.tolerance == 0.05

    def test_the_json_schema_spec_reads_the_yaml_key_schema(self) -> None:
        case = self.parse({"kind": "json_schema", "schema": {"type": "object"}})
        assert isinstance(case.grader, JsonSchemaSpec)
        assert case.grader.json_schema == {"type": "object"}


class TestRunGrader:
    def test_exact_spec_passes_on_a_match(self) -> None:
        spec = ExactSpec(kind="exact", expected="4")
        result = run_grader(spec, "4")
        assert result.passed is True
        assert result.score == 1.0

    def test_contains_spec_passes_case_insensitive(self) -> None:
        spec = ContainsSpec(kind="contains", substring="Paris", case_sensitive=False)
        result = run_grader(spec, "the capital is PARIS")
        assert result.passed is True

    def test_regex_fullmatch_fails_on_partial_match(self) -> None:
        spec = RegexSpec(kind="regex", pattern=r"\d+", fullmatch=True)
        result = run_grader(spec, "42 is the answer")
        assert result.passed is False

    def test_numeric_tolerance_passes_inside_and_fails_outside(self) -> None:
        inside = NumericToleranceSpec(kind="numeric_tolerance", expected=3.14, tolerance=0.05)
        assert run_grader(inside, "3.16").passed is True

        outside = NumericToleranceSpec(kind="numeric_tolerance", expected=3.14, tolerance=0.05)
        assert run_grader(outside, "3.5").passed is False

    def test_json_schema_spec_passes_valid_and_fails_invalid(self) -> None:
        spec = JsonSchemaSpec(
            kind="json_schema",
            schema={"type": "object", "required": ["name"]},
        )
        assert run_grader(spec, '{"name": "alice"}').passed is True
        assert run_grader(spec, '{"age": 3}').passed is False


class TestSuiteErrors:
    """Assert that load_suite raises SuiteError with fixable messages."""

    def test_nonexistent_directory_raises(self) -> None:
        with pytest.raises(SuiteError) as exc:
            load_suite(Path("/this/path/does/not/exist"))
        msg = str(exc.value)
        assert "does not exist" in msg

    def test_empty_directory_raises(self, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        with pytest.raises(SuiteError) as exc:
            load_suite(empty_dir)
        msg = str(exc.value)
        assert "no case files" in msg

    def test_empty_prompt_raises(self, tmp_path: Path) -> None:
        directory = tmp_path / "smoke"
        directory.mkdir()
        (directory / "a.yaml").write_text('prompt: ""\ngrader:\n  kind: exact\n  expected: "x"\n')
        with pytest.raises(SuiteError) as exc:
            load_suite(directory)
        msg = str(exc.value)
        assert "prompt" in msg

    def test_unknown_grader_kind_raises(self, tmp_path: Path) -> None:
        directory = tmp_path / "smoke"
        directory.mkdir()
        (directory / "a.yaml").write_text("prompt: hello\ngrader:\n  kind: magic\n  stuff: true\n")
        with pytest.raises(SuiteError) as exc:
            load_suite(directory)
        msg = str(exc.value)
        # The message should list the valid kinds
        assert "exact" in msg
        assert "contains" in msg
        assert "regex" in msg
        assert "numeric_tolerance" in msg
        assert "json_schema" in msg

    def test_duplicate_case_ids_raises(self, tmp_path: Path) -> None:
        directory = tmp_path / "smoke"
        directory.mkdir()
        case_text = 'prompt: hello\ngrader:\n  kind: exact\n  expected: "x"\n'
        (directory / "a.yaml").write_text("id: dup\n" + case_text)
        (directory / "b.yaml").write_text("id: dup\n" + case_text)
        with pytest.raises(SuiteError) as exc:
            load_suite(directory)
        msg = str(exc.value)
        assert "duplicate" in msg
