# /// script
# dependencies = [
#     "marimo>=0.24.0",
#     "moops",
#     "numpy",
# ]
# ///

import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(args):
    args.md("# Matrix pseudoinverse", notebook_only=True)
    return


@app.cell
def _(args, matrix):
    interface = args.interface(matrix)
    interface
    return


@app.cell
def _():
    import numpy as np

    import moops

    return moops, np


@app.cell
def _(moops):
    args = moops.Group()
    return (args,)


@app.cell
def _(args):
    matrix = args.matrix(
        [[1.0, 2.0], [3.0, 4.0], [5.0, 7.0]],
        step=0.1,
        row_labels=["a", "b", "c"],
        column_labels=["x", "y"],
        label="Matrix",
        help_text="Matrix to pseudoinvert as JSON",
    )
    matrix
    return (matrix,)


@app.cell
def _(matrix, np):
    pseudoinverse = np.linalg.pinv(np.asarray(matrix.value)).tolist()
    return (pseudoinverse,)


@app.cell
def _(args, pseudoinverse):
    args.matrix_display(
        pseudoinverse,
        row_labels=["x", "y"],
        column_labels=["a", "b", "c"],
        label="Pseudoinverse",
        precision=4,
    )
    return


if __name__ == "__main__":
    app.run()
