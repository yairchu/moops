# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.5.1",
# ]
# ///

import marimo

__generated_with = "0.23.8"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def _(args):
    args.md("# Trip cost", notebook_only=True)
    return


@app.cell
def _(args, car, distance, gas_price, mode, tickets, train):
    interface = args.interface(
        mode,
        car.interface(distance, gas_price),
        train.interface(tickets),
    )
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
    mode = args.dropdown(
        ["car", "train"],
        value="car",
        option="--mode",
        help_text="How to travel",
        allow_select_none=False,
    )
    mode
    return (mode,)


@app.cell
def _(args, mode):
    travel = args.variant("travel", mode)
    car = travel["car"]
    train = travel["train"]
    return car, train


@app.cell
def _(car):
    distance = car.number(
        value=120,
        start=0,
        step=5,
        option="--distance",
        help_text="Driving distance in miles",
    )
    distance
    return (distance,)


@app.cell
def _(car):
    gas_price = car.number(
        value=3.75,
        start=0,
        step=0.05,
        option="--gas-price",
        help_text="Gas price per gallon",
    )
    gas_price
    return (gas_price,)


@app.cell
def _(train):
    tickets = train.number(
        value=2,
        start=1,
        step=1,
        option="--tickets",
        help_text="Number of train tickets",
    )
    tickets
    return (tickets,)


@app.cell
def _(distance, gas_price, mode, tickets):
    if mode.value == "car":
        gallons = distance.value / 30
        result = gallons * gas_price.value
    else:
        result = tickets.value * 18
    return (result,)


@app.cell
def _(args, mode, result):
    args.md(f"{mode.value.title()} cost: **${result:.2f}**")
    return


if __name__ == "__main__":
    app.run()
