import time
import ast

from llm30.pipeline.QAagent.agents.merge_strategies.merger_concat import merge_tests_concat
from llm30.pipeline.QAagent.utils.processing import process_block
from llm30.pipeline.QAagent.tools.call_and_handle import call_and_handle


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

    entry_point = problem_name.get("entry_point", "")

    full_merger_prompt = f"""{merger_prompt}

Entry Point: `{entry_point}`

{test_sets_str}

## Merged Test Set:
"""
    messages = [
        {"role": "system", "content": "You are a software programmer."},
        {"role": "user", "content": full_merger_prompt}
    ]
    
    try:
        merged_tests_response, input_token_count, output_token_count = call_and_handle(messages, model)
        merged_tests = process_block(merged_tests_response.choices[0].message.content)
        
        logger.info(f"Task ID: {problem_name['task_id']}: Merged tests using LLM")
        logger.debug(f"Tests: {test_sets_str}")
        logger.debug(f"Merged tests: {merged_tests}")
        logger.info(f"Input tokens: {input_token_count}, Output tokens: {output_token_count}")
        
        return merged_tests, input_token_count, output_token_count
    
    except Exception as e:
        logger.error(f"Error merging tests with LLM: {e}")
        print(f"Error merging tests with LLM: {e}")
        time.sleep(10)
        # Fallback to concat strategy if LLM fails
        logger.warning("Falling back to concat strategy")
        return merge_tests_concat(valid_test_sets), 0, 0
