# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops[status]>=0.13.4",
# ]
# ///

import marimo

__generated_with = "0.23.9"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(args):
    args.md("# Status report", notebook_only=True)
    return


@app.cell
def _(args, steps):
    interface = args.interface(steps)
    interface
    return


@app.cell
def _():
    import time

    return (time,)


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
    steps = args.number(
        value=3,
        start=1,
        stop=10,
        step=1,
        option="--steps",
        help_text="Number of fake work items to report",
    )
    steps
    return (steps,)


@app.cell
def _(args, steps, time):
    total = 0
    with args.spinner(title="Preparing work") as status:
        status.update(subtitle=f"{steps.value} items")
        time.sleep(1.5)
    for n in args.progress_bar(
        range(int(steps.value)),
        title="Processing",
        completion_title="Processed",
    ):
        time.sleep(0.5)
        total += n * n
    result = total
    return (result,)


@app.cell
def _(args, result):
    args.md(f"Result checksum: **{result}**")
    return


if __name__ == "__main__":
    app.run()
