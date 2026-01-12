def process_block(text_block):
    """
    Extract code block from markdown-formatted text.

    Args:
        text_block: The text containing code block

    Returns:
        str: Extracted code without markdown formatting
    """
    if f"```python" in text_block:
        text_block = text_block[text_block.find(f"```python") + len(f"```python"):]
        text_block = text_block[:text_block.find("```")]
    elif f"```" in text_block:
        text_block = text_block[text_block.find(f"```") + len(f"```"):]
        text_block = text_block[:text_block.find("```")]
    else:
        # Fall back to raw content when no code fence is present.
        pass

    # Keep only assert statements to reduce accidental prose or partial outputs.
    lines = [
        line.strip()
        for line in text_block.splitlines()
        if line.strip().startswith("assert")
    ]
    return "\n".join(lines)
