# Changelog

<!-- markdownlint-disable MD024 -->

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed

- `Presets` now infers its JSON filename from the calling notebook or script by
  default. Pass `filename=` to customize where presets are stored.
- Markdown headings emitted by subgroups are demoted by one level by default,
  with `markdown_heading_offset` available to customize the offset.

## [0.2.0] - 2026-05-12

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

## [0.1.1] - 2026-05-09

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

## [0.1.0] - 2026-05-05

Initial release.
