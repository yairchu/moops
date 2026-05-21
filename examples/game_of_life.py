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
    args.md("# Game of Life", notebook_only=True)
    return


@app.cell
def _(args, birth_rule, board_input, steps, survive_rule):
    interface = args.interface(board_input, survive_rule, birth_rule, steps)
    interface
    return


@app.cell
def _():
    import matplotlib.pyplot as plt
    import numpy as np

    return np, plt


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
    board_input = args.text_area(
        value=".#.\n###\n.#.",
        label="Initial board",
        option="--board",
        help_text="Starting board state (. = dead, # = alive)",
    )
    board_input
    return (board_input,)


@app.cell
def _(args):
    survive_rule = args.multiselect(
        options=[str(i) for i in range(9)],
        value=["2", "3"],
        label="Survive rule",
        help_text="Neighbor counts that keep a live cell alive",
    )
    survive_rule
    return (survive_rule,)


@app.cell
def _(args):
    birth_rule = args.multiselect(
        options=[str(i) for i in range(9)],
        value=["3"],
        label="Birth rule",
        help_text="Neighbor counts that birth a new live cell",
    )
    birth_rule
    return (birth_rule,)


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
def _(
    birth_rule,
    board_input,
    game_of_life_iteration,
    moops,
    steps,
    survive_rule,
):
    _board = board_input.value
    for _ in range(int(steps.value)):
        _board = moops.run(
            game_of_life_iteration,
            board=_board,
            survive_rule=survive_rule.value,
            birth_rule=birth_rule.value,
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


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
