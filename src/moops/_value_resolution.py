import dataclasses
import sys
import typing

import marimo as mo

from . import _options, _parse, _query_params

_UNSET: typing.Any = object()


@dataclasses.dataclass
class ValueResolver:
    option_prefix: str
    state: _parse.ParseState
    overrides: dict[str, typing.Any]
    query_params: _query_params.QueryParams
    preset_state: _parse.ParseState | None
    default_preset_state: _parse.ParseState | None

    def override_key(self, option: str) -> str:
        option = option[len(self.option_prefix) :].lstrip("-")
        if option.startswith("no-"):
            option = option[3:]
        return option.replace("-", "_")

    def get_value(
        self,
        control: _options.InputControl,
        default: typing.Any,
    ) -> typing.Any:
        key = self.override_key(control.option)
        if key in self.overrides:
            return self.overrides[key]
        if self.preset_state is not None:
            match control.parse(self.preset_state.args):
                case _options.ParseResult(value=v):
                    self.query_params.sync(control, key, v)
                    return v
                case None:
                    self.query_params.sync(control, key, default)
                    return default
                case _:
                    pass
        raw = self.query_params.get(key)
        if raw is not None:
            match control.parse_query_value(raw):
                case _options.ParseError(message=msg):
                    self.state.validation_errors[control.option] = msg
                case _options.ParseResult(value=v):
                    return v
        match control.parse(self.state.args):
            case _options.ParseError(message=msg):
                self.state.validation_errors[control.option] = msg
            case _options.ParseResult(value=v):
                return v
            case None:
                if self.state.args.is_interactive and not mo.running_in_notebook():
                    prompted_value = self._prompt_interactive(control, default)
                    if prompted_value is not _UNSET:
                        return prompted_value
        if self.default_preset_state is not None:
            match control.parse(self.default_preset_state.args):
                case _options.ParseResult(value=v):
                    self.query_params.sync(control, key, v)
                    return v
                case _:
                    pass
        return default

    def _prompt_interactive(
        self,
        control: _options.InputControl,
        default: typing.Any,
    ) -> typing.Any:
        effective_default = default
        if self.default_preset_state is not None:
            match control.parse(self.default_preset_state.args):
                case _options.ParseResult(value=v):
                    effective_default = v
                case _:
                    pass
        try:
            prompted = control.prompt_interactive(effective_default)
        except KeyboardInterrupt:
            print("\nAborted.")
            sys.exit(1)
        for option, value in prompted.items():
            if isinstance(value, list):
                self.state.args.set_values(option, value)
            else:
                self.state.args.set_value(option, value)
        match control.parse(self.state.args):
            case _options.ParseResult(value=v):
                return v
            case _:
                return _UNSET

    def is_overridden(self, option: str) -> bool:
        return self.override_key(option) in self.overrides

    def query_on_change(
        self,
        control: _options.InputControl,
        on_change: typing.Callable[[typing.Any], None] | None,
    ) -> typing.Callable[[typing.Any], None] | None:
        return self.query_params.on_change(
            control,
            self.override_key(control.option),
            on_change,
            disabled=self.is_overridden(control.option),
        )
