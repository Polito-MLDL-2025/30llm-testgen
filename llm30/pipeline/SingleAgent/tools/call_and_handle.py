import os
import time
import logging

try:
    import httpx
except ImportError:
    httpx = None

try:
    from openai import OpenAI, APITimeoutError
except ImportError:  # pragma: no cover - older openai versions
    from openai import OpenAI
    APITimeoutError = None
from dotenv import load_dotenv

load_dotenv()

# Configure logger for this module
logger = logging.getLogger(__name__)

client = OpenAI(base_url=os.getenv("OPENAI_URL_BASE"), api_key=os.getenv("OPENAI_API_KEY"))


def _is_timeout_error(exc: Exception) -> bool:
    if APITimeoutError and isinstance(exc, APITimeoutError):
        return True
    if httpx is not None and isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, TimeoutError):
        return True
    message = str(exc).lower()
    return "timed out" in message or "timeout" in message

def call_and_handle(messages, model, timeout=120):
    """
    Call the OpenAI API and handle the response.

    Args:
        messages: List of message dictionaries
        model: The model to use for generation
        timeout: Request timeout in seconds (default: 180)

    Returns:
        tuple: (completion, input_token_count, output_token_count)

    Raises:
        OpenAI API exceptions on failure
    """
    logger.debug("Calling model: %s", model)

    completion = None
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                top_p=1.0,
                timeout=timeout,
            )
            break
        except Exception as exc:
            if _is_timeout_error(exc) and attempt < max_attempts:
                logger.warning(
                    "Request timed out (attempt %s/%s). Retrying in 30 seconds.",
                    attempt,
                    max_attempts,
                )
                time.sleep(30)
                continue
            raise

    if completion is None:
        raise RuntimeError("OpenAI completion failed after retries.")

    # Extract token counts
    input_token_count = completion.usage.prompt_tokens
    output_token_count = completion.usage.completion_tokens

    # Log token usage
    logger.debug(
        "API call successful. Tokens - Input: %s, Output: %s, Total: %s",
        input_token_count,
        output_token_count,
        completion.usage.total_tokens,
    )

    # Log response preview (first 100 chars)
    response_preview = (completion.choices[0].message.content or "")[:100]
    logger.debug("Response preview: %s...", response_preview)

    return completion, input_token_count, output_token_count
