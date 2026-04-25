# moops

Easily write Marimo notebooks that work as CLI scripts with minimal boilerplate.

Marimo supports notebooks running as CLI scripts,
but until now this required maintaining matching input handling implementations.

Using `moops`, both implementations are merged into one.

## Transition guide

* Create your argument group: `args = moops.Group()`
* Replace your `mo.ui` usages with using methods of `args`
* Add a help cell, preferably at the top, usung `args.help` and proving it with the UI elements.

Now your notebook doubles as a CLI script

## Missing features

* File inputs
* text_area with support for inputting from stdin/pipe
* Embedded notebooks and option groups
* More interfaces
  * Exposing a Marimo notebook as simple callable functions?
  * HTTP services, OpenAPI?
