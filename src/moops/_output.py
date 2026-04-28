import marimo as mo


def _md(text) -> mo.Html | None:
    if mo.running_in_notebook():
        return mo.md(text)
    text = text.strip()
    if text.startswith("```\n") and text.endswith("\n```"):
        text = text[4:-4]
    elif text.startswith("`") and text.endswith("`"):
        text = text[1:-1]
    print(f"{text}\n")
