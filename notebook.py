# ruff: noqa: F401
# pyright: reportUnusedExpression=false

import marimo

__generated_with = "0.23.1"
app = marimo.App(width="full")


@app.cell
def _(args, name_text, polite_switch, times_number):
    _ = polite_switch, name_text, times_number

    args.help()
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
def _(args):
    polite_switch = args.switch(
        label="Be polite", help_text="Makes the greeting polite"
    )
    polite_switch
    return (polite_switch,)


@app.cell
def _(args):
    name_text = args.text(label="Name", help_text="Name for the greeting")
    name_text
    return (name_text,)


@app.cell
def _(args):
    times_number = args.number(
        start=1,
        stop=10,
        step=1,
        value=1,
        label="Times",
        help_text="How many times to repeat the greeting",
    )
    times_number
    return (times_number,)


@app.cell
def _(args, name_text, polite_switch, times_number):
    greeting = "Hello Milady" if polite_switch.value else "You sneaky bastard!"
    parts = [
        *([name_text.value] if name_text.value else []),
        *([greeting] * times_number.value),
    ]
    args.md("... ".join(parts))
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
