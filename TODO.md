# TODO

Bugs found reviewing the unreleased "hide inactive variant branches from
`--help`" feature (`src/moops/_list_options.py`, `src/moops/group.py`,
`src/moops/interface.py`), not yet fixed:

- `src/moops/_list_options.py:353` — `active_variant_keys_from_args`
  re-implements `SubgroupListControl.parse`'s segmentation and per-leaf
  parsing as a second, independent pass used only for `--help` rendering,
  instead of reusing it. Risks `--help`'s active-branch detection drifting
  from what CLI parsing actually accepts.
