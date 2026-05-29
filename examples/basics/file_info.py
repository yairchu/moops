# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.1.0",
# ]
# ///

import marimo

__generated_with = "0.23.5"
app = marimo.App(width="full")


@app.cell
def _(args, file_ctrl):
    interface = args.interface(file_ctrl)
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
    args = moops.Group(presets=moops.Presets(get_preset_sel, set_preset_sel))
    return (args,)


@app.cell
def _(args):
    file_ctrl = args.file_browser(
        label="File",
        help_text="File to inspect",
        multiple=False,
    )
    file_ctrl
    return (file_ctrl,)


@app.cell
def _(args, file_ctrl, mo):
    _path = file_ctrl.path()
    if _path is None:
        mo.stop(True, args.md("No file selected."))
    _lines = _path.read_text().splitlines()
    _preview = "\n".join(_lines[:20])
    result = args.md(f"**{_path.name}** — {len(_lines)} lines\n\n```\n{_preview}\n```")
    result
    return


if __name__ == "__main__":
    app.run()
