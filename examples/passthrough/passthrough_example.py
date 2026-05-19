# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.1.0",
# ]
# ///

import marimo

__generated_with = "0.23.6"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # moops.embed.Passthrough demo

    Both this notebook and `word_report` start from the same `text_source` step.
    Rather than running `text_source` twice, we pass
    `moops.embed.Passthrough(source_result)` into `word_report` so it reuses
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
    import moops.embed

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
def _(moops, text_source):
    text_source_instance = moops.embed.App(text_source.app).clone()
    return (text_source_instance,)


@app.cell
def _(moops, word_report):
    word_report_instance = moops.embed.App(word_report.app).clone()
    return (word_report_instance,)


@app.cell
def _(args):
    source_args = args.subgroup("source")
    return (source_args,)


@app.cell
async def _(source_args, text_source_instance):
    source_result = await text_source_instance.embed(defs={"args": source_args})
    source_result.output
    return (source_result,)


@app.cell
def _(args):
    report_args = args.subgroup("report")
    return (report_args,)


@app.cell
async def _(moops, report_args, source_result, word_report_instance):
    # word_report would normally run text_source itself — moops.embed.Passthrough
    # makes it reuse source_result instead.
    report_result = await word_report_instance.embed(
        defs={
            "args": report_args,
            "text_source_embed": moops.embed.Passthrough(source_result),
        }
    )
    report_result.output
    return (report_result,)


if __name__ == "__main__":
    app.run()
