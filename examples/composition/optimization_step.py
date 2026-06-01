# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.9.0",
# ]
# ///

import marimo

__generated_with = "0.23.8"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(args):
    args.md("# Optimization step", notebook_only=True)
    return


@app.cell
def _(args, x):
    interface = args.interface(x)
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
    x = args.number(
        value=0.0,
        step=0.5,
        option="--x",
        help_text="Point to evaluate the loss f(x) = (x - 3)**2",
    )
    x
    return (x,)


@app.cell
def _(x):
    # The loss this step reports back to a parent sweep (read via moops.run).
    result = (x.value - 3) ** 2
    return (result,)


@app.cell
def _(args, result, x):
    # Dual text output: a heading in a notebook, printed text in a CLI run.
    args.md(f"f({x.value:g}) = {result:.3f}")
    return


@app.cell
def _(args, mo, moops, result, x):
    # A richer visual. args.output_mode lets this notebook decide whether to
    # build it at all: a standalone notebook or an output-collecting parent sets
    # OutputMode.NOTEBOOK, while a lean CLI/sub-run leaves it off. Binding it to
    # `report` lets a parent collect it from app.run()'s defs.
    if args.output_mode is moops.OutputMode.NOTEBOOK:
        bar = "█" * max(1, round(result))
        report = mo.md(f"**f({x.value:g})** {bar} `{result:.2f}`")
    else:
        report = None
    report
    return (report,)


if __name__ == "__main__":
    app.run()
