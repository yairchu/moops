import marimo

__generated_with = "0.23.14"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Short mirrored list variant options

    Only one sibling variant opts into short options, so its `--value` control
    becomes `--item-x-value` without colliding with the other variant.
    """)
    return


@app.cell
def _(items, parent):
    interface = parent.interface(items)
    interface
    return (interface,)


@app.cell
def _():
    import shlex

    import marimo as mo

    import moops

    return mo, moops, shlex


@app.cell
def _(moops):
    source = moops.Group(cli_args=["source.py"])

    first = source.dropdown(
        ["x", "y"],
        value="x",
        option="--first",
        help_text="First variant",
        allow_select_none=False,
    )
    alpha = source.variant("alpha", first, short_options=True)
    alpha_x = alpha["x"].number(
        value=1,
        option="--value",
        help_text="Alpha value",
    )
    alpha_y = alpha["y"].number(
        value=2,
        option="--value",
        help_text="Alpha value",
    )

    second = source.dropdown(
        ["x", "y"],
        value="x",
        option="--second",
        help_text="Second variant",
        allow_select_none=False,
    )
    beta = source.variant("beta", second)
    beta_x = beta["x"].number(
        value=3,
        option="--value",
        help_text="Beta value",
    )
    beta_y = beta["y"].number(
        value=4,
        option="--value",
        help_text="Beta value",
    )

    source_interface = source.interface(
        first,
        alpha["x"].interface(alpha_x),
        alpha["y"].interface(alpha_y),
        second,
        beta["x"].interface(beta_x),
        beta["y"].interface(beta_y),
    )
    return (source_interface,)


@app.cell
def _(mo):
    original = {
        "first": "x",
        "alpha-x": {"value": 10},
        "second": "x",
        "beta-x": {"value": 3},
    }
    get_items, set_items = mo.state([original])
    return get_items, original, set_items


@app.cell
def _(get_items):
    item_values = get_items()
    return (item_values,)


@app.cell
def _(item_values, moops, set_items, source_interface):
    parent = moops.Group()
    items = parent.list(
        option="--item",
        item=lambda group: group.controls_from(
            source_interface,
            prefix="item",
        ),
        help_text="Items",
        value=item_values,
        on_change=set_items,
    )
    items
    return items, parent


@app.cell
def _(interface):
    generated_command = interface.preset_args()
    return (generated_command,)


@app.cell
def _(generated_command, moops, shlex, source_interface):
    target = moops.Group(cli_args=["repro.py", *shlex.split(generated_command)])
    parsed_items = target.list(
        option="--item",
        item=lambda group: group.controls_from(
            source_interface,
            prefix="item",
        ),
        help_text="Items",
        value=[],
    )
    return parsed_items, target


@app.cell
def _(parsed_items, target):
    target.interface(parsed_items)
    parsed = parsed_items.value[0]
    return (parsed,)


@app.cell
def _(generated_command, mo, original, parsed):
    expected_beta = original["beta-x"]["value"]
    actual_beta = parsed["beta-x"]["value"]
    mo.md(
        "Generated command:\n\n"
        f"```text\n{generated_command}\n```\n\n"
        "| Field | Before round-trip | After round-trip |\n"
        "|---|---:|---:|\n"
        f"| `alpha-x.value` | {original['alpha-x']['value']} | "
        f"{parsed['alpha-x']['value']} |\n"
        f"| `beta-x.value` | {expected_beta} | {actual_beta} |\n\n"
        "The command uses `--item-x-value 10` only for the opted-in alpha "
        "variant. The beta variant keeps its structural option prefix, so "
        f"`beta-x.value` remains `{actual_beta}`."
    )
    return


@app.cell
def _(generated_command, parent, parsed):
    with parent.assertions():
        assert generated_command == "--item --item-x-value 10", (
            f"Generated command was `{generated_command}`, expected the short "
            "alpha option `--item --item-x-value 10`"
        )
        assert parsed["alpha-x"]["value"] == 10, (
            f"`alpha-x.value` changed to `{parsed['alpha-x']['value']}`, expected `10`"
        )
        assert parsed["beta-x"]["value"] == 3, (
            f"`beta-x.value` changed to `{parsed['beta-x']['value']}`, expected `3`"
        )
    return


if __name__ == "__main__":
    app.run()
