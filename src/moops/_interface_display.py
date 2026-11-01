"""Validate Interface outputs that marimo's script runner does not render."""

from __future__ import annotations

import functools
import typing

from marimo._runtime.app.script_runner import (  # pyright: ignore[reportMissingTypeStubs]
    AppScriptRunner,
)
from marimo._runtime.context import ContextNotInitializedError, get_context

if typing.TYPE_CHECKING:
    from marimo._runtime.runner.result import RunResult
    from marimo._types.ids import CellId_t  # pyright: ignore[reportMissingTypeStubs]

    from .interface import Interface


def validate_display(interface: Interface) -> None:
    """Enforce marimo's creating-cell rule without rendering or reading values.

    UIElementRegistry records the creating cell in both kernel and script
    contexts. Compare contexts too: nested notebooks can reuse cell IDs.
    """
    try:
        ctx = get_context()
    except ContextNotInitializedError:
        return
    execution = ctx.execution_context
    if execution is None or execution.setting_element_value:
        return
    for control in interface._flatten():  # pyright: ignore[reportPrivateUsage]
        if getattr(control, "_ctx", None) is not ctx:
            continue
        if ctx.ui_element_registry.get_cell(control._id) == execution.cell_id:
            raise RuntimeError(
                "Cannot display an Interface in the cell that creates its controls: "
                "display `interface` from a cell other than the one creating "
                "its controls. Move the bare `interface` expression to another cell."
            )


@functools.cache
def install_script_output_validation() -> None:
    """Bridge script output collection to the same check used by _mime_.

    marimo 0.25's script runner has no output-validation hook and never calls
    _mime_. Wrap only its result collector, preserving exception and stop
    handling. Install lazily when an Interface is created, including when
    moops is first imported inside a running notebook cell.
    """
    original = AppScriptRunner._handle_run_result  # pyright: ignore[reportPrivateUsage]

    @functools.wraps(original)
    def handle_run_result(
        self: AppScriptRunner,
        cid: CellId_t,
        result: RunResult,
        outputs: dict[CellId_t, typing.Any],
    ) -> None:
        from .interface import Interface

        if result.exception is None and isinstance(result.output, Interface):
            validate_display(result.output)
        original(self, cid, result, outputs)

    AppScriptRunner._handle_run_result = handle_run_result  # pyright: ignore[reportPrivateUsage]
