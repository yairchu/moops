import dataclasses
import shlex

from . import _parse, _query_params
from .presets import Presets


@dataclasses.dataclass(frozen=True)
class PresetState:
    selected: _parse.ParseState | None
    default: _parse.ParseState | None
    active: str | None

    @classmethod
    def resolve(
        cls,
        *,
        presets: Presets | None,
        query_params: _query_params.QueryParams,
        state: _parse.ParseState,
    ) -> "PresetState":
        selected = _build_selected(presets)
        default = _build_default(
            presets=presets,
            query_params=query_params,
            state=state,
        )
        return cls(
            selected=selected,
            default=default,
            active=_build_active(presets, default),
        )


def _build_selected(presets: Presets | None) -> _parse.ParseState | None:
    if presets is None or not presets.selected_args:
        return None
    return _parse_preset_args(presets.selected_args)


def _build_default(
    *,
    presets: Presets | None,
    query_params: _query_params.QueryParams,
    state: _parse.ParseState,
) -> _parse.ParseState | None:
    if (
        presets is None
        or (query_params.params is None and not state.args.is_interactive)
        or query_params.has_user_params()
        or presets.get_current() is not None
        or not presets.default_args
    ):
        return None
    return _parse_preset_args(presets.default_args)


def _build_active(
    presets: Presets | None,
    default: _parse.ParseState | None,
) -> str | None:
    if presets is None:
        return None
    if default is not None:
        return "default"
    return presets.get_current() or None


def _parse_preset_args(args_text: str) -> _parse.ParseState:
    args = _parse.ParsedArgs.from_options(shlex.split(args_text))
    return _parse.ParseState(args=args)
