# moops

Easily write Marimo notebooks that work as CLI scripts (and more!) with minimal boilerplate.

Marimo supports notebooks running as CLI scripts,
but until now this required maintaining matching input handling implementations.

Using `moops`, both implementations are merged into one.

## Transition guide

* Create your argument group: `args = moops.Group()`
* Replace your `mo.ui` usages with using methods of `args`
* Add `args.interface` call, preferably as the top cell, and provide the UI elements to it. This makes the notebook works as a script and adds info about it in the notebook.

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

Keyword arguments override `moops.Group` inputs by their label names.
If no overrides are provided, `moops.run` uses the notebook defaults.

## Property-based testing

`moops.testing.from_notebook` generates a [Hypothesis](https://hypothesis.readthedocs.io/) strategy that produces valid `moops.run` kwargs by introspecting the notebook's interface — dropdowns yield their allowed keys, switches yield booleans, and text fields yield arbitrary strings.

```python
from examples import name_casing

_defaults = moops.testing.defaults(name_casing)

@hypothesis.given(moops.testing.from_notebook(name_casing))
def test_name_casing_preserves_alphanumeric_count(kwargs):
    result = moops.run(name_casing, **kwargs)
    input_text = kwargs.get("input_text", _defaults["input_text"])
    assert sum(c.isalnum() for c in result) == sum(c.isalnum() for c in input_text)
```

`moops.testing.defaults(module)` returns the default value for each string control, useful for filling in omitted inputs when writing assertions.

`from_notebook` covers all controls, including those not passed to `interface`. Controls omitted from `interface` are notebook-only — they don't appear in CLI help — but they are still overridable via `moops.run` and exercised by property tests. This keeps `from_notebook` consistent with `moops.run`.

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
