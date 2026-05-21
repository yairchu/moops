# moops

[![PyPI](https://img.shields.io/pypi/v/moops.svg)](https://pypi.org/project/moops/)
[![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/yairchu/moops/blob/main/examples/notebook.py)

Easily write Marimo notebooks that work as CLI scripts (and more!) with minimal boilerplate.

Marimo supports notebooks running as CLI scripts,
but until now this required maintaining matching input handling implementations.

Using `moops`, both implementations are merged into one.

## Installation

`uv add` (or `pip install`) `moops`

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

## URL query parameters

In browser notebooks, `Group()` lets URL query parameters initialize controls
and keeps later control changes reflected in the URL.

```python
args = moops.Group()
input_text = args.text(value="", help_text="Input text")
style = args.dropdown(
    ["snake_case", "camel_case"],
    value="snake_case",
    help_text="Output style",
    allow_select_none=False,
)
```

Opening the notebook with `?input_text=Hello&style=camel_case` initializes
those controls from the URL. Query keys use the same names as `moops.run`
keyword arguments. For subgroups, use dot-separated names such as
`?casing.style=camel_case`.

## Presets

Presets save and restore named groups of control values from a JSON file stored
next to the calling notebook as `<notebook>_presets.json`.

```python
get_preset, set_preset = mo.state(None)
args = moops.Group(presets=moops.Presets(get_preset, set_preset))
```

## Custom notebook controls

Use `args.custom()` when the notebook needs an interactive control that moops
does not wrap directly, while the CLI should use a supported fallback control.
The fallback supplies the CLI parser, help text, defaults, and query-parameter
format.

```python
plot_selection = mo.ui.matplotlib(ax)
fallback_slider = args.range_slider(
    start=0,
    stop=100,
    value=[10, 50],
    option="--x-range",
    help_text="X axis range",
)
x_range = args.custom(
    plot_selection,
    fallback_slider,
    value=lambda plot:
        [plot.value.x_min, plot.value.x_max]
        if plot.value else fallback_slider.value,
)
```

## Property-based testing

`moops.interface_of` returns the notebook's `Interface`, from which `.strategy()` generates a [Hypothesis](https://hypothesis.readthedocs.io/) strategy that produces valid `moops.run` kwargs by introspecting the notebook's interface — dropdowns yield their allowed keys, switches yield booleans, and text fields yield arbitrary strings.

```python
from examples import name_casing

_name_casing_interface = moops.interface_of(name_casing)
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
uv run --with matplotlib --with numpy examples/custom_control.py --x-range 30,70
```

Or `uv run marimo edit` to run as notebooks.

## Feedback welcome

This is an early release — issues, ideas, and pull requests are very welcome on [GitHub](https://github.com/yairchu/moops).
