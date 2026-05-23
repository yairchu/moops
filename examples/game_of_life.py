# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.5.0",
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
def _(args, step_controls, steps):
    interface = args.interface(step_controls, steps)
    interface
    return


@app.cell
def _():
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np

    return mo, np, plt


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
        value=1,
        start=1,
        stop=100,
        step=1,
        label="Steps",
        help_text="Number of iterations to run",
    )
    steps
    return (steps,)


@app.cell
def _(game_of_life_iteration, moops, step_controls, steps):
    _kwargs = step_controls.value
    _board = _kwargs["board"]
    for _ in range(int(steps.value)):
        _board = moops.run(
            game_of_life_iteration,
            **{**_kwargs, "board": _board},
        )
    result = _board
    return (result,)


@app.cell
def _(np, plt, result):
    plt.imshow(np.array([list(x) for x in result.split()]) == "#")
    plt.xticks([])
    plt.yticks([])
    plt.gca()
    return


if __name__ == "__main__":
    app.run()
