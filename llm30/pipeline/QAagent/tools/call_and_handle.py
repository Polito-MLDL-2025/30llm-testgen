import os
import logging

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

client = OpenAI(base_url=os.getenv("OPENAI_URL_BASE"), api_key=os.getenv("OPENAI_API_KEY"))


def call_and_handle(messages, model, temperature=0, top_p = 1.0,timeout=180):
    """
    Call the OpenAI API and handle the response.

    Args:
        messages: List of message dictionaries
        model: The model to use for generation
        temperature: Sampling temperature (default: 0)
        top_p: Nucleus sampling parameter (default: 1.0)
        timeout: Request timeout in seconds (default: 180)

    Returns:
        tuple: (completion, input_token_count, output_token_count)

    Raises:
        OpenAI API exceptions on failure
    """
    logger.debug("Calling model: %s", model)

    # Call the model to get the completion
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        timeout=timeout,
        top_p=top_p,
    )

    input_token_count = completion.usage.prompt_tokens
    output_token_count = completion.usage.completion_tokens

    logger.debug(
        "API call successful. Tokens - Input: %s, Output: %s, Total: %s",
        input_token_count,
        output_token_count,
        completion.usage.total_tokens,
    )

    response_preview = (completion.choices[0].message.content or "")[:100]
    logger.debug("Response preview: %s...", response_preview)

    return completion, input_token_count, output_token_count
