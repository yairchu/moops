"""Width-aware text wrapping for CLI usage/help output and the script callout."""

import shlex


def wrap_usage(prefix: str, parts: list[str], width: int = 88) -> str:
    indent = " " * len(prefix)
    lines: list[str] = []
    current = prefix
    first_on_line = True
    for part in parts:
        attempt = current + part if first_on_line else f"{current} {part}"
        if first_on_line or len(attempt) <= width:
            current = attempt
            first_on_line = False
        else:
            lines.append(current)
            current = indent + part
    lines.append(current)
    return "\n".join(lines)


def wrap_help_line(line: str, width: int = 88) -> list[str]:
    if len(line) <= width:
        return [line]
    sep = ": "
    sep_idx = line.find(sep)
    if sep_idx == -1:
        return [line]
    header = line[: sep_idx + 1]  # e.g. "  --option METAVAR:"
    indent = "      "
    result = [header]
    current = indent
    first_on_line = True
    for word in line[sep_idx + len(sep) :].split():
        attempt = current + word if first_on_line else f"{current} {word}"
        if first_on_line or len(attempt) <= width:
            current = attempt
            first_on_line = False
        else:
            result.append(current)
            current = indent + word
    result.append(current)
    return result


def wrap_command(name: str, groups: list[str], width: int = 72) -> str:
    """Render a script command, wrapping long lines with shell continuations.

    Short commands stay on one line. When the single-line form exceeds ``width``,
    each option group goes on its own line joined by `` \\`` continuations, which
    remains valid copy-pasteable shell.
    """
    quoted_name = shlex.quote(name)
    single_line = " ".join([quoted_name, *groups])
    if not groups or len(single_line) <= width:
        return single_line
    return " \\\n    ".join([quoted_name, *groups])
