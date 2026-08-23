# /// script
# dependencies = [
#     "marimo>=0.24.0",
#     "moops>=0.15.4",
# ]
# ///

import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(args):
    args.md("# Matrix transform", notebook_only=True)
    return


@app.cell
def _(args, transform):
    interface = args.interface(transform)
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
def _(args):
    transform = args.matrix(
        [[1.0, 0.0], [0.0, 1.0]],
        min_value=-5,
        max_value=5,
        step=0.1,
        row_labels=["x out", "y out"],
        column_labels=["x", "y"],
        label="Transform",
        option="--transform",
        help_text="2x2 transform matrix as JSON",
    )
    transform
    return (transform,)


@app.cell
def _(args, transform):
    matrix = transform.value
    point = [2.0, 1.0]
    transformed = [
        matrix[0][0] * point[0] + matrix[0][1] * point[1],
        matrix[1][0] * point[0] + matrix[1][1] * point[1],
    ]
    determinant = matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]
    args.md(f"""
    The point `{point}` becomes `{transformed}`.

    Determinant: `{determinant:.2f}`
    """)
    return


if __name__ == "__main__":
    app.run()
