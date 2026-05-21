"""Workarounds for marimo UI elements that lack `disabled` support."""


class LockedMultiselect:
    """Read-only multiselect placeholder used when a control is overridden.

    Workaround for mo.ui.multiselect not supporting disabled=True.
    See https://github.com/marimo-team/marimo/issues/9579
    """

    def __init__(self, value: list[str], label_html: str) -> None:
        self.value = value
        _chips = "".join(
            f'<span style="background:var(--sky-2,#dbeafe);border-radius:4px;'
            f'padding:2px 8px;margin:2px;display:inline-block">{v}</span>'
            for v in value
        )
        self._html = (
            f'<div style="padding:4px 0;opacity:0.7">'
            f"{label_html}: {_chips or '(none)'}"
            f"</div>"
        )

    def _mime_(self) -> tuple[str, str]:
        return ("text/html", self._html)
