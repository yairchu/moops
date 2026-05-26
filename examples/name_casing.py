# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.1.0",
# ]
# ///

import marimo

__generated_with = "0.23.8"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(args):
    args.md(
        r"""
    # Name casing
    """,
        notebook_only=True,
    )
    return


@app.cell
def _(args, input_text, mode_dropdown):
    interface = args.interface(mode_dropdown, input_text)
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
def _():
    def _camel_case(text):
        def cap(word):
            x, *xs = word
            return f"{x.upper()}{''.join(xs).lower()}"

        return "".join(cap(x) for x in text.split())

    name_casings = {
        "snake_case": lambda text: "_".join(x.lower() for x in text.split()),
        "camel_case": _camel_case,
    }
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
def _(args, input_text, mo, mode_dropdown):
    mo.stop(args.is_interface_query)

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


if __name__ == "__main__":
    app.run()
