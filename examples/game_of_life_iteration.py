# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.5.0",
#     "numpy>=1.26",
#     "xarray>=2024.1",
# ]
# ///

import marimo

__generated_with = "0.23.6"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(args):
    args.md("# Game of Life — One Iteration", notebook_only=True)
    return


@app.cell
def _(args, birth_rule, board_input, survive_rule):
    interface = args.interface(board_input, survive_rule, birth_rule)
    interface
    return


@app.cell
def _():
    import marimo as mo
    import numpy as np
    import xarray as xr

    return mo, np, xr


@app.cell
def _():
    import moops

    return (moops,)


@app.cell
def _(mo):
    get_preset_sel, set_preset_sel = mo.state(None)
    return get_preset_sel, set_preset_sel


@app.cell
def _(get_preset_sel, moops, set_preset_sel):
    args = moops.Group(presets=moops.Presets(get_preset_sel, set_preset_sel))
    return (args,)


@app.cell
def _(mo):
    get_board, set_board = mo.state(None)
    return get_board, set_board


@app.cell
def _(args):
    # Hidden moops control: constant default so presets compare correctly.
    board_cli = args.text_area(
        value=".#.\n###\n.#.",
        label="Current board",
        option="--board",
        help_text="Board state (. = dead, # = alive)",
    )
    return (board_cli,)


@app.cell
def _(board_cli, set_board):
    # Sync state from the moops-resolved value whenever args changes (preset
    # loaded, CLI arg applied). Does NOT re-run on Advance — only board_cli
    # (which depends on args) is in this cell's inputs.
    set_board(board_cli.value)
    return


@app.cell
def _(args, board_cli, get_board, mo):
    _board_display = mo.ui.text_area(
        value=get_board(),
        label="Current board",
    )
    board_input = args.custom(_board_display, fallback=board_cli)
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
def _(birth_rule, np, survive_rule):
    survive_set = np.array([int(x) for x in survive_rule.value])
    birth_set = np.array([int(x) for x in birth_rule.value])
    return birth_set, survive_set


@app.cell
def _(birth_set, board_input, np, survive_set, xr):
    _rows = board_input.value.strip().splitlines()
    _height = len(_rows)
    _width = max((len(r) for r in _rows), default=0)
    _src = xr.DataArray(
        np.array([list(r.ljust(_width, ".")) for r in _rows]) == "#",
        dims=["y", "x"],
    ).pad(y=(1, 1), x=(1, 1), constant_values=False)
    _total = _src.astype(int).rolling(y=3, x=3, min_periods=1, center=True).sum()
    _neighbour_counts = _total - _src.astype(int)
    _alive = _src.values
    _next = xr.where(
        _alive,
        _neighbour_counts.isin(survive_set),
        _neighbour_counts.isin(birth_set),
    )
    # Trim edges
    for _d in ["x", "y"]:
        while _next.sizes[_d] > 1 and not _next[{_d: 0}].any():
            _next = _next.isel({_d: slice(1, None)})
        while _next.sizes[_d] > 1 and not _next[{_d: -1}].any():
            _next = _next.isel({_d: slice(None, -1)})
    result = "\n".join("".join("#" if c else "." for c in row) for row in _next)
    return (result,)


@app.cell
def _(mo, result, set_board):
    mo.ui.button(label="Advance →", on_click=lambda _: set_board(result))
    return


@app.cell
def _(args, mo, result):
    mo.stop(args.is_interface_query)

    args.md(f"```\n{result}\n```")
    return


if __name__ == "__main__":
    app.run()
