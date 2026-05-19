# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.1.0",
# ]
# ///

import marimo

__generated_with = "0.23.6"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(args):
    args.md("# Word report", notebook_only=True)
    return


@app.cell
def _(args, source_result):
    _source_iface = source_result.defs.get("interface")
    interface = args.interface(
        *([_source_iface] if _source_iface is not None else []),
    )
    interface
    return


@app.cell
def _():
    import moops

    return (moops,)


@app.cell
def _():
    import text_source

    return (text_source,)


@app.cell
def _(moops):
    args = moops.Group()
    return (args,)


@app.cell
def _(text_source):
    # Outer notebook can inject moops.embed.Passthrough here via
    # defs={"text_source_embed": ...} to reuse an already-computed
    # text_source result instead of running it again.
    text_source_embed = text_source.app.clone()
    return (text_source_embed,)


@app.cell
def _(args):
    source_args = args.subgroup("source")
    return (source_args,)


@app.cell
async def _(source_args, text_source_embed):
    source_result = await text_source_embed.embed(defs={"args": source_args})
    source_result.output
    return (source_result,)


@app.cell
def _(args, source_result):
    _text = source_result.defs.get("result", "")
    _words = _text.split()
    result = args.md(
        f"Words: **{len(_words)}** · "
        f"Unique: **{len({w.lower() for w in _words})}** · "
        f"Avg length: **{sum(len(w) for w in _words) / len(_words):.1f}**"
        if _words
        else "*(no text)*"
    )
    result
    return


if __name__ == "__main__":
    app.run()
