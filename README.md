# moops

Easily write Marimo notebooks that work as CLI scripts with minimal boilerplate.

Marimo supports notebooks running as CLI scripts,
but until now this required maintaining matching input handling implementations.

Using `moops`, both implementations are merged into one.

## Transition guide

* Create your argument group: `args = moops.Group()`
* Replace your `mo.ui` usages with using methods of `args`
* Add a help cell, preferably at the top: `args.help()`
  * Tell marimo that the help cell depends on the ui elements: `_ = ui_elem_a, ui_elem_b`

Now your notebook doubles as a CLI script

## Missing features

Support for additional Marimo ui elements:

* Dropdowns
* Sliders
* File input
* Embedded notebooks and option groups
* What else?
