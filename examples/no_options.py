# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.3.2",
# ]
# ///

import marimo

__generated_with = "0.23.6"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(args):
    args.md("# A notebook with no options", notebook_only=True)
    return


@app.cell
def _(args):
    interface = args.interface()
    interface
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import moops

    return (moops,)


@app.cell
def _(moops):
    args = moops.Group()
    return (args,)


@app.cell
def _(args):
    args.md(
        # Flush-left so the plain-text CLI rendering is not indented; marimo
        # dedents markdown in the notebook either way.
        "## Why have no options?\n"
        "\n"
        "Most `moops` examples wrap `mo.ui` controls so the notebook doubles as\n"
        "a CLI *with arguments*. But a notebook can be worth running through\n"
        "`moops` even when it takes **no arguments at all** — when it is a\n"
        "*report* or a fixed *computation* rather than a configurable tool.\n"
        "\n"
        "You still get three things that have nothing to do with argument\n"
        "parsing:\n"
        "\n"
        "- **Dual-rendered output.** `args.md(...)` renders as rich markdown in\n"
        "  the notebook and prints as clean plain text when the notebook runs as\n"
        "  a script. Write the prose once; it reads well in both places.\n"
        "- **Composability.** When this notebook is embedded as a subgroup of\n"
        "  another, the headings below are demoted automatically so the combined\n"
        "  document keeps a sensible heading hierarchy.\n"
        "- **A uniform entry point.** `--help` and script execution behave\n"
        "  consistently with the rest of your notebooks, and `moops.run(...)`\n"
        "  can call this one from Python or a test.\n"
    )
    return


@app.cell
def _():
    result = [n for n in range(2, 30) if all(n % d for d in range(2, n))]
    return (result,)


@app.cell
def _(args, result):
    args.md(
        "## A fixed computation\n"
        "\n"
        "This notebook always produces the same answer — the primes below 30 —\n"
        "which is exactly why it needs no options:\n"
        "\n"
        f"**{', '.join(map(str, result))}**\n"
    )
    return


if __name__ == "__main__":
    app.run()
