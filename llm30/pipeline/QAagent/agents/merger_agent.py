import time
import ast
from llm30.pipeline.QAagent.utils.processing import process_block
from llm30.pipeline.QAagent.tools.call_and_handle import call_and_handle

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
        for line in tests.split('\n'):
            line = line.strip()
            if not line or not line.startswith('assert'):
                continue
            
            try:
                # Attempt to compile the line to check for syntax errors
                compile(line, '<string>', 'exec')
                valid_tests.append(line)
            except SyntaxError:
                syntax_errors += 1
                logger.debug(f"Filtered out test with syntax error: {line}")
    
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
    
    # Stage 3: Prioritize tests with correct function name
    correct_name = problem_name.get('entry_point', '')
    if correct_name:
        # Sort so tests with correct function name come first
        prioritized = sorted(unique_tests, 
                           key=lambda t: correct_name in t,
                           reverse=True)
    else:
        prioritized = unique_tests
    
    logger.info(f"Enhanced concat: {len(valid_tests)} valid → {len(unique_tests)} unique tests")
    
    return '\n'.join(prioritized)

def merge_tests_llm(test_sets, problem_name, plan, prompt_path, model, logger):
    """
    Merge multiple test sets using an LLM to intelligently combine tests,
    removing duplicates, conflicts, and syntax errors.
    
    Args:
        test_sets (list): List of test set strings to merge
        problem_name (dict): Problem information including prompt and entry_point
        plan (str): The plan/pseudocode for the problem
        prompt_path (str): Path to the merger prompt file
        model (str): Model name to use for merging
        logger: Logger instance for logging
        
    Returns:
        tuple: (merged_tests, input_token_count, output_token_count)
    """
    if not test_sets:
        return "", 0, 0
    
    # Filter out empty or None test sets
    valid_test_sets = [tests for tests in test_sets if tests and tests.strip()]
    
    if not valid_test_sets:
        return "", 0, 0
    
    # If only one test set, return it as-is
    if len(valid_test_sets) == 1:
        return valid_test_sets[0], 0, 0
    
    # Read the merger prompt
    with open(prompt_path, "r") as f:
        merger_prompt = f.read()
    
    # Build the full prompt with problem context and test sets
    test_sets_str = ""
    for i, tests in enumerate(valid_test_sets, 1):
        test_sets_str += f"\n## Test Set {i}:\n```python\n{tests}\n```\n"
    
    full_merger_prompt = (
        f"{merger_prompt}\n"
        f"\n"
        f"## Problem Prompt:\n"
        f"```\n"
        f"{problem_name['prompt']}\n"
        f"```\n"
        f"\n"
        f"## Plan:\n"
        f"```\n"
        f"{plan}\n"
        f"```\n"
        f"\n"
        f"{test_sets_str}\n"
        f"\n"
        f"## Merged Test Set:"
    )
    
    messages = [
        {"role": "system", "content": "You are a software programmer."},
        {"role": "user", "content": full_merger_prompt}
    ]
    
    try:
        merged_tests_response, input_token_count, output_token_count = call_and_handle(messages, model)
        merged_tests = process_block(merged_tests_response.choices[0].message.content)
        
        logger.info(f"Task ID: {problem_name['task_id']}: Merged tests using LLM")
        logger.info(f"Tests: {test_sets_str}")
        logger.info(f"Merged tests: {merged_tests}")
        logger.info(f"Input tokens: {input_token_count}, Output tokens: {output_token_count}")
        
        return merged_tests, input_token_count, output_token_count
    
    except Exception as e:
        logger.error(f"Error merging tests with LLM: {e}")
        print(f"Error merging tests with LLM: {e}")
        time.sleep(10)
        # Fallback to concat strategy if LLM fails
        logger.warning("Falling back to concat strategy")
        return merge_tests_concat(valid_test_sets), 0, 0
