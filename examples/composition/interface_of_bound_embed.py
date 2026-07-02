# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.13.8",
# ]
# ///

import marimo

__generated_with = "0.23.9"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(args):
    args.md("# Bound interface query before a result-gated embed", notebook_only=True)
    return


@app.cell
def _(args, count, state_iface):
    interface = args.interface(count, state_iface)
    interface
    return


@app.cell
def _():
    import marimo as mo

    import moops

    return mo, moops


@app.cell
def _():
    import result_viewer

    return (result_viewer,)


@app.cell
def _(moops):
    args = moops.Group()
    return (args,)


@app.cell
def _(args):
    count = args.number(
        value=3,
        start=1,
        stop=10,
        step=1,
        option="--count",
        help_text="How many items to process",
    )
    count
    return (count,)


@app.cell
def _(args):
    state_args = args.subgroup("state")
    return (state_args,)


@app.cell
def _(moops, result_viewer, state_args):
    state_iface = moops.interface_of(
        result_viewer,
        args=state_args,
        defs={"state_path": None},
    )
    return (state_iface,)


@app.cell
def _(count):
    summary = f"Processed {int(count.value)} items."
    return (summary,)


@app.cell
async def _(moops, result_viewer, state_args, summary):
    embedded = await moops.embed(
        result_viewer.app,
        defs={
            "args": state_args,
            "state_path": None,
            "summary": summary,
        },
    )
    embedded.output
    return (embedded,)


@app.cell
def _(args, embedded):
    result = embedded.defs["result"]
    args.md(f"Embedded viewer result: `{result}`")
    return


if __name__ == "__main__":
    app.run()
