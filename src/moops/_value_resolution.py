import dataclasses
import sys
import typing
import warnings

import marimo as mo

from . import _list_options, _naming, _options, _parse, _query_params

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
        return _naming.option_to_key(option, self.option_prefix)

    def get_value(
        self,
        control: _options.InputControl,
        default: typing.Any,
    ) -> typing.Any:
        key = self.override_key(control.option)
        if key in self.overrides:
            return self.overrides[key]
        query_value = self._query_value(control, key)
        if self.preset_state is not None:
            changed, changed_value = self.query_params.changed_value(key)
            if changed:
                formatted = control.format_query_value(changed_value)
                if formatted is None or isinstance(
                    control.parse_query_value(formatted), _options.ParseResult
                ):
                    return changed_value
                self.query_params.forget_changed_value(key)
            # Honor live notebook list state over the preset: if the persisted
            # query matches the value the caller passed (so it reflects the
            # current edited state rather than a stale param), keep it. Compare
            # in parsed/canonical form by round-tripping `default` through the
            # same query (de)serialization — a list's live value holds mapped
            # objects (e.g. a dropdown's resolved value) that don't compare
            # equal to the parsed query's key form directly.
            if (
                _is_list_control(control)
                and query_value is not _UNSET
                and query_value == self._normalized_default(control, default)
            ):
                return default
            match control.parse(self.preset_state.args):
                case _options.ParseResult(value=v):
                    self.query_params.sync(control, key, v)
                    return v
                case None:
                    self.query_params.sync(control, key, default)
                    return default
                case _:
                    pass
        if query_value is not _UNSET:
            return query_value
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

    def _normalized_default(
        self,
        control: _options.InputControl,
        default: typing.Any,
    ) -> typing.Any:
        """``default`` round-tripped through the control's query (de)serialization.

        Returns it in the same parsed form a query value takes, so the two can
        be compared directly. Returns ``_UNSET`` (which never equals a real
        query value) when ``default`` cannot be serialized or parsed back.
        """
        formatted = control.format_query_value(default)
        if formatted is None:
            return _UNSET
        match control.parse_query_value(formatted):
            case _options.ParseResult(value=v):
                return v
            case _:
                return _UNSET

    def _query_value(
        self,
        control: _options.InputControl,
        key: str,
    ) -> typing.Any:
        raw = self.query_params.get(key)
        if raw is None:
            return _UNSET
        match control.parse_query_value(raw):
            case _options.ParseError(message=msg):
                self.state.validation_errors[control.option] = msg
                if mo.running_in_notebook():
                    warnings.warn(msg, stacklevel=5)
                return _UNSET
            case _options.ParseResult(value=v):
                return v

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
            tokens = control.prompt_interactive(effective_default)
        except EOFError:
            return _UNSET
        except KeyboardInterrupt:
            print("\nAborted.")
            sys.exit(1)
        if tokens:
            new_raw = [*self.state.args.raw_args, *tokens]
            self.state.args = _parse.ParsedArgs.from_options(new_raw)
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


def _is_list_control(control: _options.InputControl) -> bool:
    return isinstance(
        control,
        (_list_options.ListControl, _list_options.SubgroupListControl),
    )
