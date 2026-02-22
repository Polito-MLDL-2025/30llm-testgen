import json
import os
import subprocess
import sys

from llm30.pipeline.QAagent.utils.extract_assert_block import extract_assert_blocks

DEFAULT_TEST_TIMEOUT_SECONDS = 10.0
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


def filter_timeout_exe_test(canonical_solution, tests, problem_id, log_folder=None):
    per_test_timeout = _read_test_timeout_seconds()

    assert_blocks = extract_assert_blocks(tests)
    timed_out_tests = []
    normal_tests = []

    for test in assert_blocks:
        status, _ = _run_single_assert_with_timeout(
            canonical_solution=canonical_solution,
            test=test,
            timeout_seconds=per_test_timeout,
        )

        if status == "timeout":
            timed_out_tests.append(test)
        else:
            normal_tests.append(test)

    timed_out_tests = "\n".join(timed_out_tests)
    filtered_tests = "\n".join(normal_tests)
    return filtered_tests, timed_out_tests, tests
