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
    args.md("# Trip planner — a list of notebook runs", notebook_only=True)
    return


@app.cell
def _(args, count, trip_controls):
    interface = args.interface(count, *trip_controls)
    interface
    return


@app.cell
def _():
    import marimo as mo

    import moops

    return mo, moops


@app.cell
def _():
    # The notebook mirrored once per list item — itself a variant notebook
    # (its controls change with the selected travel mode).
    import variant_trip

    return (variant_trip,)


@app.cell
def _(moops):
    args = moops.Group()
    return (args,)


@app.cell
def _(args):
    count = args.number(
        value=2,
        start=1,
        stop=8,
        step=1,
        option="--trips",
        help_text="How many trips to plan",
    )
    count
    return (count,)


@app.cell
def _(args, count, moops, variant_trip):
    # One mirror of variant_trip's controls per trip, each in its own prefixed
    # subgroup. controls_from recreates the child's controls here (including its
    # variant branches) rather than embedding the app, so this stays a plain
    # synchronous notebook. Changing the trip count rebuilds the list.
    trip_controls = [
        args.controls_from(moops.interface_of(variant_trip), prefix=f"trip-{i}")
        for i in range(int(count.value))
    ]
    return (trip_controls,)


@app.cell
def _(mo, trip_controls):
    mo.vstack(
        [
            mo.vstack([mo.md(f"### Trip {i + 1}"), *controls.values()])
            for i, controls in enumerate(trip_controls)
        ]
    )
    return


@app.cell
def _(moops, trip_controls, variant_trip):
    # Run variant_trip once per trip with that trip's mirrored control values.
    costs = [moops.run(variant_trip, **controls.value) for controls in trip_controls]
    total = sum(costs)
    return (total,)


@app.cell
def _(args, total, trip_controls):
    result = total
    args.md(f"## Total for {len(trip_controls)} trips: **${total:.2f}**")
    return


if __name__ == "__main__":
    app.run()
