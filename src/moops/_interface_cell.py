"""Reject an Interface created in the same cell as any of its controls."""

from __future__ import annotations

import typing

from marimo._runtime.context import ContextNotInitializedError, get_context

if typing.TYPE_CHECKING:
    from .interface import Interface


def validate_creation_cell(interface: Interface) -> None:
    """Require the Interface's cell to differ from its controls' cells.

    marimo never reruns a control's defining cell when the control changes,
    so an Interface created there would keep showing stale values in its CLI
    line. UIElementRegistry records the creating cell in both kernel and
    script contexts. Compare contexts too: nested notebooks can reuse cell IDs.
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
                "Cannot create an Interface in a cell that creates its controls: "
                "marimo does not rerun a control's own cell when the control "
                "changes, so the interface would show stale values. Move the "
                "`args.interface(...)` call to a cell of its own."
            )
