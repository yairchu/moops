import collections.abc as abc
import dataclasses
import marimo as mo
import sys

help_flags = ["--help", "-h"]


class Group:
    """Unified CLI argument parser and marimo UI element generator."""

    def __init__(self, cli_args: list[str] | None = None) -> None:
        """Initialize with command line arguments (defaults to sys.argv)."""

        if cli_args is None:
            cli_args = sys.argv
        [self.command, *args] = cli_args
        if not self.command:
            self.command = "script"

        self._parse_args(args)
        self.is_help = any(x in self.parsed_args for x in help_flags)
        self.flags = {}
        self.str_options = {}

    def _parse_args(self, args: list[str]) -> None:
        """Parse command line arguments into flags and options."""

        self.parsed_args = {}
        self.unexpected_args = []
        prev = None
        for arg in args:
            if arg.startswith("-"):
                if "=" in arg:
                    prefix, value = arg.split("=", 1)
                    self.parsed_args[prefix] = value
                    prev = None
                else:
                    self.parsed_args[arg] = None
            elif prev is not None and prev.startswith("-"):
                self.parsed_args[prev] = arg
            else:
                self.unexpected_args.append(arg)
            prev = arg

    def help(self) -> mo.Html | None:
        """
        group.help() serves two purposes:
        * Display help text based on the defined flags and options.
        * Verify the arguments passed to the script.
        """

        show_help = self.is_help
        if not mo.running_in_notebook():
            issues = list(self._validate_args())
            if issues:
                print("Argument errors:\n" + "\n".join(f"- {x}" for x in issues))
                print()
                show_help = True

        segments = [
            f"Usage: {self.command} {' '.join(f'[{x}]' for x in [*self.flags.keys(), '-h/--help'])}"
        ]
        opts_help = [f"  {k}: {v}" for k, v in self.flags.items()]
        for k, v in self.str_options.items():
            opts_help.append(
                f"  {k} {v.metavar}: {v.help_text}{f' (default: {v.default})' if v.default else ''}"
            )
        if opts_help:
            segments.append("\n".join(opts_help))
        help_text = "\n\n".join(segments)
        if mo.running_in_notebook():
            return mo.md(f"```\n{help_text}\n```")
        elif show_help:
            print(help_text)
            sys.exit(1)

    def _validate_args(self) -> abc.Iterator[str]:
        unexp_text = "Unexpected argument: "
        for x in self.unexpected_args:
            yield f"{unexp_text}{x}"
        for k, v in self.parsed_args.items():
            if k in self.flags:
                if v is not None:
                    yield f"{unexp_text}{v}"
            elif k in self.str_options:
                if v is None:
                    yield f"Option {k} requires a value"
            elif k not in help_flags:
                yield f"{unexp_text}{k}"

    def md(self, text: str) -> mo.Html | None:
        """Display markdown in notebooks or plain text in CLI."""

        if self.is_help:
            return
        if mo.running_in_notebook():
            return mo.md(text)
        text = text.strip()
        if text.startswith("```\n") and text.endswith("\n```"):
            text = text[4:-4]
        elif text.startswith("`") and text.endswith("`"):
            text = text[1:-1]
        print(f"{text}\n")

    def switch(
        self,
        value: bool = False,
        flag: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        **kwargs,
    ) -> mo.ui.switch:
        """Create a switch UI element that maps to a CLI flag."""

        opt = OptionLabel.make(
            label=label, option=flag, prefix="no-" if value else None
        )
        self.flags[opt.option] = help_text
        if opt.option in self.parsed_args:
            value = not value
        return mo.ui.switch(value=value, label=opt.label, **kwargs)

    def text(
        self,
        value: str = "",
        placeholder: str = "",
        option: str | None = None,
        *,
        help_text: str,
        label: str | None = None,
        **kwargs,
    ) -> mo.ui.text:
        """Create a text input UI element that maps to a CLI option."""

        opt = OptionLabel.make(label=label, option=option)
        self.str_options[opt.option] = OptionDesc(
            default=value,
            metavar=placeholder or opt.label.upper().replace(" ", "_"),
            help_text=help_text,
        )
        return mo.ui.text(
            value=self.parsed_args.get(opt.option, ""), label=opt.label, **kwargs
        )


@dataclasses.dataclass
class OptionDesc:
    """Metadata for CLI options with defaults and help text."""

    default: str | None
    metavar: str
    help_text: str | None


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
            assert label is not None
            option = f"--{prefix or ''}{label.lower().replace(' ', '-')}"
        else:
            assert prefix is None
            if label is None:
                label = option.replace("-", " ")
        return OptionLabel(label=label, option=option)
