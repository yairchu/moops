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
    args.md("# Trip planner - a list of notebook runs", notebook_only=True)
    return


@app.cell
def _(args, trips):
    interface = args.interface(trips)
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
def _(mo):
    get_trips, set_trips = mo.state([])
    return get_trips, set_trips


@app.cell
def _(get_trips):
    trips_val = get_trips()
    return (trips_val,)


@app.cell
def _(args, moops, set_trips, trips_val, variant_trip):
    trips = args.list(
        lambda g: g.controls_from(moops.interface_of(variant_trip), prefix="trip"),
        option="--trip",
        help_text="Trip to plan",
        value=trips_val,
        on_change=set_trips,
    )
    trips
    return (trips,)


@app.cell
def _(moops, trips, variant_trip):
    # Run variant_trip once per trip with that trip's mirrored control values.
    costs = [moops.run(variant_trip, **trip) for trip in trips.value]
    total = sum(costs)
    return (total,)


@app.cell
def _(args, total, trips):
    result = total
    args.md(f"## Total for {len(trips.value)} trips: **${total:.2f}**")
    return


if __name__ == "__main__":
    app.run()
