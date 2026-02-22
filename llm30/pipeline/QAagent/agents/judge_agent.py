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


def judge_single_test_suite(problem_name, candidate, prompt_path, model, logger, candidate_idx=None):
    """
    Score one candidate test suite in isolation (black-box).

    Returns:
        tuple: (score, reason, input_tokens, output_tokens, raw_parsed_json)
    """
    with open(prompt_path, "r") as f:
        judge_prompt_template = f.read()

    candidate_label = f"Candidate {candidate_idx}" if candidate_idx is not None else "Candidate"

    full_prompt = f"""{judge_prompt_template}

## Problem Prompt
```python
{problem_name["prompt"]}
```

## Entry Point
{problem_name.get("entry_point", "N/A")}

## {candidate_label}
### Generated Tests
```python
{candidate["tests"]}
```
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
    reason = parsed.get("reason")

    # Compatibility fallback if the model emits ranking-like JSON.
    if score is None and isinstance(parsed.get("ranking"), list) and parsed["ranking"]:
        first = parsed["ranking"][0]
        if isinstance(first, dict):
            score = first.get("score")
            reason = reason or first.get("reason")

    try:
        score = float(score)
    except Exception:
        raise ValueError(f"Invalid score from judge: {score}")

    return score, str(reason or "No reason provided."), input_tokens, output_tokens, parsed
