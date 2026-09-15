---
name: migrate-marimo-to-moops
description: Migrate existing marimo notebooks to use moops so the same notebook controls also work as CLI arguments, Python-callable inputs, and shareable interface metadata. Use when converting mo.ui controls, mo.status calls, or marimo notebooks/scripts to moops.Group, args.interface, moops.run-compatible inputs, or moops CLI workflows in any project.
---

# Migrate marimo notebooks to moops

Use this skill to convert an existing marimo notebook to moops while preserving
the notebook's behavior. Do the smallest migration that gives useful CLI or
programmatic inputs.

## Workflow

1. Inspect the notebook's imports, `mo.ui.*` controls, `mo.status.*` calls,
   `mo.md`/display cells, and existing script-entry behavior.
2. Add `import moops` and create one argument group near the top:

   ```python
   args = moops.Group()
   ```

3. Convert only user-facing inputs that should be configurable outside the
   notebook. Leave internal or purely interactive controls as `mo.ui.*`.
4. Replace eligible controls with `args.*` wrappers and preserve their existing
   defaults, labels, callbacks, and marimo-specific keyword arguments.
5. Add an `interface` cell near the top, preferably immediately after the title
   or imports cell:

   ```python
   interface = args.interface(input_text, style)
   interface
   ```

   It may reference controls defined in later cells; marimo's DAG resolves
   execution order. Keep `interface` as the cell's last expression to display
   the CLI callout and help. This does not display the controls themselves;
   preserve or add separate notebook outputs for them.
6. Replace user-triggered `mo.ui.run_button` controls with
   `interface.run_button`. Keep them in a separate cell downstream of the
   interface so CLI arguments are validated before gated computation begins.
7. Preserve output cells unless moops has a direct reason to own them. Common
   safe replacements are `args.md`, `args.table`, `args.progress_bar`, and
   `args.spinner` when the output should also behave well in CLI runs.
8. If the notebook has many options or users often reuse option sets, consider
   presets:

   ```python
   get_preset, set_preset = mo.state(None)
   ```

   Then in a separate cell:

   ```python
   args = moops.Group(presets=moops.Presets(get_preset, set_preset))
   ```

   Keep plain `moops.Group()` for small notebooks or one-off scripts.
9. Validate with the project's existing commands. Prefer the project's package
   manager and checks. If no checks are obvious, run the migrated notebook with
   marimo or execute the notebook file as a script.

## Control Mapping

Use the closest `Group` method:

- `mo.ui.text` -> `args.text`
- `mo.ui.text_area` -> `args.text_area`
- `mo.ui.number` -> `args.number`
- `mo.ui.slider` -> `args.slider`
- `mo.ui.range_slider` -> `args.range_slider`
- `mo.ui.switch` -> `args.switch`
- `mo.ui.checkbox` -> `args.checkbox`
- `mo.ui.dropdown` -> `args.dropdown`
- `mo.ui.multiselect` -> `args.multiselect`
- `mo.ui.matrix` -> `args.matrix`, or `args.matrix_display` when the
  original is `disabled=True` and only shows a computed result
- `mo.ui.file` -> `args.file`
- `mo.ui.file_browser` -> `args.file_browser`
- `mo.ui.run_button` -> `interface.run_button`
- `mo.ui.table` -> `args.table` only when CLI table output is useful
- `mo.status.progress_bar` -> `args.progress_bar`
- `mo.status.spinner` -> `args.spinner`

Pass through marimo-specific keyword arguments with `**kwargs` instead of
recreating moops wrappers.

## Migration Rules

- Keep existing names when possible; downstream cells may depend on them.
- Keep `help_text` useful because it becomes CLI help.
- Use `option=` only when the inferred CLI flag would be unclear or unstable.
- Pass every converted input control to `args.interface(...)`.
- For `args.subgroup(...)` or `args.variant(...)`, pass subgroup interfaces to
  the parent interface instead of flattening controls by hand.
- Do not add tests unless the migration exposes a real bug or surprising
  behavior. Use existing examples/checks first.
- Do not rewrite notebook logic, formatting, plotting, or data processing unless
  needed for the migration.

## Register and Display Input Controls

Every converted input control has two independent requirements:

1. Pass it to `args.interface(...)` so it is available as a CLI argument and in
   CLI help.
2. Display it in the notebook as a cell's last expression or nested in a
   displayed object such as `mo.vstack`, markdown interpolation, or
   `mo.accordion`.

`args.interface(...)` registers controls with moops but does not display them as
interactive notebook controls. A control that is registered but never displayed
is inert in the notebook, so its `.value` stays at its default.

- Assign an element to a global variable and read `.value` in a different cell;
  the defining cell does not observe its own updates.
- Wrap elements created dynamically in loops or comprehensions in `mo.ui.array`
  or `mo.ui.dictionary` so marimo can track them reactively.
- Preserve the notebook's existing control display when replacing `mo.ui.*`
  constructors with `args.*` wrappers; passing the controls to the interface is
  additional, not a replacement for displaying them.

## Validation

Run the smallest checks that prove the migrated notebook still works:

- Existing project checks, if documented.
- `marimo check` on the notebook or notebook directory, if available.
- The notebook as a script with default arguments.
- One representative CLI invocation with non-default arguments.
- Any existing tests that import or execute the notebook.

If a project uses `uv`, prefer `uv run ...`. Otherwise use the project's
existing toolchain; do not introduce one just for the migration.
