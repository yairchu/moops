# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.1.0",
# ]
# ///

import marimo

__generated_with = "0.23.6"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(args):
    args.md("# Text source", notebook_only=True)
    return


@app.cell
def _(args, text_input):
    interface = args.interface(text_input)
    interface
    return


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
    text_input = args.text_area(
        value="The quick brown fox jumps over the lazy dog",
        label="Source text",
        help_text="Text to analyze",
    )
    text_input
    return (text_input,)


@app.cell
def _(text_input):
    result = text_input.value
    return (result,)


if __name__ == "__main__":
    app.run()
