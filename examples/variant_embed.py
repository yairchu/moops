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
def _(args, embedded, notebook, notebook_interfaces):
    interface = args.interface(
        notebook,
        embedded.defs["interface"],
        *notebook_interfaces,
    )
    interface
    return


@app.cell
def _():
    import name_casing
    import word_count

    import moops

    return moops, name_casing, word_count


@app.cell
def _(moops):
    args = moops.Group()
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


if __name__ == "__main__":
    app.run()
