# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
