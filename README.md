# moops

[![PyPI](https://img.shields.io/pypi/v/moops.svg)](https://pypi.org/project/moops/)
[![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/yairchu/moops/blob/main/examples/composition/notebook.py)

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

## Agent-assisted migrations

If you use a coding agent, moops includes an agent skill for migrating existing
marimo notebooks: [`migrate-marimo-to-moops`](skills/migrate-marimo-to-moops/SKILL.md).

Install or point your agent at that skill, then ask it to migrate a notebook to
moops while preserving the notebook's behavior.

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
from examples.composition import name_casing

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

## Variant inputs

Use `args.variant()` to create branch subgroups controlled by a selector. Branch
controls are normal controls and should still be passed to `args.interface()`;
inactive branch controls are disabled automatically, and CLI help groups branch
options under selector-specific headings.

```python
source = args.dropdown(
    ["heuristic", "file"],
    value="heuristic",
    option="--source",
    help_text="Seed source",
    allow_select_none=False,
)
seed = args.variant("seed", source)

budget = seed["heuristic"].number(value=100, help_text="Heuristic budget")
path = seed["file"].text(value="", help_text="Result file")

interface = args.interface(
    source,
    seed["heuristic"].interface(budget),
    seed["file"].interface(path),
)
```

Pass `short_options=True` to `args.variant()` to omit the variant group name
from branch CLI options, such as `--file-path` instead of `--seed-file-path`.
Moops rejects shortened options that would collide.

## Presets

Presets save and restore named groups of control values from a JSON file stored
next to the calling notebook as `<notebook>_presets.json`.

```python
get_preset, set_preset = mo.state(None)
args = moops.Group(presets=moops.Presets(get_preset, set_preset))
```

With presets enabled, the command line shown in the script callout is editable:
edit it in place (or paste a different command) and commit to initialize every
control from those arguments. Malformed input is reported inline.

## Custom notebook controls

Use `args.custom()` when the notebook needs an interactive control that moops
does not wrap directly, while the CLI should use a supported fallback control.
The fallback supplies the CLI parser, help text, defaults, and query-parameter
format.

`build(value)` is a factory that constructs the notebook component from the
fallback's resolved value. Passing a factory (rather than a pre-built control)
lets `controls_from` recreate the component when the notebook is mirrored into a
parent. `value(component, fallback)` maps the component's value to the
fallback's shape.

```python
fallback_slider = args.range_slider(
    start=0,
    stop=100,
    value=[10, 50],
    option="--x-range",
    help_text="X axis range",
)
x_range = args.custom(
    fallback_slider,
    lambda x_range: mo.ui.matplotlib(build_selection_plot(x_range)),
    value=lambda plot, fallback:
        [plot.value.x_min, plot.value.x_max]
        if plot.value else fallback.value,
)
```

## Property-based testing

`moops.interface_of` returns the notebook's `Interface`, from which `.strategy()` generates a [Hypothesis](https://hypothesis.readthedocs.io/) strategy that produces valid `moops.run` kwargs by introspecting the notebook's interface — dropdowns yield their allowed keys, switches yield booleans, and text fields yield arbitrary strings.

Hypothesis is an optional dependency, since it is only needed for `.strategy()`; install it with `pip install moops[test]` (or just `pip install hypothesis`).

```python
from examples.composition import name_casing

_name_casing_interface = moops.interface_of(name_casing)
_name_casing_defaults = _name_casing_interface.default

@hypothesis.given(_name_casing_interface.strategy())
def test_name_casing_preserves_alphanumeric_count(kwargs):
    result = moops.run(name_casing, **kwargs)
    input_text = kwargs.get("input_text", _name_casing_defaults["input_text"])
    assert sum(c.isalnum() for c in result) == sum(c.isalnum() for c in input_text)
```

## Running the examples

The `examples/` directory is grouped by topic:

* `basics/` — small notebooks covering options, flags, file inputs, dataclass inputs, and status output
* `custom_controls/` — `args.custom()` and mirroring it via `controls_from`
* `composition/` — embedding and varying notebooks (`embed`, `variant_embed`)
* `game_of_life/` — a worked multi-notebook example
* `passthrough/` — passing values between notebooks

From the project root:

```sh
uv run examples/composition/notebook.py
uv run --with matplotlib --with numpy examples/custom_controls/custom_control.py --x-range 30,70
```

Or `uv run marimo edit` to run as notebooks.

## Feedback welcome

This is an early release — issues, ideas, and pull requests are very welcome on [GitHub](https://github.com/yairchu/moops).
