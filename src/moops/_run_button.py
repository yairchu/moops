import typing

import marimo as mo


class _RunButtonStub:
    """Returned by run_button() outside notebooks; always considered clicked."""

    value: bool = True


def run_button(**kwargs: typing.Any) -> mo.ui.run_button | _RunButtonStub:
    """Create a run button that gates notebook execution.

    In CLI context, always returns a stub with .value = True so code that
    checks `mo.stop(not btn.value)` runs unconditionally.
    """
    if mo.running_in_notebook():
        return mo.ui.run_button(**kwargs)
    return _RunButtonStub()
