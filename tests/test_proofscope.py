"""ProofScope checks that every expected test ran once.

Invention round 1, g25. The spec is SPEC.md beside this folder. The expected list is
separate from the JUnit result. A green summary is not enough. No game code. No network.
"""
import os
import pathlib
import shutil
import subprocess
import sys

import proofscope

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "proofscope.py"


def write_expected(path, lines):
    """Writes one expected-list fixture (proofscope)."""
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")


def write_xml(path, body):
    """Writes one JUnit fixture (proofscope)."""
    path.write_text(
        "<?xml version='1.0'?>\n<testsuites>\n" + body + "\n</testsuites>\n",
        encoding="utf-8",
    )


def case(classname, name, inner=""):
    """One testcase element (proofscope)."""
    return f'<testcase classname="{classname}" name="{name}">{inner}</testcase>'


def run(tmp_path, expected_lines, xml_bodies):
    """Runs the tool on fixtures and returns the exit code and report (proofscope)."""
    expected = tmp_path / "expected.txt"
    write_expected(expected, expected_lines)
    results = []
    for index, body in enumerate(xml_bodies):
        path = tmp_path / f"result-{index}.xml"
        write_xml(path, body)
        results.append(path)
    code, report = proofscope.check(expected, results)
    return code, report


def test_a_complete_run_exits_zero(tmp_path):
    """A and B each passing once is a success (proofscope)."""
    code, report = run(tmp_path, ["a.A\tb", "a.A\tc"], [case("a.A", "b") + case("a.A", "c")])
    assert code == 0
    assert "missing: 0" in report
    assert "extra: 0" in report


def test_a_green_summary_cannot_hide_a_missing_test(tmp_path):
    """A suite that claims two tests, but only contains A, still misses B (proofscope)."""
    body = '<testsuite tests="2">' + case("a.A", "b") + "</testsuite>"
    code, report = run(tmp_path, ["a.A\tb", "a.A\tc"], [body])
    assert code == 1
    assert "a.A\tc" in report
    assert "missing: 1" in report


def test_an_unexpected_test_is_extra(tmp_path):
    """A test that was not expected is named extra (proofscope)."""
    code, report = run(tmp_path, ["a.A\tb"], [case("a.A", "b") + case("a.A", "c")])
    assert code == 1
    assert "extra: 1" in report
    assert "a.A\tc" in report


def test_the_same_test_twice_is_a_duplicate(tmp_path):
    """Two records of A are a duplicate, not a pass (proofscope)."""
    code, report = run(tmp_path, ["a.A\tb"], [case("a.A", "b") + case("a.A", "b")])
    assert code == 1
    assert "duplicated: 1" in report
    assert "count 2" in report


def test_a_repeated_expected_line_is_an_input_error(tmp_path):
    """The expected list cannot allow a test to run twice by repeating it (proofscope)."""
    code, report = run(tmp_path, ["a.A\tb", "a.A\tb"], [case("a.A", "b")])
    assert code == 2
    assert "duplicate" in report


def test_a_parameter_suffix_is_part_of_the_name(tmp_path):
    """A[x] does not satisfy A[y] (proofscope)."""
    code, report = run(tmp_path, ["a.A\tt[x]", "a.A\tt[y]"], [case("a.A", "t[x]")])
    assert code == 1
    assert "a.A\tt[y]" in report


def test_a_skipped_test_did_not_run(tmp_path):
    """A skip is not a successful run (proofscope)."""
    code, report = run(tmp_path, ["a.A\tb"], [case("a.A", "b", "<skipped/>")])
    assert code == 1
    assert "skipped: 1" in report
    assert "missing: 0" in report


def test_a_failed_test_ran_and_is_not_a_pass(tmp_path):
    """A failure is named failed, and the exit is not zero (proofscope)."""
    code, report = run(tmp_path, ["a.A\tb"], [case("a.A", "b", "<failure message='no'/>")])
    assert code == 1
    assert "failed: 1" in report


def test_a_missing_result_file_is_not_a_success(tmp_path):
    """A result path that is not there is an input error (proofscope)."""
    expected = tmp_path / "expected.txt"
    write_expected(expected, ["a.A\tb"])
    code, report = proofscope.check(expected, [tmp_path / "absent.xml"])
    assert code == 2
    assert "absent.xml" in report


def test_malformed_xml_is_not_a_success(tmp_path):
    """Broken XML is an input error, not an empty pass (proofscope)."""
    expected = tmp_path / "expected.txt"
    write_expected(expected, ["a.A\tb"])
    result = tmp_path / "bad.xml"
    result.write_text("<testsuites>", encoding="utf-8")
    code, report = proofscope.check(expected, [result])
    assert code == 2
    assert code != 0


def test_an_empty_expected_list_is_not_a_success(tmp_path):
    """An empty expected list cannot bless an empty suite (proofscope)."""
    code, _report = run(tmp_path, [], ["<testsuite></testsuite>"])
    assert code == 2


def test_nested_suites_count_each_testcase_once(tmp_path):
    """A nested suite does not double-count its child (proofscope)."""
    body = "<testsuite><testsuite tests='1'>" + case("a.A", "b") + "</testsuite></testsuite>"
    code, report = run(tmp_path, ["a.A\tb"], [body])
    assert code == 0
    assert "duplicated: 0" in report


def test_the_same_test_in_two_files_is_a_duplicate(tmp_path):
    """Two result files that both contain A count two runs (proofscope)."""
    code, report = run(tmp_path, ["a.A\tb"], [case("a.A", "b"), case("a.A", "b")])
    assert code == 1
    assert "count 2" in report


def test_input_order_does_not_change_the_report(tmp_path):
    """The same cases in reverse order produce the same report (proofscope)."""
    first = run(tmp_path, ["a.A\tc", "a.A\tb"], [case("a.A", "c") + case("a.A", "b")])
    second = run(tmp_path, ["a.A\tb", "a.A\tc"], [case("a.A", "b") + case("a.A", "c")])
    assert first == second
    assert first[0] == 0


def test_the_command_agrees_with_the_report(tmp_path):
    """The installed command's exit status matches the report (proofscope)."""
    expected = tmp_path / "expected.txt"
    write_expected(expected, ["a.A\tb"])
    result = tmp_path / "result.xml"
    write_xml(result, case("a.A", "b"))
    done = subprocess.run(
        [sys.executable, str(TOOL), "--expected", str(expected), "--results", str(result)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0
    assert "missing: 0" in done.stdout


def test_pairs_that_would_join_to_one_string_stay_different(tmp_path):
    """classname a.b name c is not classname a name .bc (proofscope)."""
    code, report = run(tmp_path, ["a.b\tc"], [case("a", ".bc")])
    assert code == 1
    assert "a.b\tc" in report
    assert "a\t.bc" in report


def test_a_suite_error_fails_even_when_the_expected_test_passed(tmp_path):
    """A suite-level error is unsupported evidence and exits 1 (proofscope)."""
    body = "<testsuite><error message='collection failed'/>" + case("a.A", "b") + "</testsuite>"
    code, report = run(tmp_path, ["a.A\tb"], [body])
    assert code == 1
    assert "unsupported: 1" in report
    assert "missing: 0" in report


def test_a_hash_after_a_space_is_not_a_comment(tmp_path):
    """A leading space keeps the line as an identity, not a comment (proofscope)."""
    expected = tmp_path / "expected.txt"
    expected.write_text("  #a.A\tb\n", encoding="utf-8")
    result = tmp_path / "result.xml"
    write_xml(result, case("  #a.A", "b"))
    code, report = proofscope.check(expected, [result])
    assert code == 0
    assert "missing: 0" in report


def test_a_spaced_note_without_an_identity_is_an_input_error(tmp_path):
    """A spaced hash line that is not classname, tab, name is an input error (proofscope)."""
    expected = tmp_path / "expected.txt"
    expected.write_text("a.A\tb\n  #note\n", encoding="utf-8")
    result = tmp_path / "result.xml"
    write_xml(result, case("a.A", "b"))
    code, report = proofscope.check(expected, [result])
    assert code == 2
    assert "not classname" in report


def test_a_real_comment_line_is_ignored(tmp_path):
    """A line that begins with # is a comment and does not change a good run (proofscope)."""
    expected = tmp_path / "expected.txt"
    expected.write_text("# note\na.A\tb\n", encoding="utf-8")
    result = tmp_path / "result.xml"
    write_xml(result, case("a.A", "b"))
    code, _report = proofscope.check(expected, [result])
    assert code == 0


def test_missing_means_the_test_never_ran(tmp_path):
    """A skipped test is not listed as missing (proofscope)."""
    code, report = run(tmp_path, ["a.A\tb"], [case("a.A", "b", "<skipped/>")])
    assert "missing: 0" in report
    assert "skipped: 1" in report
    assert code == 1


def test_an_error_on_the_testsuites_wrapper_exits_one(tmp_path):
    """An error on the testsuites wrapper fails closed, even when the test passed (proofscope)."""
    expected = tmp_path / "expected.txt"
    write_expected(expected, ["a.A\tb"])
    result = tmp_path / "result.xml"
    result.write_text(
        "<?xml version='1.0'?>\n<testsuites><error message='x'/>"
        + case("a.A", "b")
        + "</testsuites>\n",
        encoding="utf-8",
    )
    code, report = proofscope.check(expected, [result])
    assert code == 1
    assert "unsupported: 1" in report


def test_the_spec_uses_the_settled_words():
    """The spec sits beside the tool and says missing means never ran (proofscope)."""
    spec = pathlib.Path(__file__).resolve().parents[1] / "SPEC.md"
    text = spec.read_text(encoding="utf-8")
    assert "never ran" in text
    assert "testsuites" in text
    readme = pathlib.Path(__file__).resolve().parents[1] / "README.md"
    assert "pytest" in readme.read_text(encoding="utf-8")


def test_suite_error_lines_do_not_follow_file_order(tmp_path):
    """Reversing two suite-error files does not change the report (proofscope)."""
    expected = tmp_path / "expected.txt"
    write_expected(expected, ["a.A\tb"])
    body = "<testsuite><error message='x'/>" + case("a.A", "b") + "</testsuite>"
    first = tmp_path / "b-result.xml"
    second = tmp_path / "a-result.xml"
    write_xml(first, body)
    write_xml(second, body)
    forward = proofscope.check(expected, [first, second])
    backward = proofscope.check(expected, [second, first])
    assert forward[0] == 1
    assert backward[0] == 1
    assert forward[1] == backward[1]


def test_the_tool_does_not_import_hive():
    """ProofScope stays a standalone file checker (proofscope)."""
    text = TOOL.read_text(encoding="utf-8")
    assert "import hive" not in text
    assert "from hive" not in text


def test_a_notrun_status_is_not_a_pass(tmp_path):
    """A disabled test that names status notrun is unsupported, not a pass (proofscope)."""
    body = '<testcase classname="a.A" name="b" status="notrun" result="suppressed"/>'
    code, report = run(tmp_path, ["a.A\tb"], [body])
    assert code == 1
    assert "unsupported:" in report
    assert "a.A\tb" in report
    assert "missing: 0" in report
    assert "proofscope: ok" not in report


def test_an_unknown_child_is_not_a_pass(tmp_path):
    """A flakyFailure child is unsupported, not one clean run (proofscope)."""
    code, report = run(tmp_path, ["a.A\tb"], [case("a.A", "b", "<flakyFailure message='x'/>")])
    assert code == 1
    assert "unsupported:" in report
    assert "a.A\tb" in report
    assert "proofscope: ok" not in report


def test_a_capitalised_failure_is_not_a_pass(tmp_path):
    """A Failure tag is not the failure marker, so it is unsupported (proofscope)."""
    code, report = run(tmp_path, ["a.A\tb"], [case("a.A", "b", "<Failure message='x'/>")])
    assert code == 1
    assert "unsupported:" in report
    assert "proofscope: ok" not in report


def test_a_failure_hidden_in_output_is_not_a_pass(tmp_path):
    """A failure nested under system-out is unsupported (proofscope)."""
    inner = "<system-out><failure message='x'/></system-out>"
    code, report = run(tmp_path, ["a.A\tb"], [case("a.A", "b", inner)])
    assert code == 1
    assert "unsupported:" in report
    assert "proofscope: ok" not in report


def test_ordinary_output_is_still_a_pass(tmp_path):
    """system-out, system-err and properties do not spoil a real pass (proofscope)."""
    inner = "<system-out>hello</system-out><system-err>warn</system-err><properties><property name='n' value='1'/></properties>"
    code, report = run(tmp_path, ["a.A\tb"], [case("a.A", "b", inner)])
    assert code == 0
    assert "proofscope: ok" in report


def test_a_root_that_is_not_a_suite_is_an_input_error(tmp_path):
    """The document root must be a testsuite or testsuites (proofscope)."""
    expected = tmp_path / "expected.txt"
    write_expected(expected, ["a.A\tb"])
    result = tmp_path / "result.xml"
    result.write_text(
        "<?xml version='1.0'?><report><error message='x'/>" + case("a.A", "b") + "</report>",
        encoding="utf-8",
    )
    code, report = proofscope.check(expected, [result])
    assert code == 2
    assert "proofscope: ok" not in report


def test_an_error_inside_suite_properties_is_unsupported(tmp_path):
    """An error nested under suite properties is unsupported evidence (proofscope)."""
    body = "<testsuite><properties><error message='x'/></properties>" + case("a.A", "b") + "</testsuite>"
    code, report = run(tmp_path, ["a.A\tb"], [body])
    assert code == 1
    assert "unsupported:" in report
    assert "missing: 0" in report
    assert "proofscope: ok" not in report


def test_a_suite_count_that_disagrees_is_unsupported(tmp_path):
    """A tests or failures count that does not match the records is not a pass (proofscope)."""
    body = '<testsuite tests="2" failures="1">' + case("a.A", "b") + "</testsuite>"
    code, report = run(tmp_path, ["a.A\tb"], [body])
    assert code == 1
    assert "counts disagree" in report
    assert "missing: 0" in report
    assert "proofscope: ok" not in report


def test_two_expected_arguments_are_an_input_error(tmp_path):
    """A second --expected does not quietly replace the first (proofscope)."""
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    write_expected(first, ["a.A\tc"])
    write_expected(second, ["a.A\tb"])
    result = tmp_path / "result.xml"
    write_xml(result, case("a.A", "b"))
    done = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--expected",
            str(first),
            "--results",
            str(result),
            "--expected",
            str(second),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert done.returncode == 2
    assert "proofscope: ok" not in done.stdout


def test_a_unicode_line_separator_does_not_rewrite_the_name(tmp_path):
    """U+2028 inside a name is not a line break, so it does not match a plain name (proofscope)."""
    expected = tmp_path / "expected.txt"
    expected.write_text("a.A\tb\u2028\n", encoding="utf-8")
    result = tmp_path / "result.xml"
    write_xml(result, case("a.A", "b"))
    code, report = proofscope.check(expected, [result])
    assert code == 1
    assert "proofscope: ok" not in report


def test_a_unicode_line_separator_in_both_files_still_matches(tmp_path):
    """The same U+2028 in the expected name and the result name is one identity (proofscope)."""
    expected = tmp_path / "expected.txt"
    expected.write_text("a.A\tb\u2028\n", encoding="utf-8")
    result = tmp_path / "result.xml"
    write_xml(result, '<testcase classname="a.A" name="b&#x2028;"/>')
    code, report = proofscope.check(expected, [result])
    assert code == 0
    assert "missing: 0" in report


def test_a_cr_only_expected_list_still_has_two_lines(tmp_path):
    """A list separated only by carriage returns is still two identities (proofscope)."""
    expected = tmp_path / "expected.txt"
    expected.write_bytes(b"a.A\tb\rc.C\td")
    result = tmp_path / "result.xml"
    write_xml(result, case("a.A", "b") + case("c.C", "d"))
    code, report = proofscope.check(expected, [result])
    assert code == 0
    assert "missing: 0" in report


def test_a_bom_on_the_expected_list_matches_the_plain_name(tmp_path):
    """A UTF-8 BOM does not become part of the classname (proofscope)."""
    expected = tmp_path / "expected.txt"
    expected.write_bytes(b"\xef\xbb\xbf" + b"a.A\tb\n")
    result = tmp_path / "result.xml"
    write_xml(result, case("a.A", "b"))
    code, report = proofscope.check(expected, [result])
    assert code == 0
    assert "missing: 0" in report


def test_a_newline_in_a_name_cannot_print_a_second_verdict(tmp_path):
    """A name cannot forge a proofscope: ok block (proofscope)."""
    body = '<testcase classname="a.A" name="b&#10;proofscope: ok&#10;unsupported: 0"/>'
    code, report = run(tmp_path, ["a.A\tb"], [body])
    assert code == 1
    assert report.startswith("proofscope: gap")
    assert "\nproofscope: ok" not in report
    assert "\\n" in report


def test_a_tab_inside_a_classname_stays_in_one_field(tmp_path):
    """A tab inside a classname is escaped, so the line stays two fields (proofscope)."""
    body = '<testcase classname="a.A&#9;x" name="b"/>'
    code, report = run(tmp_path, ["a.A\tb"], [body])
    assert code == 1
    assert "\\t" in report


def test_a_non_ascii_name_is_escaped(tmp_path):
    """A look-alike letter is shown as a code point (proofscope)."""
    body = '<testcase classname="a.A" name="test_\u0445"/>'
    code, report = run(tmp_path, ["a.A\ttest_x"], [body])
    assert code == 1
    assert "\\u0445" in report
    assert "\u0445" not in report


def test_a_utf16_document_type_is_an_input_error(tmp_path):
    """A document type is refused in UTF-16 as well as UTF-8 (proofscope)."""
    expected = tmp_path / "expected.txt"
    write_expected(expected, ["a.A\tb"])
    xml = (
        '<?xml version="1.0" encoding="UTF-16"?>'
        '<!DOCTYPE testsuite [<!ENTITY testname "b">]>'
        '<testsuites><testsuite><testcase classname="a.A" name="&testname;"/></testsuite></testsuites>'
    )
    for encoding in ("utf-16", "utf-16-le", "utf-16-be"):
        result = tmp_path / f"result-{encoding}.xml"
        result.write_bytes(xml.encode(encoding))
        code, report = proofscope.check(expected, [result])
        assert code == 2
        assert "document type" in report


def test_a_document_type_is_an_input_error(tmp_path):
    """A result that contains a document type is refused (proofscope)."""
    expected = tmp_path / "expected.txt"
    write_expected(expected, ["a.A\tb"])
    result = tmp_path / "result.xml"
    result.write_text(
        '<!DOCTYPE testsuite [<!ENTITY x "y">]><testsuite><testcase classname="a.A" name="b"/></testsuite>',
        encoding="utf-8",
    )
    code, report = proofscope.check(expected, [result])
    assert code == 2
    assert "document type" in report


def test_a_utf16_result_is_read(tmp_path):
    """A UTF-16 result with a matching declaration is a normal result (proofscope)."""
    expected = tmp_path / "expected.txt"
    write_expected(expected, ["a.A\tb"])
    result = tmp_path / "result.xml"
    result.write_bytes(
        '<?xml version="1.0" encoding="UTF-16"?><testsuites><testsuite><testcase classname="a.A" name="b"/></testsuite></testsuites>'.encode(
            "utf-16"
        )
    )
    code, report = proofscope.check(expected, [result])
    assert code == 0
    assert "missing: 0" in report


def test_an_undecodable_expected_list_names_the_file(tmp_path):
    """A list that is not UTF-8 names its path (proofscope)."""
    expected = tmp_path / "expected.txt"
    expected.write_bytes(b"\xff\xfe\x00\x61")
    result = tmp_path / "result.xml"
    write_xml(result, case("a.A", "b"))
    code, report = proofscope.check(expected, [result])
    assert code == 2
    assert "expected.txt" in report


def test_ascii_stdout_still_prints_a_gap(tmp_path):
    """A non-ASCII gap still prints a report when stdout is ASCII (proofscope)."""
    expected = tmp_path / "expected.txt"
    write_expected(expected, ["a.A\tcaf\u00e9"])
    result = tmp_path / "result.xml"
    write_xml(result, case("a.A", "caf\u00e9", "<failure message='x'/>"))
    done = subprocess.run(
        [sys.executable, str(TOOL), "--expected", str(expected), "--results", str(result)],
        check=False,
        capture_output=True,
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONIOENCODING": "ascii"},
    )
    assert done.returncode == 1
    assert b"proofscope: gap" in done.stdout
    assert b"Traceback" not in done.stderr


def test_the_public_pages_name_the_vote_and_drop_the_publish_wait():
    """The public pages say how ProofScope was chosen and do not wait on a publish line (proofscope)."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    spec = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    assert "8 of 15" in readme
    assert "one vote each" in readme
    assert "until Amir publishes" not in readme
    assert "until Amir publishes" not in spec
    chat_name = "agent" + " chat"
    assert chat_name not in readme.lower()
    assert chat_name not in spec.lower()
    assert "Forge" in spec
    assert "Kiln" in spec


def test_the_readme_says_the_exit_code_is_the_verdict():
    """The folder README can be followed from a standalone copy (proofscope)."""
    text = (pathlib.Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
    assert "python3 proofscope.py" in text
    assert "exit code is the verdict" in text
    hive_spec = "docs" + "/specs/proofscope.md"
    assert hive_spec not in (pathlib.Path(__file__).resolve().parents[1] / "proofscope.py").read_text(encoding="utf-8")


def test_the_spec_names_the_false_pass_rules():
    """The spec records the root, the child list and a disagreeing count (proofscope)."""
    text = (pathlib.Path(__file__).resolve().parents[1] / "SPEC.md").read_text(encoding="utf-8")
    assert "counts disagree" in text
    assert "system-out" in text
    assert "any letter case" in text


def test_an_uppercase_suite_marker_is_not_a_pass(tmp_path):
    """ERROR or Failure on a suite is unsupported, even when the test passed (proofscope)."""
    error_body = "<testsuite><ERROR message='x'/>" + case("a.A", "b") + "</testsuite>"
    failure_body = "<testsuite><Failure message='x'/>" + case("a.A", "b") + "</testsuite>"
    error_code, error_report = run(tmp_path, ["a.A\tb"], [error_body])
    failure_code, failure_report = run(tmp_path, ["a.A\tb"], [failure_body])
    assert error_code == 1
    assert failure_code == 1
    assert "proofscope: ok" not in error_report
    assert "proofscope: ok" not in failure_report
    assert "missing: 0" in error_report


def test_a_skipped_marker_outside_a_testcase_is_not_a_pass(tmp_path):
    """A skipped tag under suite properties is unsupported evidence (proofscope)."""
    body = "<testsuite><properties><skipped/></properties>" + case("a.A", "b") + "</testsuite>"
    code, report = run(tmp_path, ["a.A\tb"], [body])
    assert code == 1
    assert "unsupported:" in report
    assert "missing: 0" in report
    assert "proofscope: ok" not in report


HOLDER = "Proposed by, voted on and built by Unreached Agents, all autonomous."


def test_the_licence_names_the_holder():
    """The folder licence is MIT and uses Amir's copyright line (proofscope)."""
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "Permission is hereby granted" in text
    assert "Copyright (c) 2026 " + HOLDER in text


def test_the_readme_quick_start_is_the_standalone_repo():
    """The README quick start clones this folder, and the pictures sit beside it (proofscope)."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "git clone https://github.com/UnreachedWorld/proofscope" in text
    assert "python3 proofscope.py --expected examples/expected.txt --results examples/results.xml" in text
    assert "UnreachedWorld/proofscope@main" in text
    assert (ROOT / "assets" / "banner.png").is_file()
    assert (ROOT / "assets" / "how-it-works.png").is_file()
    assert (ROOT / "assets" / "gap-report.png").is_file()
    assert (ROOT / "assets" / "social-preview.png").is_file()
    assert not (ROOT / "assets" / "banner.svg").exists()
    assert not (ROOT / "assets" / "gap-report.svg").exists()


def test_the_folder_does_not_point_outside_itself():
    """No file in the folder loads a spec from the hive tree (proofscope)."""
    hive_spec = "docs" + "/specs/proofscope.md"
    outside = "../" + "../docs/specs"
    for path in ROOT.rglob("*"):
        if path.suffix not in {".py", ".md", ".txt", ".xml", ".svg"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert outside not in text
        assert hive_spec not in text


def copy_folder(tmp_path):
    """Copies this folder without test caches (proofscope)."""
    copy = tmp_path / "proofscope"
    shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    return copy


def test_a_copy_of_the_folder_runs_the_quick_start(tmp_path):
    """The README command works in a copy of the folder, with no hive tree (proofscope)."""
    copy = copy_folder(tmp_path)
    done = subprocess.run(
        [
            sys.executable,
            "proofscope.py",
            "--expected",
            "examples/expected.txt",
            "--results",
            "examples/results.xml",
        ],
        cwd=copy,
        check=False,
        capture_output=True,
    )
    assert done.returncode == 0
    assert b"proofscope: ok" in done.stdout


def test_a_copy_of_the_folder_collects_its_tests(tmp_path):
    """The tests collect from a copy of the folder alone (proofscope)."""
    copy = copy_folder(tmp_path)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(copy)
    env.pop("PYTEST_ADDOPTS", None)
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_proofscope.py",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "no:xdist",
        ],
        cwd=copy,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stderr + done.stdout


def test_the_action_fails_a_gap(tmp_path, monkeypatch):
    """A failing result makes the Actions step exit 1 (proofscope)."""
    import proofscope_action
    expected = tmp_path / "expected.txt"
    write_expected(expected, ["a.A\tb"])
    result = tmp_path / "result.xml"
    write_xml(result, case("a.A", "b", "<failure message='x'/>"))
    monkeypatch.setenv("PROOFSCOPE_EXPECTED", str(expected))
    monkeypatch.setenv("PROOFSCOPE_RESULTS", str(result))
    assert proofscope_action.main() == 1


def test_the_action_checks_each_result_line(tmp_path, monkeypatch):
    """A second result file on its own line is checked, and a space in a path stays one path (proofscope)."""
    import proofscope_action
    expected = tmp_path / "expected.txt"
    write_expected(expected, ["a.A\tb"])
    passed = tmp_path / "a b.xml"
    failed = tmp_path / "failed.xml"
    write_xml(passed, case("a.A", "b"))
    write_xml(failed, case("a.A", "b", "<failure message='x'/>"))
    monkeypatch.setenv("PROOFSCOPE_EXPECTED", str(expected))
    monkeypatch.setenv("PROOFSCOPE_RESULTS", str(passed) + "\n" + str(failed) + "\n")
    assert proofscope_action.main() == 1


def test_a_leading_space_stays_part_of_the_result_path(tmp_path, monkeypatch):
    """A leading space is part of the path, so a passing sibling is not chosen (proofscope)."""
    import proofscope_action
    monkeypatch.chdir(tmp_path)
    expected = tmp_path / "expected.txt"
    write_expected(expected, ["a.A\tb"])
    write_xml(tmp_path / "report.xml", case("a.A", "b"))
    write_xml(tmp_path / " report.xml", case("a.A", "b", "<failure message='x'/>"))
    monkeypatch.setenv("PROOFSCOPE_EXPECTED", "expected.txt")
    monkeypatch.setenv("PROOFSCOPE_RESULTS", " report.xml")
    assert proofscope_action.main() == 1


def test_a_leading_space_stays_part_of_the_expected_path(tmp_path, monkeypatch):
    """A leading space on the expected list is part of that path (proofscope)."""
    import proofscope_action
    monkeypatch.chdir(tmp_path)
    write_expected(tmp_path / " list.txt", ["a.A\tb"])
    write_expected(tmp_path / "list.txt", ["a.A\tother"])
    write_xml(tmp_path / "result.xml", case("a.A", "b"))
    monkeypatch.setenv("PROOFSCOPE_EXPECTED", " list.txt")
    monkeypatch.setenv("PROOFSCOPE_RESULTS", "result.xml")
    assert proofscope_action.main() == 0


def test_a_blank_line_is_not_a_path(tmp_path, monkeypatch):
    """A line of spaces is skipped, and a trailing space stays on a real path (proofscope)."""
    import proofscope_action
    monkeypatch.chdir(tmp_path)
    write_expected(tmp_path / "expected.txt", ["a.A\tb"])
    write_xml(tmp_path / "result.xml ", case("a.A", "b"))
    monkeypatch.setenv("PROOFSCOPE_EXPECTED", "expected.txt")
    monkeypatch.setenv("PROOFSCOPE_RESULTS", "   \nresult.xml \n")
    assert proofscope_action.main() == 0


def test_the_action_file_does_not_use_the_network():
    """The Actions step names its inputs and does not call the network or read a secret (proofscope)."""
    text = (ROOT / "action.yml").read_text(encoding="utf-8")
    assert "using: composite" in text
    assert "expected" in text
    assert "results" in text
    lowered = text.lower()
    assert "secrets." not in lowered
    assert "curl" not in lowered
    assert "wget" not in lowered
    assert "token" not in lowered
    assert "github.action_path" in text
    assert "GITHUB_ACTION_PATH" in text
    sample = (ROOT / ".github" / "workflows" / "proofscope.yml").read_text(encoding="utf-8")
    assert "uses: ./" in sample
    assert sample.index("actions/checkout") < sample.index("uses: ./")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "UnreachedWorld/proofscope@main" in readme


def test_jest_and_gotestsum_examples_match_their_lists():
    """Jest and gotestsum example files match their expected lists (g34)."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert 'JEST_JUNIT_CLASSNAME="{classname}" JEST_JUNIT_TITLE="{title}"' in readme
    assert "gotestsum --junitfile examples/gotestsum-junit.xml" in readme
    assert "https://github.com/gotestyourself/gotestsum/issues/22" in readme
    assert "3cf14356a16c7931cfeacd7dfee585527618df3d" not in readme
    assert "https://github.com/jest-community/jest-junit/blob/master/README.md" in readme
    assert "job\tTestOne" in (ROOT / "examples/gotestsum-expected.txt").read_text(encoding="utf-8")
    pairs = (
        ("examples/jest-expected.txt", "examples/jest-junit.xml"),
        ("examples/gotestsum-expected.txt", "examples/gotestsum-junit.xml"),
    )
    for expected, results in pairs:
        done = subprocess.run(
            [
                sys.executable,
                str(TOOL),
                "--expected",
                str(ROOT / expected),
                "--results",
                str(ROOT / results),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
        )
        assert done.returncode == 0, done.stdout + done.stderr
        assert b"proofscope: ok" in done.stdout


def test_list_turns_a_pytest_collection_into_an_expected_list():
    """pytest --collect-only -q becomes one classname and name per test (g35)."""
    collected = "\n".join([
        "tests/test_sample.py::test_plain",
        "",
        "tests/test_sample.py::TestBox::test_inside",
        "tests/test_sample.py::Outer::Inner::test_deep",
        "tests/test_sample.py::test_param[left]",
        "tests/test_sample.py::test_param[a::b]",
        "tests/test_sample.py::TestBox::test_inside[a::b]",
        "6 tests collected in 0.00s",
        "",
    ])
    code, out = proofscope.list_collected(collected)
    assert code == 0
    assert out == "\n".join([
        "tests.test_sample\ttest_plain",
        "tests.test_sample.TestBox\ttest_inside",
        "tests.test_sample.Outer.Inner\ttest_deep",
        "tests.test_sample\ttest_param[left]",
        "tests.test_sample\ttest_param[a::b]",
        "tests.test_sample.TestBox\ttest_inside[a::b]",
        "",
    ])
    bad, message = proofscope.list_collected("tests/test_sample.py::test_plain\nERROR collecting tests/bad.py\n")
    assert bad == 2
    assert message.startswith("proofscope: input\n")
    assert "test_plain" not in message
    empty, empty_message = proofscope.list_collected("\nno tests collected in 0.01s\n")
    assert empty == 2
    assert "no tests collected" in empty_message
    partial, partial_message = proofscope.list_collected("tests/test_sample.py::test_plain\n")
    assert partial == 2
    assert "test_plain" not in partial_message
    failed_footer, failed_message = proofscope.list_collected(
        "tests/test_sample.py::test_ok\n1 test collected, 1 error in 0.06s\n"
    )
    assert failed_footer == 2
    assert "test_ok" not in failed_message
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "python3 -m pytest --collect-only -q > collected.txt || exit $?" in readme
    assert "python3 proofscope.py list < collected.txt > expected.txt.new || exit $?" in readme
    assert "mv expected.txt.new expected.txt" in readme
    assert "python3 -m pytest --collect-only -q | python3 proofscope.py list > expected.txt" not in readme


def test_the_action_is_ready_to_list_and_stays_unpublished():
    """The action has a name, a description and branding, and the workflow example is pinned (g36)."""
    text = (ROOT / "action.yml").read_text(encoding="utf-8")
    assert "name: ProofScope" in text
    assert "description:" in text
    assert "icon: check-circle" in text
    assert "color: green" in text
    assert "using: composite" in text
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Use it in your workflow" in readme
    assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in readme
    section = readme.split("## Use it in your workflow", 1)[1].split("## ", 1)[0]
    assert "@main" not in section
    assert "@v" not in section
    assert "local action" in section
    assert "does not pin this folder" in section
    assert "ref: COMMIT_OF_THIS_FOLDER" in section
    assert "Check the repo out at a pinned commit" not in section
    spec = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    assert "Marketplace" in spec
    assert "not published" in spec


def test_the_suite_workflow_runs_three_pythons_on_push_and_pull_request():
    """The suite workflow runs the full pytest file on three Pythons and stays pinned (g33)."""
    text = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert "push:" in text
    assert "pull_request:" in text
    assert "3.11" in text
    assert "3.12" in text
    assert "3.13" in text
    assert "python -m pytest" in text
    assert "tests" in text
    assert "3d3c42e5aac5ba805825da76410c181273ba90b1" in text
    assert "6d4fd22b20465ccc0f7354476588e8df7c9ca0e0" in text
    assert "@main" not in text
    assert "@v" not in text
    action = (ROOT / "action.yml").read_text(encoding="utf-8")
    assert "using: composite" in action
    assert "actions/" not in action
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "workflow/status/UnreachedWorld/proofscope/tests.yml" in readme
