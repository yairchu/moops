# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.5.0",
# ]
# ///

import marimo

__generated_with = "0.23.6"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(args):
    args.md("# Non-string options", notebook_only=True)
    return


@app.cell
def _(args, count_dropdown, selected_numbers):
    interface = args.interface(count_dropdown, selected_numbers)
    interface
    return


@app.cell
def _():
    import moops

    return (moops,)


@app.cell
def _(moops):
    args = moops.Group()
    return (args,)


@app.cell
def _(args):
    count_dropdown = args.dropdown(
        [1, 2, 3],
        value=2,
        label="Count",
        help_text="Numeric dropdown option",
        allow_select_none=False,
    )
    count_dropdown
    return (count_dropdown,)


@app.cell
def _(args):
    selected_numbers = args.multiselect(
        [1, 2, 3, 4],
        value=[1, 3],
        option="--selected-numbers",
        label="Selected numbers",
        help_text="Numeric multiselect options",
    )
    selected_numbers
    return (selected_numbers,)


@app.cell
def _(count_dropdown, selected_numbers):
    result = {
        "count": count_dropdown.value,
        "selected": selected_numbers.value,
        "total": sum(selected_numbers.value),
    }
    return (result,)


@app.cell
def _(args, result):
    args.md(f"`{result}`")
    return


if __name__ == "__main__":
    app.run()
