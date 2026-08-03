# Changelog

<!-- markdownlint-disable MD024 -->

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed

- Add `Interface.run_button()` so CLI arguments are fully validated before
  cells gated by the button can begin expensive computation. Remove the
  misleading `Group.run_button()` alias; `moops.run_button()` remains available
  for gates that deliberately do not depend on an interface.

## [0.15.2] - 2026-08-03 - Notebook CLI disclosure

### Changed

- Collapse the notebook CLI callout behind a compact `Notebook CLI info`
  disclosure, while automatically expanding warnings and errors.

### Fixed

- Shrinking a dynamically generated set of controls no longer reports stale
  controls that are awaiting cyclic garbage collection.

## [0.15.1] - 2026-07-27 - Lazy control folds

### Changed

- Add `moops.ui.fold()`, a compact disclosure that shows a control’s label and
  value while collapsed and lazily renders the control when expanded.
- When `Group.file_browser()` has a default selection but no explicit
  `initial_path`, it now opens at the common parent of the selected paths.
- Depend on `marimo-base` instead of the full `marimo` package, reducing the
  dependency footprint for CLI-only installations.

## [0.15.0] - 2026-07-26 - Native file browser selections

### Changed

- `Group.file_browser()` now uses marimo's native `value` parameter for initial
  selections; `initial_path` once again controls only the initially displayed
  directory.

## [0.14.4] - 2026-07-22 - Custom control CLI resets

### Fixed

- Editing the notebook CLI box now resets custom controls through their fallback
  controls instead of assigning to their read-only derived values.

## [0.14.3] - 2026-07-21 - Rich terminal Markdown

### Changed

- `Group.md()` now renders Markdown styling with Rich when CLI output is attached
  to a terminal, while redirected and captured output remains unchanged.

## [0.14.2] - 2026-07-20 - cmux terminal graphics

### Fixed

- Kitty graphics detection now recognizes Ghostty-compatible terminals such as
  cmux when they identify themselves with `TERM_PROGRAM=ghostty` and a generic
  `TERM=xterm-256color`.

## [0.14.1] - 2026-07-16 - Short variant options and notebook assertions

### Added

- `Group.variant(..., short_options=True)` can omit the variant group name from
  branch CLI options, including when mirrored into `Group.list`. Shortened
  options that would collide are rejected.
- `Group.assertions()` preserves normal Python assertions on the CLI and turns
  assertion failures, including those raised by called code, into visible
  notebook danger callouts that stop the current cell and its descendants.

## [0.14.0] - 2026-07-15 - Unambiguous mirrored list options

### Changed

- **Breaking:** Mirrored `Group.list` item options now retain their structural
  prefix (for example, `--trip --trip-mode train`) so multiple lists and nested variant
  structures can reuse child option names without CLI ambiguity. Existing
  commands and presets using unprefixed item options must be updated.

### Fixed

- Lists of variant controls now preserve active-branch options in generated CLI
  commands and saved presets when the selector dropdown maps keys to values.

## [0.13.12] - 2026-07-14 - Preset edit preservation

### Changed

- Controls now reject the `disabled` option with a clear error because moops
  manages disabled state for overrides and inactive variants.

### Fixed

- Variant controls now retain edits when switching branches under an active
  preset instead of reverting to the saved preset value.

## [0.13.11] - 2026-07-07 - Mirrored list control rows

### Changed

- `Group.list(..., controls_from(...))` notebook items now render their item
  controls in a single wrapping row, including nested variant controls.

## [0.13.10] - 2026-07-06 - Numeric CLI formatting

### Changed

- CLI and query formatting for numeric controls now omits redundant `.0` suffixes.

## [0.13.9] - 2026-07-02 - Bound interface queries

### Added

- `moops.interface_of(module, args=..., defs=...)` can now inspect a child
  notebook against a bound group with extra definition overrides, so parent
  `--help` output can declare options from result-gated embeds early.
- Added a composition example demonstrating early interface declaration for a
  result-gated child embed.

## [0.13.8] - 2026-07-01 - Variant help visibility

### Changed

- `--help` output now shows only the active (selected or default) variant branch
  options, hiding inactive branches that would otherwise add noise.
- List `--help` output groups variant item options under labelled sections (e.g.
  `Options for --mode car (default) (per item):`) and shows only the sections
  relevant to modes mentioned in the command line, defaulting to the default
  mode when no items are specified.

### Fixed

- Editable notebook CLI commands now accept newline-separated arguments without
  shell continuation backslashes, and tolerate a final trailing continuation
  backslash while still formatting commands with real shell continuations.

## [0.13.7] - 2026-06-29 - Dropdown default validation

### Fixed

- Dropdown controls now reject defaults that are not one of their options before
  notebook widget construction.
- `controls_from` list items now omit redundant default dropdown options when
  the dropdown uses distinct option keys and display values.

## [0.13.6] - 2026-06-23 - Bounded control validation

### Fixed

- Out-of-range saved/query values for bounded number and slider controls now
  fall back to the code default and report a moops validation warning instead
  of raising from marimo widget construction.

## [0.13.5] - 2026-06-22 - Dataclass controls

### Added

- `Group.dataclass()` can now generate controls and CLI options for defaulted
  dataclass fields.

## [0.13.4] - 2026-06-17 - Status output

### Added

- `Group.progress_bar()` and `Group.spinner()` now mirror marimo status
  displays in notebooks, use `tqdm` on the CLI when installed with
  `moops[status]`, and otherwise fall back to plain status lines.
- List controls in notebooks now include a per-item duplicate button.

## [0.13.3] - 2026-06-17

### Fixed

- `file_browser` controls mirrored into `Group.list(..., controls_from(...))`
  items now round-trip notebook file selections when list items are rebuilt.
- Wrapped script callouts that use `uv run` now keep `uv run <script>` together
  on the first line instead of wrapping after just `uv`.

## [0.13.2] - 2026-06-16

### Fixed

- `controls_from` now preserves a control's explicit label instead of deriving
  the mirrored label from the option name (e.g. a `--count` control labelled
  "Maximum item count" kept showing "count" when mirrored).
- Standalone URLs now round-trip controls inside a subgroup. The URL keyed such
  a control by its flat leaf option, but the subgroup reads it back under its
  dotted path (e.g. `sub.mode`), so opening the URL silently dropped subgroup
  values; only top-level controls survived.
- Standalone URLs now round-trip `controls_from` mirrors, whose query params
  must use the mirrored subgroup's dotted path (e.g. `step.style`) rather than
  the flat CLI-derived key.

## [0.13.1] - 2026-06-16

### Fixed

- Notebook CLI command blocks now include `uv run` when rendered from a
  `uv run marimo ...` session and the target notebook file is not executable.
- Switch and checkbox controls now work as `variant()` selectors in the
  `controls_from` mirroring path (e.g. pipeline step controls). Resolving the
  active branch read the selector's `.value`, tripping marimo's "value accessed
  in its creating cell" guard on the freshly-cloned widget; dropdowns were
  unaffected because they expose `_selected_key`. `selected_key()` now falls
  back to the raw cached `_value`.

## [0.13.0] - 2026-06-15 - CLI table output

### Added

- `Group.table()` now works on the CLI: it prints the table using
  `pandas.to_markdown()` when pandas is available, with a plain `print(data)`
  fallback otherwise.

### Fixed

- `missing_options_msg` is no longer silently dropped when the interface has
  no active controls.
- The usage disclosure in the CLI callout is now collapsible only for longer
  help text; short usage (≤ 3 lines) is shown inline instead.
- The `Usage:` block is no longer emitted for empty interfaces (no controls).

## [0.12.2] - 2026-06-15

### Changed

- Hypothesis is now an optional dependency instead of a hard runtime
  requirement. It is only needed for `Interface.strategy()` (property-based
  testing); install it with `pip install moops[test]` or `pip install
  hypothesis`. Importing `moops` and all non-`strategy()` functionality no
  longer pulls in Hypothesis.

### Fixed

- Clearing a `Group.list` to empty while a preset is active now persists the
  empty list in query parameters, instead of dropping the parameter and letting
  the preset restore the old items on rerender.
- `Group.list` items whose values are not JSON-serializable (e.g. a dropdown
  mapped to a class) no longer drop the whole list's query parameter. Each item
  is now serialized per leaf via that leaf's own query form (a dropdown's key,
  etc.), keeping the item structure, so it round-trips for both serializable and
  mapped values. Previously the dropped query param let an active preset
  override edits on every rerender, so editing any control reverted it.

## [0.12.1] - 2026-06-12

### Added

- An embedded notebook's interface summary now also shows a CLI command that
  reproduces the embed's current setup standalone, when `args` is the only
  definition overridden via `moops.embed` (injecting other defs suppresses the
  command, since the CLI cannot reproduce them).

### Changed

- Script-mode embeds now expose the embedded notebook's rendered cell outputs
  on the returned object's `output`, matching notebook-mode embeds, instead of
  always returning `None`.

### Fixed

- `Group.graphics_supported` switches matplotlib off GUI backends when
  returning `True` on the CLI, fixing a crash on macOS when an app that plots
  runs in a worker thread, e.g. when embedded by another notebook (GUI
  backends only allow figure creation on the main thread, and CLI figures are
  only ever rasterized).

## [0.12.0] - 2026-06-11

### Added

- `moops.embed` accepts a `keep=` sequence of definition names to retain in
  lean script-mode embeds, alongside the always-kept `result`.

### Changed

- CLI command block in notebook shows full command path
- Wrapped CLI command blocks now use two-space continuation indentation.

### Fixed

- `moops.embed(..., keep=...)` and `moops.Passthrough(..., keep=...)` now reject
  a bare string instead of treating it as a sequence of single-character names.

## [0.11.5] - 2026-06-10

### Fixed

- `Group.md` now demotes headings in indented triple-quoted markdown strings,
  matching converted `mo.md(...)` calls whose markdown content stays indented in
  the Python source.
- `Group.md` CLI output now strips language-tagged fenced code blocks and no
  longer mangles separate inline code spans that happen to start and end with
  backticks, nor text containing multiple separate fenced blocks.
- Interactive multiselect prompts now reject invalid entries immediately and
  re-prompt instead of falling through to parse errors that leave defaults
  unchanged.
- Interactive multiselect prompts now accept numbered replies such as `1,3`,
  matching the numbered menu they display.
- Interactive prompts now preserve the default value instead of crashing when
  stdin reaches EOF after an invalid reply.
- Split CLI values such as `--count -.5` now parse as negative decimals,
  matching the already-supported `--count=-.5` form.
- Split CLI range values such as `--range -5,10` now parse correctly, and
  generated range-slider commands with negative values now round-trip.
- Errors for options missing their value now suggest the `--option=value` form
  when the next argument starts with a dash, such as `--tag -dev`.
- Missing-value hints now shell-quote dash-leading multi-word values, such as
  `--tag='-d ev'`.
- File browser CLI fallbacks now display repeated default paths in their
  original order instead of rendering them through an unordered, deduplicating
  set.
- Invalid control definitions now raise `ValueError` consistently, including
  under optimized Python, instead of relying on `assert`.
- Script callouts and editable commands now derive command names with platform
  path rules instead of always splitting on `/`.

## [0.11.4] - 2026-06-09

### Fixed

- `controls_from` mirrors with nested variants now hide the inactive nested
  branch in notebook display. Previously only the top-level variant was
  variant-aware; a variant branch that was itself a mirrored subgroup
  containing another variant showed all of its inner branches at once.
- Editing a nested variant selector inside a `Group.list` item now updates the
  item's live value immediately. Previously the list change callback received
  the new selector value, but the mirrored item's cached value could still hold
  the previous branch until the next notebook rerun.
- Deleting or reordering a `Group.list` item no longer leaks an edited item's
  value onto the item that takes its position. Per-item mirrored controls used
  to sync to query params keyed by list index, so a value edited in one item
  reappeared on whichever item later occupied that index. List items no longer
  write per-index query params; the list as a whole still round-trips through
  its own query param.

## [0.11.3] - 2026-06-09

### Fixed

- A `Passthrough` injected as an embed override now works when the embedding
  notebook calls `moops.embed(override, ...)` (rather than `override.embed(...)`)
  in script mode. That path runs the override via `.run()`, which `Passthrough`
  did not implement, so it raised `AttributeError`. `Passthrough` now satisfies
  the full embed-app interface.

## [0.11.2] - 2026-06-08

### Fixed

- `Passthrough` instances forwarding the same result now compare equal (and
  hash equal). marimo's embed-output cache compares the overrides it was
  handed, so a cell that rebuilt `Passthrough(input_result)` on every re-run
  used to miss the cache and reset the embedded notebook's UI (e.g. dropdowns)
  on each interaction; the inline pattern is now cache-stable.

## [0.11.1] - 2026-06-04

### Fixed

- `Group.controls_from` mirrors keep their stacked, variant-aware display when
  embedded inside composite controls such as `Group.list`, while remaining
  reactive `UIElement`s.

## [0.11.0] - 2026-06-04 - Kitty Terminal graphics protocol support

### Added

- `moops.run` accepts `output_mode=` to control where a child notebook's
  dual-output goes. It defaults to `OutputMode.STDOUT` (unchanged behavior);
  pass `None` to silence the child, e.g. when looping and only the final
  iteration should be displayed. The Game of Life example uses this with a
  "Show intermediate steps" switch.

- `Group.figure` displays a figure both in notebooks and on the CLI: a
  matplotlib `Figure`/`Axes`, PIL `Image`, or raw PNG `bytes` is rendered by
  marimo in notebooks and streamed inline to the terminal via the Kitty
  graphics protocol (kitty, Ghostty, WezTerm, Konsole) on the CLI. The
  `Group.graphics_supported` property reports whether inline images will
  render, so notebooks can gate plotting or fall back to text/ASCII. The Game
  of Life example uses it to show the board as an image when supported and the
  ASCII grid otherwise.

### Fixed

- Editing a control created with `Group.controls_from` now reactively reruns
  dependent cells. The mirrored controls were returned as a non-`UIElement`
  wrapper, which marimo's reactivity could not bind to, so changes did not
  propagate until another control triggered a rerun.
- Overridden dropdown controls now accept non-string option values, such as
  classes, while rendering the locked read-only dropdown.

## [0.10.0] - 2026-06-03 - Editable commands and option naming

### Added

- In preset-enabled notebooks the command line in the script callout is now
  editable. Edit it in place (or paste a different command) and commit to
  initialize all controls from those arguments. Malformed input — unbalanced
  quotes, unknown options, or values of the wrong type — is reported inline and
  leaves the controls unchanged.

### Changed

- The notebook UI for `Group.list` now renders per-item controls: move an item
  up or down to reorder, remove any individual item, and insert a new item
  above any item, plus a trailing "+ Append" button to add at the end.
  Previously the only controls were a single "+ Add" (append) and "- Remove"
  (remove last). Structural edits read the current item values, so in-progress
  edits to other items are preserved across reorder, insert, and remove.

### Fixed

- Dropdown CLI values now normalize display labels with spaces, so labels like
  `Word Count` use arguments such as `--notebook word-count` and variant branch
  options such as `--notebook-word-count-*`. Invalid inactive-branch arguments
  fail validation without emitting embedded child output first.
- Labels with parenthetical units now use the base label for the option name and
  the unit for the metavar; for example `Length (seconds)` becomes
  `--length SECONDS` instead of `--length-(seconds) LENGTH_(SECONDS)`.

## [0.9.0] - 2026-06-01 - List controls and notebook polish

### Added

- `Group.number(..., allow_none=False)` disables `None` as a CLI value for
  unbounded number inputs while preserving marimo's editable number widget.

- `OutputMode` enum and a settable `Group.output_mode` property control where a
  notebook's dual-output (e.g. `Group.md`) goes: marimo display objects
  (`NOTEBOOK`), printed text (`STDOUT`), or nothing (`None`). It defaults from
  context (notebook vs CLI). A parent running a child via `app.run` can set
  `args.output_mode = OutputMode.NOTEBOOK` so the child renders its output, then
  collect it from `app.run`'s returned definitions — see
  `examples/composition/run_outputs.py`.

### Changed

- The "This notebook also works as a script" callout now wraps long commands
  onto multiple lines using shell `\` continuations (one option per line)
  instead of overflowing horizontally, keeping the command copy-pasteable.

### Fixed

- `Group.list()` notebook add/remove buttons now interact correctly with
  presets: "Clear changes" resets list state, and active saved default presets
  no longer snap edited lists back to the preset value on each rerender.
- Mirrored `Group.list()` notebook items now stay editable while a preset is
  active instead of snapping back to the preset item list on each rerender.
- Merged `Group.list()` script-callout arguments now round-trip when a default
  item value starts with `-`.

## [0.8.0] - 2026-06-01 - Repeated-option list controls

### Added

- `Group.list()` creates a control for repeated CLI options (e.g. `--factor 2
  --factor 5`) with a matching add/remove UI in notebooks. Supports both merged
  mode (anchor option == item option) and non-merged mode (bare anchor option
  separates items).

### Changed

- **Breaking:** `Group.custom()` now takes `custom(fallback, build, *,
  value=None)` where `build(value)` is a factory that constructs the notebook
  component from the fallback's resolved value, replacing the previous
  `custom(control, fallback, *, value=...)` that took a pre-built control. The
  factory is what lets `controls_from` recreate the component. `value` now
  receives `(component, fallback)` so it can read the fallback supplied in the
  current context (e.g. after mirroring).
- Custom controls are now recreated when mirroring a child notebook, rebuilding
  the notebook component in the parent instead of falling back to the bare
  fallback control.
- Mirrored controls now hide inactive variant branches in notebook UI while
  keeping every branch registered so values still pass through and CLI help
  lists all branches. As with native `group.variant`, options belonging to an
  inactive branch are rejected on the CLI.

### Fixed

- CLI help no longer advertises `[--interactive]` in the usage line when the
  notebook has no controls, since there is nothing to prompt for in that case.
- An unbounded `number()` (no `start`/`stop`) can be cleared to `None` in a
  notebook; with a non-`None` default that state now round-trips through the
  CLI and query params via a `--no-<option>` flag (mirroring `dropdown`'s none
  handling) instead of serializing to an invalid `--option None`. Bounded
  numbers and sliders coerce `None` to their start, so they are unaffected.
- `number()` and `slider()` now preserve integers larger than 2^53 instead of
  silently rounding them. Integer-looking values were parsed through `float()`,
  so e.g. `--count 9007199254740993` resolved to `9007199254740992` on the CLI
  and via query params; they are now parsed as exact integers first.

## [0.7.2] - 2026-05-28 - CLI help formatting

### Fixed

- Standalone CLI options that follow variant group sections in help output are
  now separated by a blank line, so they are no longer visually grouped with
  the last variant branch.
- The `Usage:` line in CLI help now wraps at 88 columns when many options are
  present, with continuation lines aligned under the first option.
- Individual option help lines in CLI output now wrap at 88 columns; when an
  option declaration plus its help text would exceed 88 columns, the help text
  moves to the next line with a fixed indent.

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

- `moops.run_button()` creates a
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
