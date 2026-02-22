import ast
import textwrap


def _clean_tests_source(test_string: str) -> str:
    lines = []
    for line in (test_string or "").splitlines():
        if line.strip().startswith("```"):
            continue
        lines.append(line.rstrip())
    return textwrap.dedent("\n".join(lines)).strip()


def _extract_assert_blocks_ast(cleaned_tests: str):
    try:
        module = ast.parse(cleaned_tests)
    except SyntaxError:
        return None

    assert_blocks = []
    for stmt in module.body:
        if isinstance(stmt, ast.Assert):
            source = ast.get_source_segment(cleaned_tests, stmt)
            if source:
                assert_blocks.append(textwrap.dedent(source).strip())
    return assert_blocks


def _extract_assert_blocks_fallback(cleaned_tests: str):
    blocks = []
    lines = cleaned_tests.splitlines()
    i = 0

    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        if not stripped.startswith("assert"):
            i += 1
            continue

        current_block = [stripped]
        i += 1

        while i < len(lines):
            candidate = "\n".join(current_block)
            try:
                parsed = ast.parse(candidate)
                if len(parsed.body) == 1 and isinstance(parsed.body[0], ast.Assert):
                    break
            except SyntaxError:
                pass

            next_stripped = lines[i].strip()
            if next_stripped.startswith("assert"):
                break
            current_block.append(next_stripped)
            i += 1

        candidate = "\n".join(current_block).strip()
        try:
            parsed = ast.parse(candidate)
            if len(parsed.body) == 1 and isinstance(parsed.body[0], ast.Assert):
                blocks.append(candidate)
            else:
                blocks.append(current_block[0].strip())
        except SyntaxError:
            blocks.append(current_block[0].strip())

    return blocks


def extract_assert_blocks(test_string: str):
    cleaned_tests = _clean_tests_source(test_string)
    if not cleaned_tests:
        return []

    ast_blocks = _extract_assert_blocks_ast(cleaned_tests)
    if ast_blocks is not None:
        return ast_blocks

    return _extract_assert_blocks_fallback(cleaned_tests)
