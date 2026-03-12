import ast

from llm30.pipeline.QAagent.utils.extract_assert_block import extract_assert_blocks


def merge_plans_concat(plans):
    """
    Merge multiple plans by concatenating them with separators.

    Args:
        plans (list): List of plan strings to merge

    Returns:
        str: Concatenated plans with numbered separators
    """
    if not plans:
        return ""

    # Filter out empty or None plans
    valid_plans = [plan for plan in plans if plan and plan.strip()]

    if not valid_plans:
        return ""

    # If only one plan, return it
    if len(valid_plans) == 1:
        return valid_plans[0]

    # Concatenate with separators
    merged_plan = ""
    for i, plan in enumerate(valid_plans, 1):
        merged_plan += f"\n## Plan {i}:\n{plan}\n"

    return merged_plan.strip()


def merge_tests_concat(test_sets):
    """
    Merge multiple test sets by concatenating them.

    Args:
        test_sets (list): List of test set strings to merge

    Returns:
        str: Concatenated test sets
    """
    if not test_sets:
        return ""

    # Filter out empty or None test sets
    valid_test_sets = [tests for tests in test_sets if tests and tests.strip()]

    if not valid_test_sets:
        return ""

    # Concatenate with newline separator
    merged_tests = "\n".join(valid_test_sets)
    return merged_tests


def merge_tests_concat_enhanced(test_sets, problem_name, logger):
    """
    Merge multiple test sets by concatenating them, then filter out:
    1. Tests with syntax errors
    2. True duplicate tests (using AST-based comparison)

    This provides better quality than simple concat without LLM overhead.

    Args:
        test_sets (list): List of test set strings to merge
        problem_name (dict): Problem information including entry_point
        logger: Logger instance for logging

    Returns:
        str: Enhanced concatenated test sets (validated and deduplicated)
    """
    if not test_sets:
        return ""

    # Filter out empty or None test sets
    valid_test_sets = [tests for tests in test_sets if tests and tests.strip()]

    if not valid_test_sets:
        return ""

    # Stage 1: Syntax validation
    valid_tests = []
    syntax_errors = 0

    for tests in valid_test_sets:
        for test in extract_assert_blocks(tests):
            try:
                # Attempt to compile the assert block to check for syntax errors
                compile(test, '<string>', 'exec')
                valid_tests.append(test)
            except SyntaxError:
                syntax_errors += 1
                logger.debug(f"Filtered out test with syntax error: {test}")

    if syntax_errors > 0:
        logger.info(f"Filtered out {syntax_errors} tests with syntax errors")

    # Stage 2: AST-based deduplication
    seen_ast = set()
    unique_tests = []
    duplicates = 0

    for test in valid_tests:
        try:
            # Parse the test and create a canonical AST representation
            ast_tree = ast.parse(test)
            ast_repr = ast.dump(ast_tree)

            if ast_repr not in seen_ast:
                seen_ast.add(ast_repr)
                unique_tests.append(test)
            else:
                duplicates += 1
                logger.debug(f"Filtered out duplicate test: {test}")
        except Exception as e:
            # If AST parsing fails (shouldn't happen after syntax check), filter the test
            logger.warning(f"AST parsing failed for test: {test}. Error: {e}")

    if duplicates > 0:
        logger.info(f"Filtered out {duplicates} duplicate tests (AST-based)")

    # Stage 3: Filter out tests with incorrect function name
    correct_name = problem_name.get('entry_point', '')
    if correct_name:
        filtered_tests = [test for test in unique_tests if correct_name in test]
        wrong_name_count = len(unique_tests) - len(filtered_tests)
        if wrong_name_count > 0:
            logger.info(f"Filtered out {wrong_name_count} tests with incorrect function name")
        final_tests = filtered_tests
    else:
        final_tests = unique_tests

    logger.info(
        f"Enhanced concat: {len(valid_tests)} valid → {len(unique_tests)} unique → {len(final_tests)} final tests")

    return '\n'.join(final_tests)
