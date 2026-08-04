# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.15.4",
# ]
# ///

import marimo

__generated_with = "0.23.16"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(args):
    args.md(
        """
        # Sparse mapping

        Set a list length, then override only the elements that should be
        nonzero. The CLI mapping option remains compact and stable regardless
        of the selected length.
        """,
        notebook_only=True,
    )
    return


@app.cell
def _(args, items, length):
    interface = args.interface(length, items)
    interface
    return


@app.cell
def _():
    import marimo as mo

    import moops

    return mo, moops


@app.cell
def _(moops):
    args = moops.Group()
    return (args,)


@app.cell
def _(mo):
    get_items, set_items = mo.state({})
    return get_items, set_items


@app.cell
def _(get_items):
    items_value = get_items()
    return (items_value,)


@app.cell
def _(args):
    length = args.number(
        label="Length",
        option="--len",
        start=0,
        stop=100,
        step=1,
        help_text="Size of the list",
    )
    length
    return (length,)


@app.cell
def _(args, items_value, set_items):
    items = args.mapping(
        label="Nonzero items",
        option="--item",
        key=int,
        value=float,
        default=items_value,
        on_change=set_items,
        help_text="Override an element as INDEX=VALUE",
    )
    items
    return (items,)


@app.cell
def _(args, items, length):
    with args.assertions():
        invalid = [index for index in items.value if not 0 <= index < length.value]
        assert not invalid, f"Indices outside the list: {invalid}"

    values = [0.0] * length.value
    for _index, _value in items.value.items():
        values[_index] = _value
    return (values,)


@app.cell
def _(args, values):
    args.md(f"Values: {values}\n\nSum: **{sum(values):.2f}**")
    return


if __name__ == "__main__":
    app.run()
