# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.8.0",
# ]
# ///

import marimo

__generated_with = "0.23.8"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(args):
    args.md("# Game of Life", notebook_only=True)
    return


@app.cell
def _(args, show_steps, step_controls, steps):
    interface = args.interface(step_controls, steps, show_steps)
    interface
    return


@app.cell
def _():
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np

    return (mo,)


@app.cell
def _():
    import moops

    return (moops,)


@app.cell
def _():
    import game_of_life_iteration

    return (game_of_life_iteration,)


@app.cell
def _(mo):
    get_preset_sel, set_preset_sel = mo.state(None)
    return get_preset_sel, set_preset_sel


@app.cell
def _(get_preset_sel, moops, set_preset_sel):
    args = moops.Group(presets=moops.Presets(get_preset_sel, set_preset_sel))
    return (args,)


@app.cell
def _(args, game_of_life_iteration, mo, moops):
    step_controls = args.controls_from(
        moops.interface_of(game_of_life_iteration),
        prefix="step",
    )
    mo.vstack(step_controls.values())
    return (step_controls,)


@app.cell
def _(args):
    steps = args.number(
        value=3,
        start=1,
        stop=100,
        step=1,
        label="Steps",
        help_text="Number of iterations to run",
    )
    steps
    return (steps,)


@app.cell
def _(args):
    show_steps = args.switch(
        value=True,
        label="Show intermediate steps",
        help_text="Print every generation, not just the final board",
    )
    show_steps
    return (show_steps,)


@app.cell
def _(game_of_life_iteration, moops, step_controls, steps):
    # Children run silent (output_mode=None); the parent renders the boards
    # itself below, so intermediate steps display in both the notebook and the
    # CLI. moops.run discards a child's own display, so emitting there would
    # only ever reach the CLI.
    _kwargs = step_controls.value
    boards = [_kwargs["board"]]
    for _ in range(int(steps.value)):
        boards.append(
            moops.run(
                game_of_life_iteration,
                output_mode=None,
                **{**_kwargs, "board": boards[-1]},
            )
        )
    return (boards,)


@app.cell
def _(boards):
    max_width = max(len(x.split("\n", 1)[0]) for x in boards)
    return (max_width,)


@app.cell
def _(args, boards, game_of_life_iteration, max_width, mo, show_steps):
    # Render with the parent's own args so figures land in this notebook (or
    # stream to the terminal on the CLI). boards[0] is the input, so the
    # intermediate-and-final view is boards[1:].
    _to_show = boards[1:] if show_steps.value else boards[-1:]
    mo.vstack(
        [
            game_of_life_iteration.show(
                args,
                b,
                width=min(8, max(2, max_width * 0.15))
                * len(b.split("\n", 1)[0])
                / max_width,
            )
            for b in _to_show
        ]
    )
    return


if __name__ == "__main__":
    app.run()
