# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.8.0",
# ]
# ///

import marimo

__generated_with = "0.23.8"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(args):
    args.md("# Multiply numbers", notebook_only=True)
    return


@app.cell
def _(args, factors):
    interface = args.interface(factors)
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
def _(mo):
    get_preset, set_preset = mo.state(None)
    return get_preset, set_preset


@app.cell
def _(get_preset, moops, set_preset):
    args = moops.Group(presets=moops.Presets(get_preset, set_preset))
    return (args,)


@app.cell
def _(mo):
    get_factors, set_factors = mo.state([])
    return get_factors, set_factors


@app.cell
def _(get_factors):
    factors_val = get_factors()
    return (factors_val,)


@app.cell
def _(args, factors_val, set_factors):
    factors = args.list(
        option="--factor",
        item=lambda g: g.number(
            value=1.0, option="--factor", help_text="A factor", allow_none=False
        ),
        help_text="Factors to multiply",
        value=factors_val,
        on_change=set_factors,
    )
    factors
    return (factors,)


@app.cell
def _(factors):
    result = 1.0
    for _f in factors.value:
        result *= _f
    return (result,)


@app.cell
def _(args, result):
    args.md(f"Product: **{result}**")
    return


if __name__ == "__main__":
    app.run()
