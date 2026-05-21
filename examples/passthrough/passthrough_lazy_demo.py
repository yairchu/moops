# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.4.0",
# ]
# ///
#
# Demo of the Passthrough-with-no-result bug.
#
# lazy_source starts with an empty text area, so it produces no `result` on
# first load.  The cell that creates moops.Passthrough(source_result) then
# crashes with KeyError because Passthrough.__init__ does source.defs["result"]
# unconditionally.  This prevents report_result from being computed and the
# parent interface cell from running, so the user sees no controls at all.

import marimo

__generated_with = "0.23.6"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Passthrough + no-result demo

    `lazy_source` starts empty, so it has no `result` yet.
    The cell below that calls `moops.Passthrough(source_result)` will crash
    with `KeyError: 'result'`, preventing this interface from ever appearing.
    """)
    return


@app.cell
def _(args, report_result, source_result):
    interface = args.interface(
        source_result.defs["interface"],
        report_result.defs["interface"],
    )
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
def _():
    import lazy_source

    return (lazy_source,)


@app.cell
def _():
    import word_report

    return (word_report,)


@app.cell
def _(moops):
    args = moops.Group()
    return (args,)


@app.cell
def _(lazy_source):
    lazy_source_instance = lazy_source.app
    return (lazy_source_instance,)


@app.cell
def _(word_report):
    word_report_instance = word_report.app
    return (word_report_instance,)


@app.cell
def _(args):
    source_args = args.subgroup("source")
    return (source_args,)


@app.cell
async def _(lazy_source_instance, moops, source_args):
    source_result = await moops.embed(lazy_source_instance, defs={"args": source_args})
    source_result.output
    return (source_result,)


@app.cell
def _(args):
    report_args = args.subgroup("report")
    return (report_args,)


@app.cell
async def _(moops, report_args, source_result, word_report_instance):
    # BUG: moops.Passthrough(source_result) crashes here with KeyError('result')
    # when lazy_source hasn't produced a result yet (empty text area on first load).
    report_result = await moops.embed(
        word_report_instance,
        defs={
            "args": report_args,
            "text_source_embed": moops.Passthrough(source_result),
        },
    )
    report_result.output
    return (report_result,)


if __name__ == "__main__":
    app.run()
