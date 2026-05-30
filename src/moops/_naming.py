import dataclasses
import html


def option_to_label(option: str) -> str:
    """Convert a CLI option like ``--max-count`` to a display label ``max count``."""
    return option.lstrip("-").replace("-", " ")


@dataclasses.dataclass
class OptionLabel:
    """Maps between UI labels and CLI option names."""

    label: str
    option: str

    @staticmethod
    def make(
        label: str | None, option: str | None, prefix: str | None = None
    ) -> "OptionLabel":
        """Generate OptionLabel from label or option name."""

        if option is None:
            assert label is not None, "Either label or option must be provided"
            option = f"--{prefix or ''}{label.lower().replace(' ', '-')}"
        else:
            assert option.startswith("-"), f"Option must start with dash: {option}"
            assert prefix is None or option.startswith(f"--{prefix}"), (
                f"Option {option} must start with --{prefix}"
            )
            if label is None:
                label = option_to_label(option)
        return OptionLabel(label=label, option=option)

    @property
    def metavar(self) -> str:
        return self.label.upper().replace(" ", "_")

    def label_with_tooltip(self, help_text: str) -> str:
        return (
            f'<span title="{html.escape(help_text, quote=True)} ({self.option})">'
            f"{self.label}</span>"
        )
