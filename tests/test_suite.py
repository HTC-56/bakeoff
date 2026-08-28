"""Suite tests: reading a directory of case files, and the five grader specs.

Error-path classes live below these; mirror :class:`TestLoadSuite` when adding one.
"""

from __future__ import annotations

from pathlib import Path

from bakeoff.suite import (
    Case,
    ContainsSpec,
    ExactSpec,
    JsonSchemaSpec,
    NumericToleranceSpec,
    RegexSpec,
    Suite,
    load_suite,
    parse_case,
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
