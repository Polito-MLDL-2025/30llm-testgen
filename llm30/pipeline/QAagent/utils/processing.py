import textwrap


def process_block(text_block):
    """
    Extract the first fenced code block from markdown-formatted text.

    Args:
        text_block: The text containing a code block.

    Returns:
        str: Extracted code without markdown formatting.
    """
    if not text_block:
        return ""

    start = text_block.find("```")
    if start != -1:
        header_end = text_block.find("\n", start + 3)
        if header_end == -1:
            header_end = start + 3
        end = text_block.find("```", header_end + 1)
        if end == -1:
            block = text_block[header_end + 1 :]
        else:
            block = text_block[header_end + 1 : end]
    else:
        # Fall back to raw content when no code fence is present.
        block = text_block

    return textwrap.dedent(block).strip()
