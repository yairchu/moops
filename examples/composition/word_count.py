# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.15.3",
# ]
# ///

import marimo

__generated_with = "0.23.6"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(args):
    args.md("# Word count", notebook_only=True)
    return


@app.cell
def _(args, text_input):
    interface = args.interface(text_input)
    interface
    return (interface,)


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
        value="Hello world",
        label="Text",
        help_text="Text to count words in",
    )
    text_input
    return (text_input,)


@app.cell
def _(interface):
    run_btn = interface.run_button(label="Count words")
    run_btn
    return (run_btn,)


@app.cell
def _(mo, run_btn, text_input):
    mo.stop(not run_btn.value)
    result = len(text_input.value.split())
    return (result,)


@app.cell
def _(args, result):
    args.md(f"Word count: **{result}**")
    return


if __name__ == "__main__":
    app.run()
