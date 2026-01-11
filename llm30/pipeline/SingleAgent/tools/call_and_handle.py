import os
import logging

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Configure logger for this module
logger = logging.getLogger(__name__)

client = OpenAI(base_url=os.getenv("OPENAI_URL_BASE"),api_key=os.getenv("OPENAI_API_KEY"))

def call_and_handle(messages, model, timeout=60):
    """
    Call the OpenAI API and handle the response.

    Args:
        messages: List of message dictionaries
        model: The model to use for generation
        timeout: Request timeout in seconds (default: 60)

    Returns:
        tuple: (completion, input_token_count, output_token_count)

    Raises:
        OpenAI API exceptions on failure
    """
    logger.debug(f"Calling model: {model}")

    # Call the model to get the completion
    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        timeout=timeout
    )

    # Extract token counts
    input_token_count = completion.usage.prompt_tokens
    output_token_count = completion.usage.completion_tokens

    # Log token usage
    logger.debug(
        f"API call successful. Tokens - Input: {input_token_count}, "
        f"Output: {output_token_count}, Total: {completion.usage.total_tokens}"
    )

    # Log response preview (first 100 chars)
    response_preview = completion.choices[0].message.content[:100]
    logger.debug(f"Response preview: {response_preview}...")

    return completion, input_token_count, output_token_count