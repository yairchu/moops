import dataclasses
import typing
from . import interface


@dataclasses.dataclass
class _OptionDesc:
    """Metadata for CLI options with defaults and help text."""

    default: str | None
    metavar: str
    help_text: str
    allowed_values: list[str] | None = None


@dataclasses.dataclass
class _OptionLabel:
    """Maps between UI labels and CLI option names."""

    label: str
    option: str

    @staticmethod
    def make(
        label: str | None, option: str | None, prefix: str | None = None
    ) -> "_OptionLabel":
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
                label = option.lstrip("-").replace("-", " ")
        return _OptionLabel(label=label, option=option)


@dataclasses.dataclass
class _ControlMeta:
    opt: _OptionLabel
    info: str | _OptionDesc
    stdin_flag: str | None = None
    no_flag: str | None = None
    overridden: bool = False


class _ControlRegistry:
    """Resolved set of flags and options built from a group's live controls."""

    def __init__(
        self, controls: tuple[typing.Any], control_meta: dict[int, _ControlMeta]
    ) -> None:
        self.flags: dict[str, str] = {}
        self.str_options: dict[str, _OptionDesc] = {}
        seen: set[str] = set()
        for ctrl in interface.Interface(controls)._flatten():
            meta = control_meta.get(id(ctrl))
            if meta is None:
                raise ValueError(f"Control {ctrl!r} was not created by this Group")
            if meta.opt.option in seen:
                raise ValueError(
                    f"Option {meta.opt.option!r} passed to render_cli() more than once"
                )
            seen.add(meta.opt.option)
            if meta.overridden:
                continue
            if isinstance(meta.info, str):
                self.flags[meta.opt.option] = meta.info
            else:
                self.str_options[meta.opt.option] = meta.info
            if meta.stdin_flag:
                self.flags[meta.stdin_flag] = f"Read {meta.opt.label} from stdin"
            if meta.no_flag:
                self.flags[meta.no_flag] = f"Set {meta.opt.label} to none"

    def format_help(self, command: str) -> str:
        options = [
            *[f"[{x}]" for x in self.flags],
            *[f"[{k} {v.metavar}]" for k, v in self.str_options.items()],
            "[-h/--help]",
        ]
        segments = [f"Usage: {command.rsplit('/', 1)[-1]} {' '.join(options)}"]
        opts_help = [f"  {k}: {v}" for k, v in self.flags.items()]
        opts_help.extend(
            f"  {k} {v.metavar}: {v.help_text}{f' (default: {v.default})' if v.default else ''}"
            for k, v in self.str_options.items()
        )
        if opts_help:
            segments.append("\n".join(opts_help))
        return "\n\n".join(segments)

    def validate(
        self, args: interface._ParsedArgs, validation_errors: dict[str, str]
    ) -> typing.Iterator[str]:
        rendered = self.flags | self.str_options
        yield from (v for k, v in validation_errors.items() if k in rendered)
        unexp_text = "Unexpected argument: "
        for x in args.unexpected:
            yield f"{unexp_text}{x}"
        for k, v in args.options.items():
            if k in self.flags:
                if v is not None:
                    yield f"{k} does not take a value, but was given: {v}"
            elif k in self.str_options:
                if v is None:
                    yield f"Option {k} requires a value"
            elif k not in interface.help_flags:
                yield f"{unexp_text}{k}"
