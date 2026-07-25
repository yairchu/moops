import marimo

__generated_with = "0.23.15"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np

    import moops

    return mo, moops, np, plt


@app.cell
def _(args, x_window):
    interface = args.interface(x_window)
    interface
    return


@app.cell
def _(mo):
    get_preset_sel, set_preset_sel = mo.state(None)
    return get_preset_sel, set_preset_sel


@app.cell
def _(get_preset_sel, moops, set_preset_sel):
    args = moops.Group(presets=moops.Presets(get_preset_sel, set_preset_sel))
    return (args,)


@app.cell
def _(np):
    x = np.linspace(0, 100, 301)
    y = np.sin(x / 8) + 0.2 * np.cos(x / 2)
    default_x_window = [20, 60]
    return default_x_window, x, y


@app.cell
def _(args, default_x_window):
    fallback_slider = args.range_slider(
        start=0,
        stop=100,
        step=1,
        value=default_x_window,
        option="--x-range",
        help_text="X axis range",
        show_value=True,
    )
    return (fallback_slider,)


@app.cell
def _(args, fallback_slider, mo, plt, x, y):
    # `build` is a factory so controls_from can recreate the selection plot when
    # this notebook is mirrored into a parent. It depends only on x/y (static)
    # and the fallback's resolved value, so it replays in any context.
    def _build_selection(x_range):
        _fig, _ax = plt.subplots(figsize=(10, 5))
        plt.plot(x, y)
        plt.grid()
        plt.xlabel("time (seconds)")
        plt.ylabel("signal")
        plt.title("Drag on the plot to choose an x range")
        return mo.ui.matplotlib(
            _ax, debounce=True, value={"x": x_range, "y": _ax.get_ylim()}
        )

    def _x_range_from_selection(selection_plot, fallback):
        selection = selection_plot.value
        if hasattr(selection, "vertices"):
            selected_x = [point[0] for point in selection.vertices]
            return (min(selected_x), max(selected_x))
        if selection:
            return (selection.x_min, selection.x_max)
        return fallback.value

    x_window = args.custom(
        fallback_slider, _build_selection, value=_x_range_from_selection
    )
    x_window
    return (x_window,)


@app.cell
def _(np, x, x_window, y):
    x_min, x_max = x_window.value
    in_window = (x >= x_min) & (x <= x_max)
    result = {
        "x_range": [x_min, x_max],
        "points": int(np.sum(in_window)),
        "mean_y": float(np.mean(y[in_window])),
    }
    return (result,)


@app.cell
def _(args, result):
    args.md(f"""
    ```
    x range: {result["x_range"][0]:.1f}..{result["x_range"][1]:.1f}
    points: {result["points"]}
    mean y: {result["mean_y"]:.3f}
    ```
    """)
    return


if __name__ == "__main__":
    app.run()
