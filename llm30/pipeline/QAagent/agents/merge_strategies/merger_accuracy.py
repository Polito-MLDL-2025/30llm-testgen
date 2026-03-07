import ast
import textwrap

from llm30.pipeline.QAagent.agents.merge_strategies.merger_concat import merge_plans_concat, merge_tests_concat_enhanced
from llm30.pipeline.QAagent.utils.extract_assert_block import extract_assert_blocks
from llm30.pipeline.QAagent.utils.utils import add_canonical_solution


def _clean_tests(test_string):
    lines = []
    for line in (test_string or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            continue
        lines.append(line.rstrip())
    return textwrap.dedent("\n".join(lines)).strip()


def _filter_tests_for_accuracy(canonical_solution, tests, logger, problem_id):
    cleaned_tests = _clean_tests(tests)
    assert_blocks = extract_assert_blocks(cleaned_tests)
    if not assert_blocks:
        logger.info(f"Accuracy filter: no tests to filter for problem {problem_id}")
        return ""

    exec_globals = {}
    exec(canonical_solution, exec_globals)

    kept_assert_blocks = []
    total_asserts = len(assert_blocks)
    kept_asserts = 0
    skipped_asserts = 0
    skipped_setup = 0

    # Run top-level setup statements once so asserts depending on simple setup
    # assignments/imports can be validated in the same scope.
    try:
        module = ast.parse(cleaned_tests)
        for stmt in module.body:
            if isinstance(stmt, ast.Assert):
                continue
            try:
                exec(compile(ast.Module([stmt], type_ignores=[]), "<tests>", "exec"), exec_globals)
            except Exception:
                skipped_setup += 1
    except SyntaxError as e:
        logger.warning(
            f"Accuracy filter parse error for problem {problem_id}: {e}. "
            "Proceeding without setup statements."
        )

    for test in assert_blocks:
        try:
            exec(test, exec_globals)
            kept_asserts += 1
            kept_assert_blocks.append(test)
        except (AssertionError, Exception):
            skipped_asserts += 1

    logger.info(
        f"Accuracy filter for problem {problem_id}: kept {kept_asserts}/{total_asserts} asserts, "
        f"skipped asserts: {skipped_asserts}, skipped setup lines: {skipped_setup}"
    )
    return "\n".join(kept_assert_blocks).strip()


def merge_test_accuracy(problem_id, problem_name, plan, generated_tests, dataset, logger):
    merged_plan = merge_plans_concat(plan)
    merged_tests = merge_tests_concat_enhanced(generated_tests, problem_name, logger)
    merged_tests = _filter_tests_for_accuracy(
        add_canonical_solution(problem_name) if dataset == "humaneval" else problem_name["canonical_solution"],
        merged_tests,
        logger,
        problem_id,
    )
    logger.info(f'Merged tests using accuracy strategy (pass-only filter)')
    return merged_plan, merged_tests
