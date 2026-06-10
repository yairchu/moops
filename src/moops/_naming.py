import dataclasses
import html
import re

_PARENTHETICAL_SUFFIX = re.compile(r"^(?P<label>.+?)\s*\((?P<metavar>[^()]+)\)$")


def option_to_label(option: str) -> str:
    """Convert a CLI option like ``--max-count`` to a display label ``max count``."""
    return option.lstrip("-").replace("-", " ")


@dataclasses.dataclass
class OptionLabel:
    """Maps between UI labels and CLI option names."""

    label: str
    option: str
    metavar_label: str | None = None

    @staticmethod
    def make(
        label: str | None, option: str | None, prefix: str | None = None
    ) -> "OptionLabel":
        """Generate OptionLabel from label or option name."""

        metavar_label = None
        if option is None:
            if label is None:
                raise ValueError("Either label or option must be provided")
            option_label, metavar_label = split_label_metavar(label)
            option = f"--{prefix or ''}{option_label.lower().replace(' ', '-')}"
        else:
            if not option.startswith("-"):
                raise ValueError(f"Option must start with dash: {option}")
            if prefix is not None and not option.startswith(f"--{prefix}"):
                raise ValueError(f"Option {option} must start with --{prefix}")
            if label is None:
                label = option_to_label(option)
        return OptionLabel(label=label, option=option, metavar_label=metavar_label)

    @property
    def metavar(self) -> str:
        label = self.metavar_label or self.label
        return label.upper().replace(" ", "_")

    def label_with_tooltip(self, help_text: str) -> str:
        return (
            f'<span title="{html.escape(help_text, quote=True)} ({self.option})">'
            f"{self.label}</span>"
        )


def split_label_metavar(label: str) -> tuple[str, str | None]:
    match = _PARENTHETICAL_SUFFIX.match(label)
    if match is None:
        return label, None
    return match.group("label"), match.group("metavar")
