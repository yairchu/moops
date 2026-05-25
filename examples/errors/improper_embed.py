# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.6.1",
# ]
# ///

import marimo

__generated_with = "0.23.8"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(args):
    args.md(
        """
    # Improper embed

    This notebook intentionally clones and embeds a child app in the same cell.
    In notebook mode, `moops.embed()` should reject this for the same reason as
    `App.embed()`: the clone must be created in one cell and embedded from
    another cell so marimo can track the dependency.
    """,
        notebook_only=True,
    )
    return


@app.cell
def _(args):
    interface = args.interface()
    interface
    return


@app.cell
def _():
    import pathlib
    import sys

    import moops

    sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
    import name_casing

    return moops, name_casing


@app.cell
def _(moops):
    args = moops.Group()
    return (args,)


@app.cell
def _(args):
    casing_args = args.subgroup("casing", overrides={"text": "same cell"})
    return (casing_args,)


@app.cell
async def _(casing_args, moops, name_casing):
    name_casing_instance = name_casing.app.clone()

    # To fix, split the cell to two here

    embedded = await moops.embed(name_casing_instance, defs={"args": casing_args})
    embedded.output
    return


if __name__ == "__main__":
    app.run()
