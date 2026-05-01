# ruff: noqa: F401
# pyright: reportUnusedExpression=false

import marimo

__generated_with = "0.23.4"
app = marimo.App(width="full")


@app.cell
def _(args, input_text, mode_dropdown):
    cli = args.render_cli(mode_dropdown, input_text)  # noqa: F841
    return


@app.cell
def _():
    import marimo as mo

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
def _():
    name_casings = {}

    def _add(func):
        name_casings[func.__name__] = func

    @_add
    def snake_case(text):
        return "_".join(x.lower() for x in text.split())

    @_add
    def camel_case(text):
        def cap(word):
            x, *xs = word
            return f"{x.upper()}{''.join(xs).lower()}"

        return "".join(cap(x) for x in text.split())

    return (name_casings,)


@app.cell
def _(args, name_casings):
    mode_dropdown = args.dropdown(
        name_casings,
        value="camel_case",
        label="Style",
        help_text="Text style",
    )
    mode_dropdown
    return (mode_dropdown,)


@app.cell
def _(args):
    input_text = args.text_area(
        value="Lorem Ipsum",
        label="Input text",
        option="--text",
        help_text="Input text",
    )
    input_text
    return (input_text,)


@app.cell
def _(input_text, mode_dropdown):
    result = (
        mode_dropdown.value(input_text.value)
        if mode_dropdown.value
        else input_text.value
    )
    return (result,)


@app.cell
def _(args, result):
    args.md(f"""
    ```
    {result}
    ```
    """)
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
