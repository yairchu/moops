# moops

Easily write Marimo notebooks that work as CLI scripts (and more!) with minimal boilerplate.

Marimo supports notebooks running as CLI scripts,
but until now this required maintaining matching input handling implementations.

Using `moops`, both implementations are merged into one.

## Installation

```sh
uv add "moops @ git+https://github.com/yairchu/moops"
```

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
    text="Hello World",
    style="snake_case",
)

assert result == "hello_world"
```

Keyword arguments override `moops.Group` inputs by their option names,
with leading dashes removed and dashes converted to underscores.
If no overrides are provided, `moops.run` uses the notebook defaults.

## Property-based testing

`moops.testing.notebook_interface` returns the notebook's `Interface`, from which `.strategy()` generates a [Hypothesis](https://hypothesis.readthedocs.io/) strategy that produces valid `moops.run` kwargs by introspecting the notebook's interface — dropdowns yield their allowed keys, switches yield booleans, and text fields yield arbitrary strings.

```python
from examples import name_casing

_name_casing_interface = moops.testing.notebook_interface(name_casing)
_name_casing_defaults = _name_casing_interface.default

@hypothesis.given(_name_casing_interface.strategy())
def test_name_casing_preserves_alphanumeric_count(kwargs):
    result = moops.run(name_casing, **kwargs)
    input_text = kwargs.get("input_text", _name_casing_defaults["input_text"])
    assert sum(c.isalnum() for c in result) == sum(c.isalnum() for c in input_text)
```

## Running the examples

From the project root:

```sh
uv run examples/notebook.py
```

Or `uv run marimo edit` to run as notebooks.

## Feedback welcome

This is an early release — issues, ideas, and pull requests are very welcome on [GitHub](https://github.com/yairchu/moops).
