import typing

import marimo as mo
from marimo._messaging.mimetypes import KnownMimeType


class RunButton(typing.Protocol):
    """A notebook run button or its always-active CLI counterpart."""

    @property
    def value(self) -> bool: ...


class _RunButtonStub:
    """Returned by run_button() outside notebooks; always considered clicked."""

    value: bool = True

    def _mime_(self) -> tuple[KnownMimeType, str]:
        # Hide run buttons in embedded notebooks output
        # to reflect that there is no run barrier.
        return ("text/plain", "")


def run_button(**kwargs: typing.Any) -> RunButton:
    """Create a run button that gates notebook execution.

    In CLI context, always returns a stub with .value = True so code that
    checks `mo.stop(not btn.value)` runs unconditionally.
    """
    if mo.running_in_notebook():
        return mo.ui.run_button(**kwargs)
    return _RunButtonStub()
