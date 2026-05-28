# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.6.0",
# ]
# ///

import marimo

__generated_with = "0.23.8"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(args):
    args.md("# Variant embed", notebook_only=True)
    return


@app.cell
def _(another_opt, args, embedded, notebook, notebook_interfaces):
    interface = args.interface(
        notebook,
        embedded.defs["interface"],
        *notebook_interfaces,
        another_opt,
    )
    interface
    return


@app.cell
def _():
    import marimo as mo

    import moops

    return mo, moops


@app.cell
def _():
    import name_casing

    return (name_casing,)


@app.cell
def _():
    import word_count

    return (word_count,)


@app.cell
def _(mo):
    get_preset_sel, set_preset_sel = mo.state(None)
    return get_preset_sel, set_preset_sel


@app.cell
def _(get_preset_sel, moops, set_preset_sel):
    args = moops.Group(presets=moops.Presets(get_preset_sel, set_preset_sel))
    return (args,)


@app.cell
def _(args, name_casing, word_count):
    notebook = args.dropdown(
        {
            "name-casing": name_casing.app,
            "word-count": word_count.app,
        },
        value="name-casing",
        option="--notebook",
        help_text="Notebook to embed",
        allow_select_none=False,
    )
    notebook
    return (notebook,)


@app.cell
def _(args, moops, notebook):
    selected_app, embed_args, notebook_interfaces = moops.variant_embed(
        args,
        notebook,
        prefix="notebook",
    )
    return embed_args, notebook_interfaces, selected_app


@app.cell
async def _(embed_args, moops, selected_app):
    embedded = await moops.embed(selected_app, defs={"args": embed_args})
    embedded.output
    return (embedded,)


@app.cell
def _(args, embedded):
    result = embedded.defs.get("result")
    args.md(f"Selected notebook result: `{result}`")
    return


@app.cell
def _(args):
    another_opt = args.checkbox(
        label="Nothing", help_text="This option does nothing, just for test"
    )
    another_opt
    return (another_opt,)


if __name__ == "__main__":
    app.run()
