# TODO: code review findings

Full-source review of `src/moops` (~5.7k lines) by Claude (Fable 5),
2026-06-10. Working list — check items off as they are addressed. Overall:
code is in good shape; these are the leftovers.

## Bugs

- [x] **Fallback file list renders in arbitrary order** — `_ui_workarounds.py:131`
  `FileBrowserWithInitialSelection._mime_` uses a *set* comprehension:
  `"\n".join({f"- \`{p}\`" for p in self._default})`. With multiple default
  paths the "Falling back to:" list shows in random order and silently dedups.
  Use a list comprehension (dedup explicitly only if intended).

## Smells / correctness-adjacent

- [ ] **`Interface.controls` annotated as a 1-tuple** — `interface.py:29`
  `controls: tuple[typing.Any]` means "tuple of exactly one element"; should be
  `tuple[typing.Any, ...]`. Strict pyright doesn't flag it because `Any`
  absorbs everything. `_embed.py`'s `typing.cast(tuple[typing.Any], ())` for
  the empty Passthrough interface is a workaround for this and can go away.
- [ ] **User-facing validation via `assert`** — `group.py:662`
  (`assert len(options) > 0`) and the asserts in `_naming.OptionLabel.make`.
  Asserts vanish under `python -O` and these validate caller input, not
  internal invariants. Raise `ValueError` instead.
- [ ] **Duplicated key-normalization logic that must never drift** —
  `_value_resolution.ValueResolver.override_key` (`_value_resolution.py:21`)
  and `Interface._key` (`interface.py:289`) implement the identical algorithm
  (strip option prefix, lstrip dashes, drop `no-`, dashes→underscores). If one
  changes, `moops.run()` override keys and interface/query keys silently
  diverge. Extract one shared helper (e.g. in `_naming`).
- [ ] **Sub-threshold duplication** (symilar's 5-line gate misses these):
  - `Group.switch` / `Group.checkbox` — only the widget literal differs.
  - `FileControl.create_marimo_element` / `MultiFileControl.create_marimo_element`
    — same browser_kwargs / initial_path dance.
  - `MultiFileControl.parse_query_value` / `MultiSelectControl.parse_query_value`
    — same JSON-list parsing shape.
  - `Interface.validate` flag/value loop vs `_list_options._validate_item_args`
    — same validation semantics implemented twice.

## Maintainability risks

- [ ] **Unbounded `marimo>=0.23.1` while depending on marimo privates** —
  code imports `marimo._plugins.ui._core.ui_element`,
  `marimo._runtime.context`, `marimo._messaging.mimetypes`, and reads/writes
  `_value`, `_selected_key`, `_id`, `_lens`, `_on_change`, `_component_args`.
  Any marimo release can break installed copies at runtime. Add an upper bound
  on marimo, or a CI job against marimo pre-releases.
- [ ] **`inspect.stack()` where `currentframe()` suffices** — `group.py:233`
  (`Group.interface`) builds the full stack with source context per call;
  `inspect.currentframe().f_back` (already used in `subgroup`) is far cheaper.
  Same in `presets._stack_filename`, which indexes two frames up the stack.
- [ ] **Unix-only path splitting** — `interface.py` `help()` and
  `apply_cli_args()` take the command basename by splitting on `"/"`; won't
  strip directories on Windows. Use `pathlib.PurePath(...).name` if Windows
  matters.

## Minor / edge cases

- [ ] `group.py:659` — `allow_select_none: bool | None = None` is immediately
  coerced to `True`; drop the dead `None` dance and default to `True`.
- [ ] `_parse.from_options` / `_is_option_token` treat only `-<digit>` as a
  negative-number value, so `--x -.5` fails confusingly ("Unexpected
  argument: -.5") while `--x=-.5` works. (Round-trip of formatted values is
  safe: `str()` of any float starts with `-<digit>`.) Consider mentioning the
  `=` form in the error.
- [ ] `Group.md` CLI mode strips only bare ``` fences — ```` ```python ````
  blocks keep their fence; the single-backtick strip can mangle text with two
  separate inline code spans.
- [ ] `MultiSelectControl.prompt_interactive` doesn't validate entries against
  the choices (number/file/dropdown prompts re-prompt until valid); a typo
  surfaces later as a parse error instead.
- [ ] `_UNSET = object()` sentinel defined independently in `_options`,
  `_list_options`, and `_value_resolution`; could be shared.
- [ ] `tests/test_group.py` (2.5k lines, 106 tests) is big enough to consider
  splitting by area (parsing, lists, variants, query params) next time it grows.
