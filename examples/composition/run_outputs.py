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
    args.md(
        "# Optimization sweep - collecting child notebook outputs",
        notebook_only=True,
    )
    return


@app.cell
def _(args, xs):
    interface = args.interface(xs)
    interface
    return


@app.cell
def _():
    import marimo as mo

    import moops

    return mo, moops


@app.cell
def _():
    # The step notebook, run once per swept point below.
    import optimization_step

    return (optimization_step,)


@app.cell
def _(moops):
    args = moops.Group()
    return (args,)


@app.cell
def _(mo):
    get_xs, set_xs = mo.state([])
    return get_xs, set_xs


@app.cell
def _(get_xs):
    xs_val = get_xs()
    return (xs_val,)


@app.cell
def _(args, set_xs, xs_val):
    xs = args.list(
        option="--x",
        item=lambda g: g.number(
            value=0.0, step=0.5, option="--x", help_text="A point to evaluate"
        ),
        help_text="Points to sweep",
        value=xs_val,
        on_change=set_xs,
    )
    xs
    return (xs,)


@app.cell
def _(moops, optimization_step, xs):
    # Run the step notebook once per point. moops.run would return only each
    # child's `result`; here we set output_mode=NOTEBOOK so each child renders
    # its visual, then collect the rendered `report` from app.run()'s defs.
    results = []
    reports = []
    for _x in xs.value:
        _child = moops.Group.with_overrides({"x": _x})
        _child.output_mode = moops.OutputMode.NOTEBOOK
        _, _defs = moops.workarounds.run_in_thread_if_in_async(
            optimization_step.app.run, defs={"args": _child}
        )
        results.append(_defs["result"])
        reports.append(_defs["report"])
    return reports, results


@app.cell
def _(args, mo, reports, results):
    if results:
        args.md(f"## {len(results)} points; best loss **{min(results):.3f}**")
        view = mo.vstack(reports)
    else:
        args.md("## Add points above to sweep")
        view = mo.md("")
    view
    return


if __name__ == "__main__":
    app.run()
