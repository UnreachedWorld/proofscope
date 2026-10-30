"""Runs ProofScope from a GitHub Actions step.

The step lives in this folder (g28, design SPEC.md). It reads the expected
list and the result paths from the environment, then returns ProofScope's
exit code. A gap fails the job. It does not use the network and it does not
read a secret.
"""
import os
import sys

import proofscope


def result_paths(text):
    """Returns one result path per line. A blank line is skipped. Other characters stay (proofscope)."""
    paths = []
    for line in text.splitlines():
        if line.strip() == "":
            continue
        paths.append(line)
    return paths


def main():
    """Runs one Actions check and returns its exit code (proofscope)."""
    expected = os.environ.get("PROOFSCOPE_EXPECTED", "")
    if expected.strip() == "":
        expected = ""
    results = result_paths(os.environ.get("PROOFSCOPE_RESULTS", ""))
    if expected == "" or not results:
        sys.stdout.write("proofscope: input\nexpected list and result files are required\n")
        return 2
    argv = ["--expected", expected]
    for path in results:
        argv.append("--results")
        argv.append(path)
    return proofscope.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
