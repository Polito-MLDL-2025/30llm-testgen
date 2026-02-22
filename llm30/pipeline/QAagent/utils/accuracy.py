import json
import os
import subprocess
import sys
from io import StringIO

DEFAULT_TEST_TIMEOUT_SECONDS = 30.0
TEST_TIMEOUT_ENV = "QAAGENT_TEST_TIMEOUT_SECONDS"


def _read_test_timeout_seconds() -> float:
    raw = os.getenv(TEST_TIMEOUT_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_TEST_TIMEOUT_SECONDS
    try:
        timeout = float(raw)
        if timeout <= 0:
            raise ValueError
        return timeout
    except ValueError:
        return DEFAULT_TEST_TIMEOUT_SECONDS


def _run_single_assert_with_timeout(canonical_solution: str, test: str, timeout_seconds: float):
    runner = (
        "import json,sys\n"
        "payload=json.loads(sys.argv[1])\n"
        "scope={}\n"
        "exec(payload['canonical_solution'], scope)\n"
        "exec(payload['test'], scope)\n"
    )
    payload = json.dumps(
        {
            "canonical_solution": canonical_solution,
            "test": test,
        }
    )

    try:
        completed = subprocess.run(
            [sys.executable, "-c", runner, payload],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return "timeout", f"Timed out after {timeout_seconds:.1f}s"

    if completed.returncode == 0:
        return "pass", ""

    stderr = (completed.stderr or "").strip()
    if "AssertionError" in stderr:
        return "assertion", ""

    return "error", stderr or f"Process exited with code {completed.returncode}"


def get_accuracy(canonical_solution, tests, log_folder, problem_id):
    test_result = StringIO()
    passed_tests = 0
    total_tests = 0
    timed_out_tests = 0

    per_test_timeout = _read_test_timeout_seconds()

    # Split the tests into individual lines
    individual_tests = tests.strip().split("\n")

    for test in individual_tests:
        test = test.strip()  # Remove leading and trailing whitespaces

        # Skip blank lines and comments
        if not test or test.startswith("#"):
            continue

        # Only count assert statements
        if not test.startswith("assert"):
            test_result.write(f"Skipping non-assert statement: {test}\n")
            continue

        total_tests += 1
        status, message = _run_single_assert_with_timeout(
            canonical_solution=canonical_solution,
            test=test,
            timeout_seconds=per_test_timeout,
        )

        if status == "pass":
            passed_tests += 1
        elif status == "timeout":
            timed_out_tests += 1
            test_result.write(f"Test timed out after {per_test_timeout:.1f}s: {test}\n")
            print(f"Problem {problem_id}: Test timed out after {per_test_timeout:.1f}s: {test}")
        elif status == "assertion":
            test_result.write(f"Test failed: {test}\n")
        else:
            print(f"Problem {problem_id}: An error occurred during test '{test}': {message}\n")
            test_result.write(f"An error occurred during test '{test}': {message}\n")

    # Calculate percentage of passed tests
    accuracy = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
    test_result.write(f"\nPassed {passed_tests}/{total_tests} tests ({accuracy:.2f}%)\n")
    if timed_out_tests:
        test_result.write(f"Timed out tests: {timed_out_tests}\n")

    return accuracy, test_result.getvalue()
