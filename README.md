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

## Running the examples

From the project root:

```sh
uv run examples/notebook.py
```

Or `uv run marimo edit` to run as notebooks.

## Missing features

* File inputs
* Testing support: drive notebook logic from tests using moops
* Notebook inputs presets: allow saving and loading the current settings of an option group
* More interfaces
  * Exposing a Marimo notebook as simple callable functions?
  * HTTP services, OpenAPI?
