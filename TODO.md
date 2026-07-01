# TODO

Bugs found reviewing the unreleased "hide inactive variant branches from
`--help`" feature (`src/moops/_list_options.py`, `src/moops/group.py`,
`src/moops/interface.py`), not yet fixed:

- `src/moops/group.py:1016` — `SubgroupListControl.active_variant_keys` is
  computed once from the process's `sys.argv`-derived CLI args at
  Group-build time and never recomputed, so it goes permanently stale once
  a marimo command-box edit changes which variant branch a list item uses.

- `src/moops/group.py:1016` — `active_variant_keys_from_args` only looks at
  raw CLI args, so a list whose initial items come entirely from a
  `value=[...]` default (no matching CLI tokens) always falls back to the
  selector's global default branch in `--help`, hiding the branch the
  configured default items actually use.

- `src/moops/_list_options.py:353` — `active_variant_keys_from_args`
  re-implements `SubgroupListControl.parse`'s segmentation and per-leaf
  parsing as a second, independent pass used only for `--help` rendering,
  instead of reusing it, and silently drops `ParseError` results. Risks
  `--help`'s active-branch detection drifting from what CLI parsing
  actually accepts.
