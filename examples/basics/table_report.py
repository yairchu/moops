# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.12.3",
#     "pandas",
# ]
# ///

import marimo

__generated_with = "0.23.9"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(args):
    args.md("# Table report", notebook_only=True)
    return


@app.cell
def _(args):
    interface = args.interface()
    interface
    return


@app.cell
def _():
    import pandas as pd

    import moops

    return moops, pd


@app.cell
def _(moops):
    args = moops.Group()
    return (args,)


@app.cell
def _(pd):
    report = pd.DataFrame(
        [
            {"item": "baseline", "score": 0.812, "error": 0.188},
            {"item": "candidate", "score": 0.947, "error": 0.053},
        ]
    )
    return (report,)


@app.cell
def _(args, report):
    _ratios = ["score", "error"]
    args.table(
        report,
        format_mapping=dict.fromkeys(_ratios, "{:.1%}"),
        show_data_types=False,
        selection=None,
    )
    return


if __name__ == "__main__":
    app.run()
