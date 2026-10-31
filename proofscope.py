"""ProofScope checks that every expected test ran once.

It reads an expected list and one or more JUnit XML files, then reports missing,
extra and duplicated tests. A green total in the XML is not evidence. Design:
SPEC.md in this folder (g25). This file imports no game code and does not use
the network.
"""
import argparse
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


def local_name(tag):
    """Returns an XML tag without its namespace (proofscope)."""
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def show_field(text):
    """Shows one field with controls and non-ASCII letters escaped (proofscope)."""
    shown = []
    for char in text:
        code = ord(char)
        if char == "\\":
            shown.append("\\\\")
        elif char == "\n":
            shown.append("\\n")
        elif char == "\r":
            shown.append("\\r")
        elif char == "\t":
            shown.append("\\t")
        elif code < 32 or code == 127:
            shown.append(f"\\x{code:02x}")
        elif code > 126:
            shown.append(f"\\u{code:04x}")
        else:
            shown.append(char)
    return "".join(shown)


def identity_text(identity):
    """Writes one identity so a name cannot forge a second report (proofscope)."""
    classname, name = identity
    return show_field(classname) + "\t" + show_field(name)


def load_expected(path):
    """Reads the expected identities. A bad or empty list is an input error (proofscope)."""
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError(f"expected list {path} is not UTF-8: {error}") from error
    except OSError as error:
        raise ValueError(f"cannot read expected list {path}: {error.strerror}") from error
    seen = []
    known = set()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for line_number, raw in enumerate(text.split("\n"), start=1):
        if raw.strip() == "":
            continue
        if raw.startswith("#"):
            continue
        parts = raw.split("\t")
        if len(parts) != 2 or parts[0] == "" or parts[1] == "":
            raise ValueError(f"expected list {path}:{line_number} is not classname, a tab, then name")
        identity = (parts[0], parts[1])
        if identity in known:
            raise ValueError(f"expected list has a duplicate: {identity_text(identity)}")
        known.add(identity)
        seen.append(identity)
    if not seen:
        raise ValueError(f"expected list {path} is empty")
    return seen


def parents_of(root):
    """Maps each element to its parent so a marker can be tied to a testcase (proofscope)."""
    parents = {}
    for parent in root.iter():
        for child in list(parent):
            parents[child] = parent
    return parents


def inside_other_testcase(element, case, parents):
    """Says whether element belongs to a testcase nested inside case (proofscope)."""
    current = parents.get(element)
    while current is not None and current is not case:
        if local_name(current.tag) == "testcase":
            return True
        current = parents.get(current)
    return False


def case_unsupported(case, parents):
    """Says whether this testcase is not one clean run (proofscope)."""
    status = case.attrib.get("status")
    if status is not None and status != "run":
        return True
    result = case.attrib.get("result")
    if result is not None and result != "completed":
        return True
    allowed = {"skipped", "failure", "error", "system-out", "system-err", "properties"}
    for child in list(case):
        if local_name(child.tag) not in allowed:
            return True
    markers = {"skipped", "failure", "error"}
    for element in case.iter():
        if element is case:
            continue
        if inside_other_testcase(element, case, parents):
            continue
        marker = local_name(element.tag)
        if marker.lower() not in markers:
            continue
        parent = parents.get(element)
        if parent is case and marker in markers:
            continue
        return True
    return False


def outcome(case, parents):
    """Classifies one testcase as passed, skipped, failed or unsupported (proofscope)."""
    if case_unsupported(case, parents):
        return "unsupported"
    children = [local_name(child.tag) for child in list(case)]
    if "skipped" in children:
        return "skipped"
    if "failure" in children or "error" in children:
        return "failed"
    return "passed"


def loose_marker(root, parents):
    """Says whether a failure, error or skipped marker sits outside a testcase (proofscope)."""
    for element in root.iter():
        if local_name(element.tag).lower() not in {"failure", "error", "skipped"}:
            continue
        parent = parents.get(element)
        if parent is None or local_name(parent.tag) != "testcase":
            return True
    return False


def counts_disagree(suite):
    """Says whether a testsuite's own counts do not match its direct testcases (proofscope)."""
    if local_name(suite.tag) != "testsuite":
        return False
    cases = [child for child in list(suite) if local_name(child.tag) == "testcase"]
    skipped = 0
    errors = 0
    failures = 0
    for case in cases:
        names = [local_name(child.tag) for child in list(case)]
        if "skipped" in names:
            skipped = skipped + 1
        elif "error" in names:
            errors = errors + 1
        elif "failure" in names:
            failures = failures + 1
    actual = {"tests": len(cases), "failures": failures, "errors": errors, "skipped": skipped}
    for key, count in actual.items():
        if key in suite.attrib and suite.attrib[key] != str(count):
            return True
    return False


def document_type(data):
    """Says whether the result bytes declare a document type in UTF-8 or UTF-16 (proofscope)."""
    if b"<!DOCTYPE" in data:
        return True
    if "<!DOCTYPE".encode("utf-16-le") in data:
        return True
    if "<!DOCTYPE".encode("utf-16-be") in data:
        return True
    return False


def load_results(paths):
    """Reads every testcase once from each result file (proofscope)."""
    records = []
    unsupported = []
    for path in paths:
        file_path = Path(path)
        try:
            data = file_path.read_bytes()
        except OSError as error:
            raise ValueError(f"cannot read result {path}: {error.strerror}") from error
        if document_type(data):
            raise ValueError(f"result {path} contains a document type")
        try:
            root = ET.fromstring(data)
        except ET.ParseError as error:
            raise ValueError(f"result {path} is not XML: {error}") from error
        if local_name(root.tag) not in {"testsuite", "testsuites"}:
            raise ValueError(f"result {path} root is not a testsuite")
        parents = parents_of(root)
        suite_error = loose_marker(root, parents)
        if suite_error:
            unsupported.append(f"suite error in {path}")
        count_error = any(counts_disagree(element) for element in root.iter())
        if count_error:
            unsupported.append(f"counts disagree in {path}")
        cases = [element for element in root.iter() if local_name(element.tag) == "testcase"]
        if not cases and not suite_error and not count_error:
            raise ValueError(f"result {path} has no testcase")
        for case in cases:
            classname = case.attrib.get("classname", "")
            name = case.attrib.get("name", "")
            if classname == "" or name == "":
                raise ValueError(f"result {path} has a testcase without classname and name")
            kind = outcome(case, parents)
            identity = (classname, name)
            records.append((identity, kind))
            if kind == "unsupported":
                unsupported.append("unsupported record " + identity_text(identity))
    return records, unsupported


def check(expected_path, result_paths):
    """Compares the expected list with the results and returns an exit code and a report (proofscope)."""
    try:
        expected = load_expected(expected_path)
        records, unsupported = load_results(result_paths)
    except ValueError as error:
        return 2, "proofscope: input\n" + str(error) + "\n"
    passed = Counter(identity for identity, kind in records if kind == "passed")
    skipped = sorted({identity for identity, kind in records if kind == "skipped"})
    failed = sorted({identity for identity, kind in records if kind == "failed"})
    skipped_set = set(skipped)
    failed_set = set(failed)
    unsupported_ids = {identity for identity, kind in records if kind == "unsupported"}
    observed = Counter(identity for identity, _kind in records)
    expected_set = set(expected)
    missing = sorted(
        identity
        for identity in expected
        if passed[identity] == 0
        and identity not in skipped_set
        and identity not in failed_set
        and identity not in unsupported_ids
    )
    extra = sorted(identity for identity in observed if identity not in expected_set)
    duplicated = sorted(identity for identity, count in observed.items() if count > 1)
    sections = [
        ("missing", missing, None),
        ("extra", extra, None),
        ("duplicated", duplicated, observed),
        ("skipped", skipped, None),
        ("failed", failed, None),
    ]
    unsupported = sorted(unsupported)
    gap = any(items for _title, items, _counts in sections) or bool(unsupported)
    lines = ["proofscope: gap" if gap else "proofscope: ok"]
    lines.append(f"unsupported: {len(unsupported)}")
    for item in unsupported:
        lines.append(item)
    for title, items, counts in sections:
        lines.append(f"{title}: {len(items)}")
        for identity in items:
            if counts is None:
                lines.append(identity_text(identity))
            else:
                lines.append(identity_text(identity) + f" count {counts[identity]}")
    return (1 if gap else 0), "\n".join(lines) + "\n"


def collected_footer(line):
    """Says whether a line is pytest's collected-tests summary (g35)."""
    parts = line.split(" ")
    if len(parts) < 3:
        return False
    if not parts[0].isdigit():
        return False
    if parts[1] not in ("test", "tests"):
        return False
    return parts[2] == "collected"


def identity_from_node(line):
    """Turns one pytest node id into classname, tab, name (g35)."""
    head, bracket, tail = line.partition("[")
    if "::" not in head:
        return None
    path, sep, rest = head.partition("::")
    if sep != "::":
        return None
    if not path.endswith(".py"):
        return None
    if path.startswith("/") or " " in path:
        return None
    module = path[:-3].replace("/", ".")
    if module == "" or module.startswith("."):
        return None
    if rest == "":
        return None
    pieces = rest.split("::")
    if any(piece == "" for piece in pieces):
        return None
    name = pieces[-1] + bracket + tail
    classes = pieces[:-1]
    classname = module
    if classes:
        classname = module + "." + ".".join(classes)
    return classname + "\t" + name


def list_collected(text):
    """Turns pytest --collect-only -q text into an expected list (g35)."""
    rows = []
    saw_footer = False
    for raw in text.splitlines():
        line = raw.strip()
        if line == "":
            continue
        if line.startswith("no tests collected"):
            continue
        if collected_footer(line):
            saw_footer = True
            continue
        identity = identity_from_node(line)
        if identity is None:
            return 2, "proofscope: input\nnot a collected test: " + line + "\n"
        rows.append(identity)
    if not saw_footer or not rows:
        return 2, "proofscope: input\nno tests collected\n"
    return 0, "\n".join(rows) + "\n"


def main(argv=None):
    """Runs one check, or writes an expected list, from the command line (proofscope, g35)."""
    try:
        sys.stdout.reconfigure(errors="backslashreplace")
    except (AttributeError, OSError):
        pass
    incoming = sys.argv[1:] if argv is None else list(argv)
    if incoming[:1] == ["list"]:
        if len(incoming) != 1:
            sys.stdout.write("proofscope: input\nlist reads the collected tests on standard input\n")
            return 2
        code, report = list_collected(sys.stdin.read())
        sys.stdout.write(report)
        return code
    parser = argparse.ArgumentParser(prog="proofscope")
    parser.add_argument("--expected", required=True, action="append")
    parser.add_argument("--results", required=True, action="append")
    args = parser.parse_args(incoming)
    if len(args.expected) != 1:
        sys.stdout.write("proofscope: input\none expected list only\n")
        return 2
    code, report = check(args.expected[0], args.results)
    sys.stdout.write(report)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
