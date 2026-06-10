def demote_markdown_headings(text: str, levels: int) -> str:
    if levels <= 0:
        return text

    margin = _common_indent_margin(text)
    fence: tuple[str, int] | None = None
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        newline = line[len(content) :]
        syntax = _strip_common_margin(content, margin)
        fence = _update_markdown_fence(syntax, fence)
        lines.append(
            content
            if fence is not None
            else _demote_markdown_heading(content, levels, margin)
        )
        lines[-1] += newline
    return "".join(lines)


def _common_indent_margin(text: str) -> int:
    indents = [
        len(line) - len(line.lstrip(" ")) for line in text.splitlines() if line.strip()
    ]
    return min(indents, default=0)


def _strip_common_margin(line: str, margin: int) -> str:
    if margin <= 0:
        return line
    return line[margin:] if line.startswith(" " * margin) else line.lstrip(" ")


def _update_markdown_fence(
    line: str, fence: tuple[str, int] | None
) -> tuple[str, int] | None:
    stripped = line.lstrip(" ")
    if len(line) - len(stripped) > 3 or not stripped:
        return fence
    marker = stripped[0]
    if marker not in "`~":
        return fence
    count = len(stripped) - len(stripped.lstrip(marker))
    if count < 3:
        return fence
    if fence is None:
        return (marker, count)
    if marker == fence[0] and count >= fence[1] and not stripped[count:].strip():
        return None
    return fence


def _demote_markdown_heading(line: str, levels: int, margin: int) -> str:
    syntax = _strip_common_margin(line, margin)
    stripped = syntax.lstrip(" ")
    indent = len(syntax) - len(stripped)
    if indent > 3:
        return line
    count = len(stripped) - len(stripped.lstrip("#"))
    if not 1 <= count <= 6:
        return line
    if len(stripped) > count and not stripped[count].isspace():
        return line
    prefix_len = len(line) - len(syntax) + indent
    return f"{line[:prefix_len]}{'#' * min(6, count + levels)}{stripped[count:]}"
