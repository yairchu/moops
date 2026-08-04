import marimo

__generated_with = "0.23.16"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import moops

    return (moops,)


@app.cell
def _(args):
    args.md("""
    ## Sparse dynamic options limitation

    This notebook shows a non-ideal use-case for moops at the moment.

    The user wants to create a sparse list, where they don't wish to specify
    the values of all the items. It's nice to specify length and then specific
    items, however the CLI help becomes variable and verbose.
    """)
    return


@app.cell
def _(args, elem_sliders, len_num):
    args.interface(len_num, *elem_sliders)
    return


@app.cell
def _(moops):
    args = moops.Group()
    return (args,)


@app.cell
def _(args):
    len_num = args.number(
        label="Length",
        option="--len",
        start=0,
        stop=100,
        step=1,
        help_text="Size of the array",
    )
    len_num
    return (len_num,)


@app.cell
def _(args, len_num, mo):
    elem_sliders = mo.ui.array(
        [
            args.slider(
                label=f"x{i}",
                option=f"--x-{i}",
                start=-10,
                stop=10,
                step=0.1,
                value=0,
                help_text=f"Value element #{i}",
            )
            for i in range(len_num.value)
        ]
    )
    mo.vstack(elem_sliders)
    return (elem_sliders,)


@app.cell
def _(args, elem_sliders):
    args.md(f"Sum: **{sum(elem_sliders.value):.2f}**")
    return


if __name__ == "__main__":
    app.run()
