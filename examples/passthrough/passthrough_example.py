# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.4.0",
# ]
# ///

import marimo

__generated_with = "0.23.6"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # moops.Passthrough demo

    Both this notebook and `word_report` start from the same `text_source` step.
    Rather than running `text_source` twice, we pass
    `moops.Passthrough(source_result)` into `word_report` so it reuses
    the result already computed here.
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
    import text_source

    return (text_source,)


@app.cell
def _():
    import word_report

    return (word_report,)


@app.cell
def _(moops):
    args = moops.Group()
    return (args,)


@app.cell
def _(text_source):
    text_source_instance = text_source.app
    return (text_source_instance,)


@app.cell
def _(word_report):
    word_report_instance = word_report.app
    return (word_report_instance,)


@app.cell
def _(args):
    source_args = args.subgroup("source")
    return (source_args,)


@app.cell
async def _(moops, source_args, text_source_instance):
    source_result = await moops.embed(text_source_instance, defs={"args": source_args})
    source_result.output
    return (source_result,)


@app.cell
def _(args):
    report_args = args.subgroup("report")
    return (report_args,)


@app.cell
async def _(moops, report_args, source_result, word_report_instance):
    # word_report would normally run text_source itself — moops.Passthrough
    # makes it reuse source_result instead.
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
