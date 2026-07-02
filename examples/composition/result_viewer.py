# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.13.8",
# ]
# ///

import marimo

__generated_with = "0.23.9"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(args):
    args.md("# Result viewer", notebook_only=True)
    return


@app.cell
def _(args, state_path_control):
    interface = args.interface(state_path_control)
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
def _():
    summary = "No parent result was injected."
    return (summary,)


@app.cell
def _():
    state_path = "previous-state.json"
    return (state_path,)


@app.cell
def _(args, state_path):
    if state_path is None:
        state_path_control = args.text(
            value="saved-state.json",
            option="--save-path",
            help_text="Where to save the computed state",
        )
    else:
        state_path_control = args.text(
            value=state_path,
            option="--load-path",
            help_text="State file to inspect",
        )
    state_path_control
    return (state_path_control,)


@app.cell
def _(args, mo, state_path_control, summary):
    mo.stop(args.is_interface_query)

    result = {
        "summary": summary,
        "path": state_path_control.value,
    }
    mo.md(
        f"""
        ## Viewer

        {summary}

        Path: `{state_path_control.value}`
        """
    )
    return (result,)


if __name__ == "__main__":
    app.run()
