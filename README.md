<p align="center"><img src="assets/banner.png" alt="ProofScope: your tests passed. Did they all run?" width="100%"></p>

<p align="center">
<img src="https://img.shields.io/badge/license-MIT-3DDC97?style=flat-square" alt="MIT licence">
<img src="https://img.shields.io/badge/python-3-3DDC97?style=flat-square" alt="Python 3">
<img src="https://img.shields.io/badge/install-nothing-3DDC97?style=flat-square" alt="Nothing to install">
<img src="https://img.shields.io/badge/built%20by-AI%20agents-F4EFE6?style=flat-square&labelColor=0D1821" alt="Built by AI agents">
</p>

# ProofScope

**Your tests passed. Did they all run?**

When your tests come back green, it feels like proof that everything works. But green only means the tests that *ran* passed. If one quietly didn't run, because a file was skipped, a setting changed or a folder was never picked up, the report still says "all passed", and nobody notices.

It's like a teacher marking homework: every paper handed in got an A, but nobody took the register, so no one noticed a student was missing.

**ProofScope takes the register.** You give it the list of tests you expect and your test report. It tells you, in plain words, whether every test on your list really ran, once, and passed.

<p align="center"><img src="assets/how-it-works.png" alt="Your list has five tests. The report says four passed, all green. ProofScope shows that Refunds work never ran." width="100%"></p>

## What it catches

| | What it means |
|---|---|
| **Missing** | On your list, but it never ran. |
| **Ran twice** | Counted more than once, so the total looks bigger than it is. |
| **Skipped** | It was there, but didn't actually run. |
| **Failed** | It ran and didn't pass. |
| **Extra** | It ran, but it isn't on your list. |
| **Can't trust it** | Something in the report doesn't add up. ProofScope says so instead of guessing. |

If nothing is wrong, you get one word: **ok**.

## Try it in 30 seconds

You need Python 3. There's nothing to install.

```
git clone https://github.com/UnreachedWorld/proofscope
cd proofscope
python3 proofscope.py --expected examples/expected.txt --results examples/results.xml
```

You'll see:

```
proofscope: ok
unsupported: 0
missing: 0
extra: 0
duplicated: 0
skipped: 0
failed: 0
```

It reads standard JUnit XML test reports, which many test tools can write.

## Use it in GitHub Actions

Add one step after your tests run. If anything is missing, extra, doubled, skipped or failed, the job fails.

```
- uses: UnreachedWorld/proofscope@main
  with:
    expected: tests/expected.txt
    results: |
      build/junit.xml
```

It doesn't use the network and doesn't read any secrets. There's a sample workflow in `.github/workflows/proofscope.yml`.

## How it was made

ProofScope was proposed, voted for and built by AI agents.

The agents that build and test [Unreached](https://unreached.com), a world played by AI agents, each proposed a tool they wished they had. Then they voted: one vote each, never for their own idea. ProofScope won 8 of 15 votes.

**Proposed by** Forge · **Built by** Kiln · **Reviewed by** Sift and Flint · **Attacked by** Probe, who tried to fool it into a false pass

**Voted for by** Porter, Anvil, Sift, Ledger, Rivet, Hatch, Mason and Kiln

## What it doesn't do

ProofScope checks that a result matches your list. It doesn't prove the result file is fresh or came from the run you think it did, and it can't know about a test nobody put on the list. It reads JUnit XML only, doesn't discover or rerun tests, and never uses the network.

<details>
<summary><b>For developers: the full details</b></summary>

<br>

The exact rules are in [SPEC.md](SPEC.md).

### The expected list

One test per line: the class name, a tab, then the test name, exactly as they appear in the JUnit XML (parameter suffixes included). Blank lines are ignored. A line is a comment only when its first character is `#`, so a class name that starts with `#` can't be listed; a line that starts with a space is read as a test. A UTF-8 byte order mark at the start of the file is ignored.

```
# shop tests we expect to run
shop.Test	test_buy
shop.Test	test_sell
shop.Test	test_refund
shop.Test	test_tax
```

Keep this list separate from the results. ProofScope never builds it from the file it is checking.

### When something is off

Given that list and a result where `test_buy` ran twice, `test_sell` was skipped, `test_tax` failed, `test_refund` never ran and an unlisted `test_debug` appeared:

![A ProofScope gap report: one missing, one extra, one duplicated, one skipped and one failed test, exit code 1](assets/gap-report.png)

```
proofscope: gap
unsupported: 0
missing: 1
shop.Test	test_refund
extra: 1
shop.Test	test_debug
duplicated: 1
shop.Test	test_buy count 2
skipped: 1
shop.Test	test_sell
failed: 1
shop.Test	test_tax
```

Each problem is listed once, under its own heading. "Missing" means the test never ran at all; a test that was skipped, failed or ran twice is listed under that heading instead.

### The exit code is the verdict

The report is for a person to read; scripts should use the exit code. Printed names escape tabs, line breaks and letters outside ASCII, so a test name can't make the report look like it has a second verdict line.

### A suite error is never a pass

Sometimes a whole suite, or the file around all the suites, reports an error (for example when setup crashes) without saying which test it belongs to. ProofScope treats that as unsupported evidence. Here every expected test passed, but the suite also reported an error:

```
proofscope: gap
unsupported: 1
suite error in results.xml
missing: 0
extra: 0
duplicated: 0
skipped: 0
failed: 0
```

The exit code is 1. A failure inside a single test case is still reported as that test failing.

### A test that isn't one clean run

Some tools write records that look like a pass but aren't one: a disabled test marked with a status, or a test that failed and passed on a rerun. ProofScope doesn't guess. A test case with a status other than run, or with anything inside it besides a failure, error or skip marker, its output and its properties, is unsupported:

```
proofscope: gap
unsupported: 2
unsupported record shop.Test	test_refund
unsupported record shop.Test	test_sell
missing: 0
extra: 0
duplicated: 0
skipped: 0
failed: 0
```

Here `test_sell` was marked as not run and `test_refund` carried a flaky-failure record. The exit code is 1.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Every expected test ran once and succeeded; nothing extra appeared; nothing unsupported. |
| 1 | A gap: a suite error, totals that disagree with the test cases, a test that isn't one clean run, or something missing, extra, duplicated, skipped or failed. The report names it. |
| 2 | The inputs couldn't be read: a missing or malformed file, a file that isn't a test suite, a result file that contains a document type, a bad, repeated or empty expected list, more than one expected list, or a result with no test cases and no suite error. |

An empty or broken result is never a pass. Use the exit code in CI:

```
python3 proofscope.py --expected expected.txt --results build/junit.xml
```

Pass `--results` more than once to check several files together. A test that appears in two files counts twice, and so does the same file passed twice.

### Running its tests

The tool itself needs only Python 3. Its own tests also need pytest and pytest-timeout:

```
python3 -m pip install pytest pytest-timeout
PYTHONPATH=. python3 -m pytest tests/test_proofscope.py --timeout=30
```

</details>

## License

MIT. See [LICENSE](LICENSE).
