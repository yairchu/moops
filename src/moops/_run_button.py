import typing

import marimo as mo
from marimo._messaging.mimetypes import KnownMimeType


class RunButton(typing.Protocol):
    """A notebook run button or its always-active CLI counterpart."""

    @property
    def value(self) -> bool: ...


class _RunButtonStub:
    """A hidden run-button value used outside interactive notebooks."""

    def __init__(self, value: bool = True) -> None:
        self.value = value

    def _mime_(self) -> tuple[KnownMimeType, str]:
        # Hide run buttons in embedded notebooks output
        # to reflect that there is no run barrier.
        return ("text/plain", "")


def run_button_stub(value: bool) -> RunButton:
    """Create a hidden run-button value for non-interactive execution."""
    return _RunButtonStub(value=value)


def run_button(**kwargs: typing.Any) -> RunButton:
    """Create a run button that gates notebook execution.

    In CLI context, always returns a stub with .value = True so code that
    checks `mo.stop(not btn.value)` runs unconditionally.
    """
    if mo.running_in_notebook():
        return mo.ui.run_button(**kwargs)
    return _RunButtonStub()
