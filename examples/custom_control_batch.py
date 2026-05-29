# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.5.0",
#     "matplotlib>=3.8",
#     "numpy>=1.26",
# ]
# ///

import marimo

__generated_with = "0.23.8"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(args):
    args.md("# Batch over custom_control", notebook_only=True)
    return


@app.cell
def _(args, window):
    interface = args.interface(window)
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
    import custom_control

    return (custom_control,)


@app.cell
def _(moops):
    args = moops.Group()
    return (args,)


@app.cell
def _(args, custom_control, mo, moops):
    # Mirror custom_control's interface. In a notebook this recreates its custom
    # range-selection plot here (prefixed --window-x-range); on the CLI it is the
    # plain range-slider fallback. Either way `window.value` feeds moops.run.
    window = args.controls_from(
        moops.interface_of(custom_control),
        prefix="window",
    )
    mo.vstack(window.values())
    return (window,)


@app.cell
def _(custom_control, moops, window):
    result = moops.run(custom_control, **window.value)
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
