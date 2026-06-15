# TODO

## Over-engineering audit (ponytail-audit)

Ranked biggest cut first. Tags: `native` (platform/dep already does it),
`shrink` (same logic, fewer lines), `yagni` (abstraction with one use),
`stdlib` (hand-rolled thing the stdlib ships).

- [x] `native:` `hypothesis` is a hard runtime dependency but only backs
  `Interface.strategy()`, a property-testing helper. Move it to an optional
  `[dependency-groups]`/extra and lazy-import at the 3 `from hypothesis import
  strategies` sites (`_options.py:12`, `interface.py:10`, `_list_options.py:9`)
  so plain CLI/notebook users don't pull a test framework. (`pyproject.toml:31`)
  **-1 runtime dep.** Done in d19756e — moved to `[project.optional-dependencies]
  test` + dev group, deferred under `TYPE_CHECKING`, lazy-imported per
  `strategy()` body.
- [x] `shrink:` `CustomControl`'s 11 pure-delegation methods
  (`options`/`flags`/`allows_repeated_values`/`parse`/`parse_query_value`/
  `format_query_value`/`strategy`/`format_usage_parts`/`format_help_lines`/
  `format_value`/`prompt_interactive`) each just `return self.inner.<same>(...)`.
  ~~Replace with `__getattr__` delegation to `inner`~~ — not possible: 7 of the
  delegations implement `@abstractmethod`s, so `__getattr__` can't satisfy the
  ABC. Done better in 5f03c7e: deleted `CustomControl` entirely; `InputControl`
  gained optional `custom_build`/`custom_value_fn` fields + a `make_element`
  template method, and `Group.custom()` sets those on the fallback via
  `dataclasses.replace`. **−57 lines** (more than the ~30 estimated).
- `yagni:` `Protocol` enum with `NONE = "none"  # room for ITERM / SIXEL
  backends later` — two values, every use is `is Protocol.KITTY` /
  `is Protocol.NONE`. Collapse `detect()` to return a `bool` ("terminal supports
  inline images"). (`_terminal_graphics.py:18-23,40,50,105` + `group.py:342`)
  **~8 lines + the speculative comment.**
- `yagni:` `CustomValueSource` Protocol + `_default_custom_value` — the Protocol
  types two params in one file (use `typing.Any`); the default fn just returns
  `component.value`, inline as `value_fn or (lambda c, _f: c.value)`.
  (`_custom_element.py:10-22`) **~8 lines.**
- `yagni:` `QueryParamStore` Protocol — declared to type a single field
  `params: QueryParamStore | None`. Replace with
  `typing.MutableMapping[str, Any]` (or `Any`); the `.get`/`.remove`/`pop`
  access is already duck-typed via `getattr`. (`_query_params.py:11-15,25`)
  **~5 lines.**
- `stdlib:` `_empty_cli_opts()` returns `{}` for one `default_factory` — and the
  same file already uses `default_factory=dict` at line 56. Use
  `default_factory=dict`. (`_options.py:21-22,993`) **-3 lines.**

net: -~55 lines, -1 runtime dep possible.

Not flagged (checked, legitimate): `OutputMode` enum (2 live values, both used),
`ValueControl`/`_NoneFlag` shared bases (6 and 3 real subclasses),
`workarounds.run_in_thread_if_in_async`, `_run_button` stub.
