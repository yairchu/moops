import marimo

__generated_with = "0.23.4"
app = marimo.App(width="full")


@app.cell
def _(args, casing_result, name_text, polite_switch, times_number):
    args.interface(
        polite_switch,
        name_text,
        times_number,
        casing_result.defs["interface"],
    )
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
def _():
    import name_casing

    return (name_casing,)


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
def _(name_text, polite_switch, times_number):
    _greeting = "Good day!" if polite_switch.value else "Hey there!"
    _parts = [
        *([name_text.value] if name_text.value else []),
        *([_greeting] * times_number.value),
    ]
    greeting_text = "... ".join(_parts)
    return (greeting_text,)


@app.cell
def _(args, greeting_text):
    casing = args.subgroup("casing", overrides={"input_text": greeting_text})
    return (casing,)


@app.cell
def _(name_casing):
    name_casing_instance = name_casing.app.clone()
    return (name_casing_instance,)


@app.cell
async def _(casing, name_casing_instance):
    casing_result = await name_casing_instance.embed(defs={"args": casing})
    return (casing_result,)


@app.cell
def _(casing_result):
    casing_result.output
    return


@app.cell
def _(casing_result):
    result = casing_result.defs.get("result")
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
