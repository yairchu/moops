import marimo

__generated_with = "0.23.6"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Testing when cells rerun

    This notebook was created to reproduce a bug where
    cells unnecessarily rerun when saving the preset
    """)
    return


@app.cell
def _(args, slider):
    interface = args.interface(slider)
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
def _(mo):
    get_preset_sel, set_preset_sel = mo.state(None)
    return get_preset_sel, set_preset_sel


@app.cell
def _(get_preset_sel, moops, set_preset_sel):
    args = moops.Group(
        presets=moops.Presets(
            "cell_rerun_test_presets.json", get_preset_sel, set_preset_sel
        )
    )
    return (args,)


@app.cell
def _(args):
    slider = args.slider(
        value=50,
        start=0,
        stop=100,
        label="Test slider",
        help_text="A slider that does nothing",
        debounce=True,
    )
    slider
    return (slider,)


@app.cell
def _(mo):
    get_counter, set_counter = mo.state(0)
    return get_counter, set_counter


@app.cell
def _(get_counter, set_counter, slider):
    _ = slider.value
    set_counter(get_counter() + 1)
    return


@app.cell
def _(get_counter, mo):
    mo.md(f"""
    **{get_counter()}** slider updates
    """)
    return


if __name__ == "__main__":
    app.run()
