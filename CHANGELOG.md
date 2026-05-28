# Changelog

<!-- markdownlint-disable MD024 -->

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed

- Standalone CLI options that follow variant group sections in help output are
  now separated by a blank line, so they are no longer visually grouped with
  the last variant branch.

## [0.7.1] - 2026-05-27 - UI polish

### Changed

- The script callout in the interface panel now shows the current command
  prominently and collapses the full usage text under a `Usage` disclosure
  widget.

## [0.7.0] - 2026-05-26 - Variant embed improvements

### Changed

- `moops.variant_embed()` no longer dry-runs the selected notebook to obtain
  its interface. The selected notebook's interface is now read from the embed
  result (`embedded.defs["interface"]`), avoiding a redundant execution of the
  selected branch. Pass `embedded.defs["interface"]` to `args.interface()` in
  the interface cell to get the same CLI help and validation coverage as before.
- Variant branch headings in CLI help now show `(default)` when the active
  branch is selected by default, or `(selected)` when it was explicitly chosen
  (via CLI flag or UI interaction).

## [0.6.1] - 2026-05-25 - Fixes

### Fixed

- `moops.embed()` now raises the same error as `App.embed()` when called from a
  notebook cell that also defines the app instance being embedded.

## [0.6.0] - 2026-05-25 - Variant embeds

### Added

- `group.variant(prefix, selector)` creates branch subgroups whose controls are
  automatically disabled when the selector points at another branch and grouped
  under selector-specific headings in CLI help.
- `moops.variant_embed(group, selector, prefix=...)` prepares a selected
  notebook app clone and argument subgroup from a dict-backed dropdown while
  preserving CLI help for all notebook variants.

## [0.5.1] - 2026-05-23 - Fixes

### Fixed

- `controls_from`: `_current_args()` and preset saving now reflect live widget
  values. Previously, `mo.ui.dictionary` clones its elements on construction,
  so the sub-interface held stale pre-clone originals; user-driven changes were
  invisible to `_current_args()` and were therefore not captured when saving a
  preset.

## [0.5.0] - 2026-05-22 - Notebook interface inspection

### Added

- `group.controls_from(iface, prefix=..., exclude=...)` — creates a prefixed
  subgroup of controls mirroring another notebook's interface (obtained via
  `moops.interface_of()`) and returns them as a `mo.ui.dictionary`, avoiding
  duplication when a parent loops over a child notebook via `moops.run()`.
- `moops.interface_of(module)` — runs a notebook headlessly and returns its
  `Interface` without executing computation cells that respect
  `args.is_interface_query`. Useful for surfacing a notebook's controls into a
  parent that calls it in a loop via `moops.run()`.
- `args.is_interface_query` — `True` when a notebook is being run only to
  obtain its interface (via `moops.interface_of()` or `--help`). Notebooks can
  gate expensive computation with `mo.stop(args.is_interface_query)`.
- `group.multiselect(options, value, ...)` — multi-select UI element that maps
  to repeated CLI options (e.g. `--survive 2 --survive 3`).
- `moops.workarounds.run_in_thread_if_in_async(fn, *args, **kwargs)` — calls
  `fn` directly outside an async context, or in a worker thread when a marimo
  event loop is running (avoiding `asyncio.run()` conflicts). Useful for any
  code that internally uses `asyncio.run()` and needs to work from notebook cells.

### Changed

- Removed `moops.testing.notebook_interface(module)`; use
  `moops.interface_of(module)` instead.

### Fixed

- All `Group` methods match `mo.ui` function's parameter order and default values.
- `moops.run()` now works when called from within a running async event loop
  (e.g. a marimo notebook cell). Previously it raised
  `RuntimeError: asyncio.run() cannot be called from a running event loop`.
- `moops.Passthrough` no longer crashes with `KeyError` when the source embed
  has not yet produced a `result` (e.g. a file-picker with nothing selected on
  first load). The `result` key is now only forwarded when it is present.

## [0.4.0] - 2026-05-21 - Fixes

### Fixed

- `moops.embed.App` wrapping and cloning a marimo app confused marimo's internal
  state tracking. The wrapper is removed: use `moops.embed(app, defs=...)` directly
  instead of `moops.embed.App(app).clone()`. `moops.embed.Passthrough` is now
  `moops.Passthrough`.

## [0.3.3] - 2026-05-20 - Multi-embed script fix

### Fixed

- Fixed a crash when running a notebook as a CLI script that embeds more than
  one notebook via `moops.embed.App` and passes all child interfaces to
  `args.interface()`.

## [0.3.2] - 2026-05-19 - Run buttons

### Added

- `moops.run_button()` (also available as `group.run_button()`) creates a
  `mo.ui.run_button` in notebooks and returns a stub with `.value = True` in
  CLI context, so `mo.stop(not btn.value)` gates notebook execution while
  always running in scripts.
- `group.subgroup()` now warns when called from an async marimo cell, as each
  re-run creates a new `Group` object and causes the embedded notebook to reload
  and lose widget state. Move `subgroup()` to a separate sync cell instead.

### Fixed

- Dict-options dropdowns now correctly reflect the selected key in URL query
  parameters instead of the string representation of the mapped value.

## [0.3.1] - 2026-05-18 - Nested embed helpers

### Added

- `moops.embed.Passthrough`, a utility for reusing the result of one embedded
  notebook as input to another.
- `moops.embed.App`, a wrapper for nested marimo embeds that retains only the
  embedded notebook's `result` definition in script mode and works around
  marimo script-mode nested embed failures.

## [0.3.0] - 2026-05-13 - Embeds' markdown heading demotion

### Added

- Markdown headings emitted by subgroups are demoted by one level by default,
  with `markdown_heading_offset` available to customize the offset.
- `group.file_browser(multiple=True)` now maps to repeated CLI options, e.g.
  `--file a.txt --file b.txt`.

### Changed

- `Presets` now infers its JSON filename from the calling notebook or script by
  default. Pass `filename=` to customize where presets are stored.

### Fixed

- Renaming a label-derived option in a notebook no longer leaves the old option
  reported as missing while marimo still retains the previous control object.

## [0.2.0] - 2026-05-12 - Browser query-string support

### Added

- `group.file_browser()`: file browser UI in notebooks, maps to a CLI path option.
- `--interactive` flag: when passed, prompts for any control not specified on
  the command line, so scripts can be driven interactively without a notebook.
- Marimo browser notebooks now initialize `Group()` controls from URL query
  parameters and keep later control changes reflected in the URL.
- Embedded notebooks now include an "Open in new tab" link that carries their
  current parameters into the standalone notebook.
- Notebook presets named `default` now initialize controls when no explicit
  preset or query parameter is selected.
- `group.custom()`: use a custom notebook control with an existing moops
  control as the CLI fallback.

### Fixed

- Missing option warnings now include omitted subgroup interfaces.

## [0.1.1] - 2026-05-09 - Tooltips

### Added

- More Marimo UI elements support: `group.checkbox()` and `group.range_slider()`
- Label tooltips now show the corresponding CLI option name

### Changed

- `Presets` redesigned. It now takes
  `(filename, get_selected_preset, set_selected_preset)` so that reactivity is
  driven by `mo.state`. Update usage to:

  ```python
  get_preset, set_preset = mo.state(None)
  presets = moops.Presets("notebook_presets.json", get_preset, set_preset)
  ```

### Fixed

- Composite child controls no longer lose moops metadata after marimo clones them
- Preset save button now correctly persists the preset
- Preset dropdown now updates immediately after a preset is saved

## [0.1.0] - 2026-05-05 - Initial release

Initial release.
