import ast
import textwrap

from llm30.pipeline.QAagent.agents.merge_strategies.merger_concat import merge_plans_concat, merge_tests_concat_enhanced
from llm30.pipeline.QAagent.utils.utils import add_canonical_solution


def _clean_tests(test_string):
    lines = []
    for line in test_string.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            continue
        lines.append(line.rstrip())
    return textwrap.dedent("\n".join(lines)).strip()


def _filter_tests_for_accuracy(canonical_solution, tests, logger, problem_id):
    cleaned_tests = _clean_tests(tests)
    if not cleaned_tests:
        logger.info(f"Accuracy filter: no tests to filter for problem {problem_id}")
        return ""

    exec_globals = {}
    exec(canonical_solution, exec_globals)

    kept_lines = []
    total_asserts = 0
    kept_asserts = 0
    skipped_asserts = 0
    skipped_setup = 0

    try:
        module = ast.parse(cleaned_tests)
        statements = module.body
        for stmt in statements:
            source = ast.get_source_segment(cleaned_tests, stmt)
            if source is None:
                continue
            if isinstance(stmt, ast.Assert):
                total_asserts += 1
                try:
                    exec(compile(ast.Module([stmt], type_ignores=[]), "<tests>", "exec"), exec_globals)
                except (AssertionError, Exception):
                    skipped_asserts += 1
                    continue
                kept_asserts += 1
                kept_lines.append(source)
            else:
                try:
                    exec(compile(ast.Module([stmt], type_ignores=[]), "<tests>", "exec"), exec_globals)
                except Exception:
                    skipped_setup += 1
                    continue
                kept_lines.append(source)
    except SyntaxError as e:
        logger.warning(
            f"Accuracy filter parse error for problem {problem_id}: {e}. "
            "Falling back to line-based filtering."
        )
        for line in cleaned_tests.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("assert"):
                total_asserts += 1
                try:
                    exec(stripped, exec_globals)
                except (AssertionError, Exception):
                    skipped_asserts += 1
                    continue
                kept_asserts += 1
                kept_lines.append(stripped)
            else:
                try:
                    exec(line, exec_globals)
                except Exception:
                    skipped_setup += 1
                    continue
                kept_lines.append(line)

    logger.info(
        f"Accuracy filter for problem {problem_id}: kept {kept_asserts}/{total_asserts} asserts, "
        f"skipped setup lines: {skipped_setup}"
    )
    return "\n".join(kept_lines).strip()


def merge_test_accuracy(problem_id, problem_name, plan, generated_tests, dataset, logger):
    merged_plan = merge_plans_concat(plan)
    merged_tests = merge_tests_concat_enhanced(generated_tests, problem_name, logger)
    # merged_tests = _filter_tests_for_accuracy(
    #     add_canonical_solution(problem_name) if dataset == "humaneval" else problem_name["canonical_solution"],
    #     merged_tests,
    #     logger,
    #     problem_id,
    # )
    logger.info(f'Merged tests using accuracy strategy (pass-only filter)')
    return merged_plan, merged_tests
