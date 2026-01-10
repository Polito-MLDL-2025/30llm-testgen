from functools import lru_cache
from llm30.pipeline.SingleAgent.utils.processing import process_block
from llm30.pipeline.SingleAgent.tools.call_and_handle import call_and_handle


# Cache prompt templates to avoid repeated file I/O
@lru_cache(maxsize=8)
def _load_prompt_template(prompt_path):
    """
    Load and cache prompt template from file.

    Args:
        prompt_path: Path to the prompt template file

    Returns:
        str: Prompt template content
    """
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def generate_test_code(problem, problem_id, prompt_path, model, logger):
    """
    Generate test cases directly from the problem description.
    This is a single-agent approach without intermediate planning.

    Args:
        problem: The problem description/prompt
        problem_id: The task ID
        prompt_path: Path to the prompt template file
        model: The model name to use
        logger: Logger instance

    Returns:
        tuple: (generated_tests, input_token_count, output_token_count)
    """
    # Load prompt template (cached for efficiency)
    test_generator_prompt = _load_prompt_template(prompt_path)

    # Construct the full prompt
    full_test_generator_prompt = f"""{test_generator_prompt}

## Prompt:
```
{problem}
```

## Completion:
"""

    messages = [
        {"role": "system", "content": "You are a software programmer and quality assurance engineer."},
        {"role": "user", "content": full_test_generator_prompt}
    ]

    try:
        generated_tests, input_token_count, output_token_count = call_and_handle(messages, model)
        raw_content = generated_tests.choices[0].message.content

        # Log summary instead of full content to avoid bloating logs
        content_preview = raw_content[:200] + "..." if len(raw_content) > 200 else raw_content
        logger.info(f"Task ID {problem_id}: Generated {len(raw_content)} chars. Preview: {content_preview}")

        # Extract code from markdown blocks
        processed_tests = process_block(raw_content)

        logger.debug(f"Task ID {problem_id}: Extracted {len(processed_tests.splitlines())} lines of test code")

        return processed_tests, input_token_count, output_token_count

    except Exception as e:
        logger.error(f"Error generating tests for task {problem_id}: {e}")
        raise