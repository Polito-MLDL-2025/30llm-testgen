import os
import re
import time

from llm30.pipeline.QAagent.agents.merge_strategies.merger_concat import merge_tests_concat
from llm30.pipeline.QAagent.utils.processing import process_block
from llm30.pipeline.QAagent.tools.call_and_handle import call_and_handle

FILTER_PROMPT_FILENAME = "merger_filter_prompt.txt"
AGGREGATE_PROMPT_FILENAME = "merger_aggregate_prompt"


def _write_debug_file(debug_mode, debug_dir, filename, content):
    if not debug_mode or not debug_dir:
        return
    os.makedirs(debug_dir, exist_ok=True)
    with open(os.path.join(debug_dir, filename), "w") as f:
        f.write(content)


def _resolve_multi_step_prompt_paths(prompt_path):
    """
    Resolve prompt files for the multi-step merger.

    Resolution order:
    1. `prompt_path` if it is a directory containing both prompt files.
    2. `<dirname(prompt_path)>/llm_merger`.
    3. `<dirname(prompt_path)>`.
    4. Built-in default: `pipeline/prompts/v1/llm_merger`.
    """
    module_dir = os.path.dirname(__file__)
    default_prompt_dir = os.path.abspath(
        os.path.join(module_dir, "..", "..", "..", "prompts", "v1", "llm_merger")
    )

    candidate_dirs = []
    if prompt_path:
        if os.path.isdir(prompt_path):
            candidate_dirs.append(prompt_path)
        else:
            parent = os.path.dirname(prompt_path)
            candidate_dirs.append(os.path.join(parent, "llm_merger"))
            candidate_dirs.append(parent)
    candidate_dirs.append(default_prompt_dir)

    for directory in candidate_dirs:
        filter_prompt_path = os.path.join(directory, FILTER_PROMPT_FILENAME)
        aggregate_prompt_path = os.path.join(directory, AGGREGATE_PROMPT_FILENAME)
        if os.path.isfile(filter_prompt_path) and os.path.isfile(aggregate_prompt_path):
            return filter_prompt_path, aggregate_prompt_path

    raise FileNotFoundError(
        "Could not locate multi-step merger prompts. "
        f"Expected files: {FILTER_PROMPT_FILENAME}, {AGGREGATE_PROMPT_FILENAME}"
    )


def _extract_reasoning_and_tests(response_text):
    """
    Parse filter-agent output.
    Expected format:
      <coverage_reasoning>...</coverage_reasoning>
      ```python
      ...
      ```
    """
    if not response_text:
        return "", ""

    reasoning_match = re.search(
        r"<coverage_reasoning>(.*?)</coverage_reasoning>",
        response_text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if reasoning_match:
        reasoning = reasoning_match.group(1).strip()
    else:
        fence_start = response_text.find("```")
        reasoning = response_text[:fence_start].strip() if fence_start != -1 else response_text.strip()

    filtered_tests = process_block(response_text)
    return reasoning, filtered_tests


def _build_filter_prompt(filter_prompt_template, problem_name, plan, tests, suite_idx):
    entry_point = problem_name.get("entry_point", "")
    reference_impl = problem_name.get("canonical_solution", "")

    return f"""{filter_prompt_template}

## Problem Prompt:
```
{problem_name.get("prompt", "")}
```

Entry Point: `{entry_point}`

Reference Implementation:
```python
{reference_impl}
```

## Plan:
```
{plan}
```

## Test Suite ID: {suite_idx}
```python
{tests}
```

## Your response:
"""


def _build_aggregate_prompt(aggregate_prompt_template, problem_name, plan, filtered_results):
    entry_point = problem_name.get("entry_point", "")
    reference_impl = problem_name.get("canonical_solution", "")

    suites_payload = []
    for item in filtered_results:
        suites_payload.append(
            f"""## Filtered Suite {item["suite_idx"]}:
Coverage Reasoning:
{item["reasoning"] or "No reasoning provided."}

Filtered Tests:
```python
{item["filtered_tests"]}
```"""
        )

    suites_payload_text = "\n\n".join(suites_payload)

    return f"""{aggregate_prompt_template}

## Problem Prompt:
```
{problem_name.get("prompt", "")}
```

Entry Point: `{entry_point}`

Reference Implementation:
```python
{reference_impl}
```

## Plan:
```
{plan}
```

## Filtered Suites + Reasoning:
{suites_payload_text}

## Final merged tests:
"""


def merge_tests_llm_multi_steps(
        test_sets,
        problem_name,
        plan,
        prompt_path,
        model,
        logger,
        debug_mode=False,
        debug_dir=None
):
    """
    Two-step LLM merge:
    1) Filter each generated test suite independently.
    2) Aggregate all filtered suites into one final merged set.

    Returns:
        tuple: (merged_tests, input_token_count, output_token_count)
    """
    if not test_sets:
        return "", 0, 0

    valid_test_sets = [tests for tests in test_sets if tests and tests.strip()]
    if not valid_test_sets:
        return "", 0, 0

    try:
        filter_prompt_path, aggregate_prompt_path = _resolve_multi_step_prompt_paths(prompt_path)
        with open(filter_prompt_path, "r") as f:
            filter_prompt_template = f.read()
        with open(aggregate_prompt_path, "r") as f:
            aggregate_prompt_template = f.read()
        _write_debug_file(debug_mode, debug_dir, "llm_multi_filter_prompt_template.txt", filter_prompt_template)
        _write_debug_file(
            debug_mode,
            debug_dir,
            "llm_multi_aggregate_prompt_template.txt",
            aggregate_prompt_template,
        )
    except Exception as e:
        logger.error(f"Failed to load multi-step merger prompts: {e}")
        return merge_tests_concat(valid_test_sets), 0, 0

    total_input_tokens = 0
    total_output_tokens = 0
    filtered_results = []

    for suite_idx, tests in enumerate(valid_test_sets, 1):
        _write_debug_file(
            debug_mode,
            debug_dir,
            f"llm_multi_input_suite_{suite_idx:02d}.py",
            tests,
        )
        filter_prompt = _build_filter_prompt(
            filter_prompt_template=filter_prompt_template,
            problem_name=problem_name,
            plan=plan,
            tests=tests,
            suite_idx=suite_idx,
        )
        _write_debug_file(
            debug_mode,
            debug_dir,
            f"llm_multi_filter_prompt_suite_{suite_idx:02d}.txt",
            filter_prompt,
        )
        filter_messages = [
            {"role": "system", "content": "You are a strict software test-quality reviewer."},
            {"role": "user", "content": filter_prompt},
        ]

        try:
            response, input_tokens, output_tokens = call_and_handle(filter_messages, model)
            total_input_tokens += input_tokens
            total_output_tokens += output_tokens

            response_text = response.choices[0].message.content or ""
            reasoning, filtered_tests = _extract_reasoning_and_tests(response_text)
            if not filtered_tests.strip():
                logger.warning(
                    f"Filter step returned empty tests for suite {suite_idx}. "
                    "Falling back to original suite."
                )
                filtered_tests = tests

            _write_debug_file(
                debug_mode,
                debug_dir,
                f"llm_multi_filter_raw_response_suite_{suite_idx:02d}.txt",
                response_text,
            )
            _write_debug_file(
                debug_mode,
                debug_dir,
                f"llm_multi_filter_reasoning_suite_{suite_idx:02d}.txt",
                reasoning,
            )
            _write_debug_file(
                debug_mode,
                debug_dir,
                f"llm_multi_filtered_tests_suite_{suite_idx:02d}.py",
                filtered_tests,
            )

            filtered_results.append(
                {
                    "suite_idx": suite_idx,
                    "reasoning": reasoning,
                    "filtered_tests": filtered_tests,
                }
            )
            logger.debug(f"Filter suite {suite_idx} reasoning:\n{reasoning}")
            logger.debug(f"Filter suite {suite_idx} filtered tests:\n{filtered_tests}")
            logger.info(
                f"Filter step complete for suite {suite_idx}/{len(valid_test_sets)}: "
                f"{len(tests.splitlines())} -> {len(filtered_tests.splitlines())} lines"
            )
        except Exception as e:
            logger.error(
                f"Error in filter step for suite {suite_idx}: {e}. "
                "Using original suite for aggregation."
            )
            _write_debug_file(
                debug_mode,
                debug_dir,
                f"llm_multi_filter_error_suite_{suite_idx:02d}.txt",
                str(e),
            )
            filtered_results.append(
                {
                    "suite_idx": suite_idx,
                    "reasoning": f"Filter step failed with error: {e}. Original suite retained.",
                    "filtered_tests": tests,
                }
            )

    if not filtered_results:
        logger.warning("No filtered suites produced; falling back to concat strategy.")
        return merge_tests_concat(valid_test_sets), total_input_tokens, total_output_tokens

    aggregate_prompt = _build_aggregate_prompt(
        aggregate_prompt_template=aggregate_prompt_template,
        problem_name=problem_name,
        plan=plan,
        filtered_results=filtered_results,
    )
    _write_debug_file(debug_mode, debug_dir, "llm_multi_aggregate_prompt.txt", aggregate_prompt)
    aggregate_messages = [
        {"role": "system", "content": "You are a software test merger focused on correctness and deduplication."},
        {"role": "user", "content": aggregate_prompt},
    ]

    try:
        aggregate_response, input_tokens, output_tokens = call_and_handle(aggregate_messages, model)
        total_input_tokens += input_tokens
        total_output_tokens += output_tokens

        aggregate_response_text = aggregate_response.choices[0].message.content or ""
        merged_tests = process_block(aggregate_response_text)
        _write_debug_file(debug_mode, debug_dir, "llm_multi_aggregate_raw_response.txt", aggregate_response_text)
        if not merged_tests.strip():
            logger.warning(
                "Aggregate step returned empty tests; using concatenation of filtered suites as fallback."
            )
            merged_tests = merge_tests_concat([x["filtered_tests"] for x in filtered_results])
        _write_debug_file(debug_mode, debug_dir, "llm_multi_merged_tests.py", merged_tests)

        logger.info(
            "Merged tests using LLM multi-step strategy "
            f"({len(filtered_results)} filtered suites -> {len(merged_tests.splitlines())} lines)"
        )
        logger.debug(f"Aggregate merged tests:\n{merged_tests}")
        return merged_tests, total_input_tokens, total_output_tokens
    except Exception as e:
        logger.error(f"Error in aggregate step: {e}")
        time.sleep(10)
        logger.warning("Falling back to concatenation of filtered suites")
        fallback_tests = merge_tests_concat([x["filtered_tests"] for x in filtered_results])
        _write_debug_file(debug_mode, debug_dir, "llm_multi_aggregate_error.txt", str(e))
        _write_debug_file(debug_mode, debug_dir, "llm_multi_fallback_tests.py", fallback_tests)
        return fallback_tests, total_input_tokens, total_output_tokens
