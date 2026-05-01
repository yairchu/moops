# moops

Easily write Marimo notebooks that work as CLI scripts with minimal boilerplate.

Marimo supports notebooks running as CLI scripts,
but until now this required maintaining matching input handling implementations.

Using `moops`, both implementations are merged into one.

## Transition guide

* Create your argument group: `args = moops.Group()`
* Replace your `mo.ui` usages with using methods of `args`
* Add `args.render_cli` call, preferably as the top cell, and provide the UI elements to it. This makes the notebook works as a script and adds info about it in the notebook.

Now your notebook doubles as a CLI script

## Running notebooks from Python

Notebooks can also be called from Python with `moops.run`.
This is useful for testing notebook logic without launching Marimo,
and for reusing notebook logic from other code.

Expose a variable named `result` from the notebook:

```python
@app.cell
def _(input_text, mode_dropdown):
    result = mode_dropdown.value(input_text.value)
    return (result,)
```

Then call the notebook module directly:

```python
import moops
from examples import name_casing

result = moops.run(
    name_casing,
    input_text="Hello World",
    style="snake_case",
)

assert result == "hello_world"
```

Keyword arguments override `moops.Group` inputs by their option names.
If no overrides are provided, `moops.run` uses the notebook defaults.

## Running the examples

From the project root:

```sh
uv run examples/notebook.py
```

Or `uv run marimo edit` to run as notebooks.

## TODO

* File inputs
* Notebook inputs presets: allow saving and loading the current settings of an option group
* More interfaces
  * HTTP services, OpenAPI?
* Finalize name
  * moops may stand for "Marimo Options"
  * Could also consider Shmoop which would stand for "shell/marimo options"
  * Other ideas?
