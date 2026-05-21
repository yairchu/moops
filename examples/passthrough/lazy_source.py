# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.4.0",
# ]
# ///

import marimo

__generated_with = "0.23.6"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(args):
    args.md("# Lazy source", notebook_only=True)
    return


@app.cell
def _(args, text_input):
    interface = args.interface(text_input)
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
    text_input = args.text_area(
        value="",
        label="Source text",
        help_text="Leave empty to exercise Passthrough with no source result",
    )
    text_input
    return (text_input,)


@app.cell
def _(args, mo, text_input):
    # Skip computation when the notebook is queried only for its interface.
    mo.stop(args.is_interface_query)
    # No default value — result is absent from defs until the user types something.
    mo.stop(not text_input.value, mo.md("*Waiting for input…*"))
    result = text_input.value
    return (result,)


if __name__ == "__main__":
    app.run()
