import json
import re

from llm30.pipeline.QAagent.tools.call_and_handle import call_and_handle


def _extract_first_json_obj(text):
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def judge_scorer_suite(problem_name, candidate, prompt_path, model, logger, candidate_idx=1):
    """
    Judge a single candidate test suite independently.

    Args:
        problem_name: Dict containing at least "prompt" and "task_id"
        candidate: Dict containing "plan" and "tests"
        prompt_path: Path to judge prompt template
        model: Model name
        logger: Logger
        candidate_idx: Index of the candidate (for logging)

    Returns:
        tuple: (score, reason, input_tokens, output_tokens, raw_parsed_json)
    """
    with open(prompt_path, "r") as f:
        judge_prompt_template = f.read()

    suite_text = (
        f"## Candidate {candidate_idx}\n"
        f"### Generated Plan\n```\n{candidate.get('plan', 'N/A')}\n```\n"
        f"### Generated Tests\n```python\n{candidate['tests']}\n```\n"
    )

    full_prompt = f"""{judge_prompt_template}

## Problem Prompt
```python
{problem_name["prompt"]}
```

## Entry Point
{problem_name.get("entry_point", "N/A")}

{suite_text}
"""

    messages = [
        {"role": "system", "content": "You are a rigorous software test reviewer."},
        {"role": "user", "content": full_prompt},
    ]

    completion, input_tokens, output_tokens = call_and_handle(messages, model, temperature=0)
    raw_content = completion.choices[0].message.content or ""
    parsed = _extract_first_json_obj(raw_content)
    
    if not isinstance(parsed, dict):
        raise ValueError("Judge output is not valid JSON object.")

    score = parsed.get("score")
    reason = str(parsed.get("reason", "Judged by judge agent."))

    logger.debug(
        "Judge scored candidate %s (problem %s) with score %s",
        candidate_idx,
        problem_name.get("task_id", "unknown"),
        score,
    )
    return score, reason, input_tokens, output_tokens, parsed


def judge_selector_suites(problem_name, candidates, prompt_path, model, logger):
    """
    Rank/select candidate test suites in a black-box setting.
    All candidates are judged together and the best one is selected.

    Args:
        problem_name: Dict containing at least "prompt" and "task_id"
        candidates: List[Dict], each item must contain "plan" and "tests"
        prompt_path: Path to judge prompt template
        model: Model name
        logger: Logger

    Returns:
        tuple: (selected_idx, selection_reason, ranking, input_tokens, output_tokens, raw_parsed_json)
    """
    if not candidates:
        return 0, "No candidates available.", [], 0, 0, {}
    if len(candidates) == 1:
        return 0, "Only one candidate available.", [], 0, 0, {}

    with open(prompt_path, "r") as f:
        judge_prompt_template = f.read()

    suites_text = []
    for idx, candidate in enumerate(candidates, start=1):
        suites_text.append(
            f"## Candidate {idx}\n"
            f"### Generated Tests\n```python\n{candidate['tests']}\n```\n"
        )

    full_prompt = f"""{judge_prompt_template}

## Problem Prompt
```python
{problem_name["prompt"]}
```

## Entry Point
{problem_name.get("entry_point", "N/A")}

{"".join(suites_text)}
"""

    messages = [
        {"role": "system", "content": "You are a rigorous software test reviewer."},
        {"role": "user", "content": full_prompt},
    ]

    completion, input_tokens, output_tokens = call_and_handle(messages, model, temperature=0)
    raw_content = completion.choices[0].message.content or ""
    parsed = _extract_first_json_obj(raw_content)
    if not isinstance(parsed, dict):
        raise ValueError("Judge output is not valid JSON object.")

    selected_candidate = int(parsed.get("selected_candidate", 1))
    selected_idx = selected_candidate - 1
    if selected_idx < 0 or selected_idx >= len(candidates):
        raise ValueError(f"Invalid selected_candidate value: {selected_candidate}")

    selection_reason = str(parsed.get("selection_reason", "Selected by judge agent."))
    ranking = parsed.get("ranking", [])
    if not isinstance(ranking, list):
        ranking = []

    logger.debug(
        "Judge selected candidate %s for problem %s",
        selected_candidate,
        problem_name.get("task_id", "unknown"),
    )
    return selected_idx, selection_reason, ranking, input_tokens, output_tokens, parsed
