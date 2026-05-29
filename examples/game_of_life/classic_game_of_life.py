# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.5.0",
# ]
# ///

import marimo

__generated_with = "0.23.6"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(args):
    args.md(
        """
    # Game of Life (Classic)

    Embeds `game_of_life_iteration.py` with rules locked to classic Conway rules.

    Demonstrates the `_LockedMultiselect` workaround for
    `mo.ui.multiselect` not supporting `disabled=True`.
    """,
        notebook_only=True,
    )
    return


@app.cell
def _(args, step_result):
    interface = args.interface(step_result.defs["interface"])
    interface
    return


@app.cell
def _():
    import moops

    return (moops,)


@app.cell
def _():
    import game_of_life_iteration

    return (game_of_life_iteration,)


@app.cell
def _(moops):
    args = moops.Group()
    return (args,)


@app.cell
def _(args):
    step_args = args.subgroup(
        "step",
        overrides={
            "survive_rule": ["2", "3"],
            "birth_rule": ["3"],
        },
    )
    return (step_args,)


@app.cell
def _(game_of_life_iteration):
    gol_app = game_of_life_iteration.app.clone()
    return (gol_app,)


@app.cell
async def _(gol_app, moops, step_args):
    step_result = await moops.embed(gol_app, defs={"args": step_args})
    step_result.output
    return (step_result,)


if __name__ == "__main__":
    app.run()
