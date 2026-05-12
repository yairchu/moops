def demote_markdown_headings(text: str, levels: int) -> str:
    if levels <= 0:
        return text

    fence: tuple[str, int] | None = None
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        newline = line[len(content) :]
        fence = _update_markdown_fence(content, fence)
        lines.append(
            content if fence is not None else _demote_markdown_heading(content, levels)
        )
        lines[-1] += newline
    return "".join(lines)


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


def _demote_markdown_heading(line: str, levels: int) -> str:
    stripped = line.lstrip(" ")
    indent = len(line) - len(stripped)
    if indent > 3:
        return line
    count = len(stripped) - len(stripped.lstrip("#"))
    if not 1 <= count <= 6:
        return line
    if len(stripped) > count and not stripped[count].isspace():
        return line
    return f"{line[:indent]}{'#' * min(6, count + levels)}{stripped[count:]}"
