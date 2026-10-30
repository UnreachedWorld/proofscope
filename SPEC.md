# ProofScope, first version

What this is: a small standalone tool that checks an explicit list of expected tests against a JUnit XML result. It checks that every expected test ran once. A green total in the XML is not evidence. This is invention round 1, Forge's idea, built by Kiln. The tool is this folder. It imports no game code. This file is the spec, so a copy of this folder stands alone. The quick start is in README.md. The GitHub Actions step in `action.yml` runs the same check and fails the job when the exit code is not 0. It does not use the network. It stays a short composite step and does not call another action. `.github/workflows/tests.yml` runs the full pytest suite on push and on pull request, on Python 3.11, 3.12 and 3.13. The checkout and Python setup in that file are pinned to commits. The sample workflow is still started by hand.

## What it checks

The expected list is a separate file. The tool never builds that list from the result it is checking.

An identity is the exact pair `(classname, name)` from a `<testcase>` element. The name keeps any parameter suffix. The tool does not trim, join, or otherwise rewrite the two strings. A testcase missing `classname` or `name` is an input error.

Each expected line is `classname`, a tab, then `name`. A line break is a line feed, a carriage return, or both. Any other separator stays inside the name. Blank lines are ignored. Only a line whose first character is `#` is a comment. A line that starts with a space and then `#` is not a comment. If that line is classname, a tab, and name, it is an expected identity, spaces included. Otherwise it is an input error. A repeated expected identity is an input error. It does not raise the number of times that test may run.

The document root must be `testsuite` or `testsuites`. Anything else is an input error.

The tool reads `<testcase>` records only, including ones nested in suites, once each. A suite's `tests` count is not a substitute for those records. When a `testsuite` carries `tests`, `failures`, `errors` or `skipped` and that number does not match its direct testcases, the report says `counts disagree` and the exit is 1. A `failure`, `error` or `skipped` tag, in any letter case, whose parent is not a `testcase`, including one on a `testsuite`, on the `testsuites` wrapper, or nested under properties, is unsupported evidence, even when a testcase in that file passed. The report names that suite error and the exit is 1.

A testcase with `<skipped>` was not executed. A testcase with `<failure>` or `<error>` did run, and did not succeed. `system-out`, `system-err` and `properties` may sit beside those markers. Any other direct child is unsupported. A `failure`, `error` or `skipped` nested under something that is not its own testcase is unsupported. A `status` attribute other than `run`, or a `result` attribute other than `completed`, is unsupported. The report names that record and the exit is 1. Any other testcase ran and succeeded. The command takes one `--expected` list. A second one is an input error.

More than one result file is allowed. The same identity in two files counts twice. Passing the same file twice counts twice.

## The report and the exit

The report is plain text. Identities are sorted by classname, then name. Suite-error lines are sorted too. The order of the inputs does not change the report.

The exit code is the verdict. The report text is for a person to read. Printed identities escape tabs, line breaks and letters outside ASCII, so a name cannot look like a second verdict. A result file that contains a document type is an input error, including a UTF-16 file. A UTF-8 byte order mark on the expected list is ignored.

Exit 0 means every expected identity ran once, succeeded, and no other testcase appeared. A wrapper error or a suite error means this is not exit 0.

Exit 1 is a gap. The report names each of these, with the observed count for a duplicate:

- missing: the expected test never ran. A skipped, failed, duplicated or unsupported test is not listed here
- extra: present, and not expected
- duplicated: present more than once
- skipped: present as skipped
- failed: present as a failure or an error
- unsupported: a suite-level or testsuites-wrapper error or failure, a counts disagree line, or one testcase that is not a single clean run

A skipped or failed expected test is not counted as a successful run. It is not described as passing.

Exit 2 is an input error: a missing file, unreadable text, malformed XML, a root that is not a suite, a bad expected line, a duplicate expected identity, an empty expected list, more than one expected list, or a result with no testcase and no suite-level error. An empty or broken result is never a success.

## What this does not do

It does not prove the result is fresh, that it came from the intended source, or that a test nobody listed was supposed to run. It does not discover tests, read other report formats, retry failures, or talk to a network.
