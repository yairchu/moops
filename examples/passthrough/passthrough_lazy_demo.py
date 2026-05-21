# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.4.0",
# ]
# ///
#
# Regression demo for Passthrough with no source result.
#
# lazy_source starts with an empty text area, so it produces no `result` on
# first load.  moops.Passthrough(source_result) used to crash with KeyError
# because Passthrough.__init__ read source.defs["result"] unconditionally.
# The parent interface should now appear even while the source is waiting for
# input.

import marimo

__generated_with = "0.23.6"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Passthrough + no-result demo

    `lazy_source` starts empty, so it has no `result` yet.
    `moops.Passthrough(source_result)` used to crash in this state; the
    parent interface should now remain visible while waiting for input.
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
    # Regression check: source_result may not have a result yet.
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
