import shlex
import typing

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import moops
from examples.composition import variant_trip
from moops import Group, _options, _parse


def _number_item(grp: Group) -> typing.Any:
    return grp.number(value=1.0, option="--tag", help_text="Tag")


def _text_item(grp: Group) -> typing.Any:
    return grp.text(value="x", option="--tag", help_text="Tag")


def _dropdown_item(grp: Group) -> typing.Any:
    return grp.dropdown(["a", "b", "c"], value="a", option="--tag", help_text="Tag")


def _multiselect_item(grp: Group) -> typing.Any:
    return grp.multiselect(["a", "b", "c"], value=[], option="--tag", help_text="Tag")


# (label, build_item, values) per supported non-merged list item control.
# The label is only for readable falsifying-example output.
_ItemRoundTripCase = tuple[str, typing.Callable[[Group], typing.Any], list[typing.Any]]

_ROUND_TRIP_ITEM_CASES = typing.cast(
    "st.SearchStrategy[_ItemRoundTripCase]",
    st.one_of(
        st.tuples(
            st.just("number"),
            st.just(_number_item),
            st.lists(st.integers(min_value=0, max_value=100).map(float), max_size=4),
        ),
        st.tuples(
            st.just("text"),
            st.just(_text_item),
            st.lists(st.text(alphabet="abcABC", min_size=1, max_size=4), max_size=4),
        ),
        st.tuples(
            st.just("dropdown"),
            st.just(_dropdown_item),
            st.lists(st.sampled_from(["a", "b", "c", None]), max_size=4),
        ),
        st.tuples(
            st.just("multiselect"),
            st.just(_multiselect_item),
            st.lists(
                st.lists(st.sampled_from(["a", "b", "c"]), unique=True), max_size=4
            ),
        ),
    ),
)


@settings(max_examples=80)
@given(case=_ROUND_TRIP_ITEM_CASES)
def test_list_non_merged_item_round_trips(
    case: _ItemRoundTripCase,
) -> None:
    """A non-merged list should round-trip any item control through CLI args.

    Generalizes over the item control type so the round-trip contract is not
    tied to one control. It covers items that serialize to no per-item token
    (an empty multiselect, whose anchor alone represents the item) and to a
    per-item flag (a dropdown ``None`` rendered as ``--no-tag``): both must
    reparse cleanly rather than being rejected as unexpected arguments.
    """
    _, build_item, values = case

    def build_list(group: Group, value: list[typing.Any]) -> typing.Any:
        return group.list(
            option="--item",
            item=build_item,
            help_text="Items",
            value=value,
        )

    source = Group(cli_args=["script.py"])
    source_ctrl = build_list(source, values)
    current_args = source.interface(source_ctrl)._current_args()  # type: ignore[reportPrivateUsage]
    target = Group(
        cli_args=(
            ["script.py", *shlex.split(current_args)] if current_args else ["script.py"]
        )
    )
    target_ctrl = build_list(target, [])

    target.interface(target_ctrl)

    assert target_ctrl.value == values


@settings(max_examples=2)
@given(
    selected=st.sampled_from(["car", "train"]),
    distance=st.integers(min_value=1, max_value=500),
    tickets=st.integers(min_value=1, max_value=20),
)
def test_controls_from_variant_rejects_inactive_branch_args(
    selected: str,
    distance: int,
    tickets: int,
) -> None:
    """Mirrored variants should still reject args for inactive branches."""

    inactive_option = (
        "--trip-travel-train-tickets"
        if selected == "car"
        else "--trip-travel-car-distance"
    )
    active_args = (
        ["--trip-travel-car-distance", str(distance)]
        if selected == "car"
        else ["--trip-travel-train-tickets", str(tickets)]
    )
    inactive_value = str(tickets if selected == "car" else distance)
    g = Group(
        cli_args=[
            "script.py",
            "--trip-mode",
            selected,
            *active_args,
            inactive_option,
            inactive_value,
        ]
    )
    trip = g.controls_from(moops.interface_of(variant_trip), prefix="trip")
    iface = typing.cast(typing.Any, trip)._moops_interface

    assert f"Unexpected argument: {inactive_option}" in list(
        iface.validate(g._state)  # type: ignore[reportPrivateUsage]
    )


def _control_from(build: typing.Callable[[Group], typing.Any]) -> _options.InputControl:
    """Build a control through the public Group API and return its InputControl.

    Going through the builders (rather than constructing ``_options`` dataclasses
    directly) keeps the generated controls configured exactly as real usage
    produces them -- correct metavars, ``select_opts`` mappings, none handling.
    """
    group = Group(cli_args=["script.py"])
    element = build(group)
    ctrl = group._input_map.get(element)  # type: ignore[reportPrivateUsage]
    assert ctrl is not None
    return ctrl


_DICT_OPTS = {"a": 1, "b": 2, "c": 3}


def _text_ctrl(value: str) -> _options.InputControl:
    return _control_from(lambda g: g.text(value=value, option="--opt", help_text="h"))


def _text_area_ctrl(value: str) -> _options.InputControl:
    return _control_from(
        lambda g: g.text_area(value=value, option="--opt", help_text="h")
    )


def _number_ctrl(value: float | None) -> _options.InputControl:
    return _control_from(lambda g: g.number(value=value, option="--opt", help_text="h"))


def _bounded_number_ctrl(value: float) -> _options.InputControl:
    return _control_from(
        lambda g: g.number(
            start=0, stop=100, value=value, option="--opt", help_text="h"
        )
    )


def _slider_ctrl(value: float) -> _options.InputControl:
    return _control_from(
        lambda g: g.slider(
            start=0, stop=100, value=value, option="--opt", help_text="h"
        )
    )


def _range_ctrl(pair: tuple[float, float]) -> _options.InputControl:
    return _control_from(
        lambda g: g.range_slider(
            start=0, stop=100, value=sorted(pair), option="--opt", help_text="h"
        )
    )


def _dropdown_ctrl(allow_none: bool) -> _options.InputControl:
    return _control_from(
        lambda g: g.dropdown(
            _DICT_OPTS,
            value="a",
            allow_select_none=allow_none,
            option="--opt",
            help_text="h",
        )
    )


def _multiselect_ctrl(default: list[int]) -> _options.InputControl:
    return _control_from(
        lambda g: g.multiselect(
            _DICT_OPTS, value=default, option="--opt", help_text="h"
        )
    )


# A meta strategy over control *types*: each branch yields an InputControl,
# parameterized over the configuration knobs that change its query behavior
# (bounds, none support, default). File controls are intentionally absent: they
# inherit a text ``strategy()`` that generates arbitrary paths, but their
# ``parse_query_value`` rejects paths that do not exist on disk, so their own
# strategy cannot round-trip. Compound list controls have their own round-trip
# tests (``test_list_*_round_trips``).
_QUERY_CONTROL_STRATEGY: st.SearchStrategy[_options.InputControl] = st.one_of(
    st.builds(_text_ctrl, st.text()),
    st.builds(_text_area_ctrl, st.text()),
    st.builds(
        _number_ctrl,
        st.one_of(
            st.none(),
            st.integers(),
            st.floats(allow_nan=False, allow_infinity=False),
        ),
    ),
    st.builds(_bounded_number_ctrl, st.floats(min_value=0, max_value=100)),
    st.builds(_slider_ctrl, st.floats(min_value=0, max_value=100)),
    st.builds(
        _range_ctrl,
        st.tuples(
            st.floats(min_value=0, max_value=100),
            st.floats(min_value=0, max_value=100),
        ),
    ),
    st.builds(_dropdown_ctrl, st.booleans()),
    st.builds(_multiselect_ctrl, st.lists(st.sampled_from([1, 2, 3]), unique=True)),
)


@st.composite
def _control_and_value(
    draw: st.DrawFn,
) -> tuple[_options.InputControl, typing.Any]:
    """Draw a control type, then a value from that control's own ``strategy()``."""
    control = draw(_QUERY_CONTROL_STRATEGY)
    return control, draw(control.strategy())


@pytest.mark.filterwarnings("ignore:.*outside the range of safe integers")
@settings(max_examples=300)
@given(case=_control_and_value())
def test_all_control_types_query_param_round_trip(
    case: tuple[_options.InputControl, typing.Any],
) -> None:
    """Any value round-trips through a control's query-param serialization.

    Generalizes the per-control round-trip checks over the control type itself:
    ``format_query_value`` then ``parse_query_value`` must reconstruct the value,
    and a ``None`` (omitted) serialization must mean the value equals the default
    (so loading without the param hydrates the same value).
    """
    control, value = case
    formatted = control.format_query_value(value)
    if formatted is None:
        assert value == control.default
        return
    result = control.parse_query_value(formatted)
    assert isinstance(result, _options.ParseResult), result
    assert result.value == value


@pytest.mark.filterwarnings("ignore:.*outside the range of safe integers")
@settings(max_examples=300)
@given(case=_control_and_value())
def test_all_control_types_cli_round_trip(
    case: tuple[_options.InputControl, typing.Any],
) -> None:
    """Any value round-trips through a control's CLI serialization.

    The companion to the query-param round-trip, over the same meta strategy:
    ``format_value`` then reparsing the resulting tokens must reconstruct the
    value, and an empty serialization must mean the value equals the default.
    Subsumes the per-control CLI parse checks (e.g. negative numbers).
    """
    control, value = case
    tokens = shlex.split(" ".join(control.format_value(value)))
    if not tokens:
        assert value == control.default
        return
    result = control.parse(_parse.ParsedArgs.from_options(tokens))
    assert isinstance(result, _options.ParseResult), result
    assert result.value == value
