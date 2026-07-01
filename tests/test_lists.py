import pathlib
import shlex
import typing

import pytest

import moops
import moops._marimo_controls as _marimo_controls
import moops._options as _options
import moops.group as group_module
import moops.interface as interface_module
from examples.composition import variant_trip
from moops import Group


def test_list_non_merged_anchor_parses_correctly() -> None:
    """Non-merged list: bare --add anchors each item; --factor VALUE follows it.
    Before the fix, --factor was flagged as unexpected and --add was not treated
    as the anchor, so parsing returned an empty list."""
    g = Group(
        cli_args=["script.py", "--add", "--factor", "2", "--add", "--factor", "5"]
    )
    ctrl = g.list(
        option="--add",
        item=lambda grp: grp.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[],
        on_change=lambda _: None,
    )
    iface = g.interface(ctrl)
    assert iface.missing_options() == []
    assert ctrl.value == [2.0, 5.0]


def test_list_non_merged_allows_following_sibling_options() -> None:
    """A non-merged list item should end before the next sibling option.

    The parser must not consume every later CLI token as part of the last list
    item; otherwise ordinary options after the list are rejected as item args.
    """
    g = Group(cli_args=["script.py", "--add", "--factor", "2", "--name", "Bob"])
    factors = g.list(
        option="--add",
        item=lambda grp: grp.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[],
    )
    name = g.text(option="--name", help_text="Name")

    iface = g.interface(factors, name)

    assert iface.missing_options() == []
    assert factors.value == [2.0]
    assert name.value == "Bob"


def test_list_non_merged_item_option_without_anchor_is_rejected(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A per-item option outside an anchor segment must not be silently ignored."""
    g = Group(cli_args=["script.py", "--factor", "2"])
    ctrl = g.list(
        option="--add",
        item=lambda grp: grp.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[],
    )

    with pytest.raises(SystemExit) as exc_info:
        g.interface(ctrl)

    assert exc_info.value.code != 0
    assert "Unexpected argument: --factor" in capsys.readouterr().out


def test_list_non_merged_rejects_duplicate_scalar_item_option_in_segment(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A single list item must not silently keep only the last scalar value."""
    g = Group(cli_args=["script.py", "--add", "--factor", "2", "--factor", "5"])
    ctrl = g.list(
        option="--add",
        item=lambda grp: grp.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[],
    )

    with pytest.raises(SystemExit) as exc_info:
        g.interface(ctrl)

    assert exc_info.value.code != 0
    assert "--factor was provided multiple times" in capsys.readouterr().out


def test_list_rejects_flag_item_controls() -> None:
    """Flag item controls are currently ambiguous and should fail fast."""
    g = Group(cli_args=["script.py"])

    with pytest.raises(ValueError, match=r"list.*value.*control"):
        g.list(
            option="--enabled",
            item=lambda grp: grp.switch(
                flag="--enabled",
                help_text="Enable item",
            ),
            help_text="Enabled items",
            value=[],
        )


def test_list_current_args_keeps_items_equal_to_item_default() -> None:
    """List items equal to the item control's default are still list data.

    Before the fix, rendering delegated to item_control.format_value(), which
    omitted default-valued items and changed [1.0, 2.0] into just [2.0]."""
    g = Group(cli_args=["script.py"])
    ctrl = g.list(
        option="--factor",
        item=lambda grp: grp.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[1.0, 2.0],
    )
    iface = g.interface(ctrl)

    assert iface._current_args() == "--factor 1.0 --factor 2.0"  # type: ignore[attr-defined]


def test_list_current_args_round_trips_default_item_starting_with_dash() -> None:
    g = Group(cli_args=["script.py"])
    ctrl = g.list(
        option="--word",
        item=lambda grp: grp.text(value="-x", option="--word", help_text="Word"),
        help_text="Words",
        value=["-x"],
    )
    current_args = g.interface(ctrl)._current_args()  # type: ignore[attr-defined]

    target = Group(cli_args=["script.py", *shlex.split(current_args)])
    target_ctrl = target.list(
        option="--word",
        item=lambda grp: grp.text(value="-x", option="--word", help_text="Word"),
        help_text="Words",
        value=[],
    )

    target.interface(target_ctrl)

    assert target_ctrl.value == ["-x"]


def test_script_callout_command_wraps_long_list_options() -> None:
    """The script-callout command should wrap, even for a single list control.

    A list emits its whole repeated sequence as one option group, so the
    per-group wrapping kept it all on a single overflowing line. The wrapped
    command should break long lines instead of producing one giant line."""
    from moops._text_wrap import wrap_command

    g = Group(cli_args=["script.py"])
    ctrl = g.list(
        option="--factor",
        item=lambda grp: grp.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[float(n) for n in range(1, 11)],
    )
    iface = g.interface(ctrl)

    command = wrap_command("script.py", iface._arg_groups())  # type: ignore[attr-defined]
    longest = max(len(line) for line in command.splitlines())
    assert longest <= 72, command


def test_script_callout_command_uses_two_space_continuation_indent() -> None:
    from moops._text_wrap import wrap_command

    command = wrap_command(
        "script.py",
        ["--first value", "--second value"],
        width=20,
    )

    assert command == "script.py \\\n  --first value \\\n  --second value"


def test_uv_run_script_callout_keeps_runner_with_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    script = tmp_path / "notebook.py"
    script.write_text("")
    monkeypatch.setenv("UV_RUN_RECURSION_DEPTH", "1")

    command = interface_module._wrap_command(  # type: ignore[reportPrivateUsage]
        str(script),
        ["--first value", "--second value"],
    )

    assert command.startswith(f"uv run {shlex.quote(str(script))} \\\n")


def test_list_controls_from_variant_parses_nested_items() -> None:
    variant_iface = moops.interface_of(variant_trip)
    g = Group(
        cli_args=[
            "script.py",
            "--trip",
            "--mode",
            "car",
            "--travel-car-distance",
            "100",
            "--trip",
            "--mode",
            "train",
            "--travel-train-tickets",
            "4",
        ]
    )
    ctrl = g.list(
        option="--trip",
        item=lambda grp: grp.controls_from(variant_iface, prefix="trip"),
        help_text="Trips",
        value=[],
    )

    g.interface(ctrl)

    assert ctrl.value == [
        {
            "mode": "car",
            "travel-car": {"distance": 100, "gas_price": 3.75},
            "travel-train": {"tickets": 2},
        },
        {
            "mode": "train",
            "travel-car": {"distance": 120, "gas_price": 3.75},
            "travel-train": {"tickets": 4},
        },
    ]


def test_list_help_shows_options_for_item_using_implicit_default_branch() -> None:
    """A list item that relies on the selector's default (car) instead of
    repeating --mode should still show that branch's options in --help."""
    variant_iface = moops.interface_of(variant_trip)
    g = Group(
        cli_args=[
            "script.py",
            "--trip",
            "--mode",
            "train",
            "--travel-train-tickets",
            "3",
            "--trip",
            "--travel-car-distance",
            "50",
        ]
    )
    ctrl = g.list(
        option="--trip",
        item=lambda grp: grp.controls_from(variant_iface, prefix="trip"),
        help_text="Trips",
        value=[],
    )
    iface = g.interface(ctrl)

    assert "Options for --mode car" in iface.help()


def test_list_help_updates_after_command_box_changes_active_variant_branch() -> None:
    variant_iface = moops.interface_of(variant_trip)
    g = Group(
        cli_args=[
            "script.py",
            "--trip",
            "--mode",
            "train",
            "--travel-train-tickets",
            "3",
        ]
    )
    ctrl = g.list(
        option="--trip",
        item=lambda grp: grp.controls_from(variant_iface, prefix="trip"),
        help_text="Trips",
        value=[],
    )
    iface = g.interface(ctrl)

    assert (
        iface.apply_cli_args("script.py --trip --mode car --travel-car-distance 50")
        == ()
    )

    assert "Options for --mode car" in iface.help()


def test_list_controls_from_variant_rejects_inactive_branch_options(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A mirrored variant list item should reject options from inactive branches."""
    variant_iface = moops.interface_of(variant_trip)
    g = Group(
        cli_args=[
            "script.py",
            "--trip",
            "--mode",
            "train",
            "--travel-car-distance",
            "999",
        ]
    )
    ctrl = g.list(
        option="--trip",
        item=lambda grp: grp.controls_from(variant_iface, prefix="trip"),
        help_text="Trips",
        value=[],
    )

    with pytest.raises(SystemExit) as exc_info:
        g.interface(ctrl)

    assert exc_info.value.code != 0
    assert "Unexpected argument: --travel-car-distance" in capsys.readouterr().out


def test_list_controls_from_current_args_round_trips_default_item() -> None:
    variant_iface = moops.interface_of(variant_trip)
    g = Group(cli_args=["script.py"])
    ctrl = g.list(
        option="--trip",
        item=lambda grp: grp.controls_from(variant_iface, prefix="trip"),
        help_text="Trips",
        value=[variant_iface.default],
    )

    iface = g.interface(ctrl)

    assert iface._current_args() == "--trip"  # type: ignore[attr-defined]


def test_list_controls_from_mapped_dropdown_omits_default_item_options() -> None:
    source = Group(cli_args=["child.py"])
    mode = source.dropdown(
        {"car": "Car", "train": "Train"},
        value="train",
        option="--mode",
        help_text="Mode",
        allow_select_none=False,
    )
    child_iface = source.interface(mode)

    g = Group(cli_args=["script.py"])
    ctrl = g.list(
        option="--trip",
        item=lambda grp: grp.controls_from(child_iface, prefix="trip"),
        help_text="Trips",
        value=[child_iface.default],
    )

    iface = g.interface(ctrl)

    assert iface._current_args() == "--trip"  # type: ignore[attr-defined]


def test_list_controls_from_seeded_items_are_editable() -> None:
    variant_iface = moops.interface_of(variant_trip)
    g = Group(cli_args=["script.py"])
    ctrl = g.list(
        option="--trip",
        item=lambda grp: grp.controls_from(variant_iface, prefix="trip"),
        help_text="Trips",
        value=[
            {
                "mode": "train",
                "travel-car": {"distance": 120, "gas_price": 3.75},
                "travel-train": {"tickets": 4},
            }
        ],
    )

    item = ctrl.elements[0]

    assert item.elements["mode"]._component_args["disabled"] is False  # type: ignore[attr-defined]
    assert (
        item.elements["travel-train"]
        .elements["tickets"]
        ._component_args[  # type: ignore[attr-defined]
            "disabled"
        ]
        is False
    )


def test_list_controls_from_item_edits_update_outer_list_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    variant_iface = moops.interface_of(variant_trip)
    changes: list[list[typing.Any]] = []
    g = Group(cli_args=["script.py"])
    monkeypatch.setattr(_options.mo, "running_in_notebook", lambda: True)
    fake_query_params: dict[str, typing.Any] = {}
    monkeypatch.setattr(_options.mo, "query_params", lambda: fake_query_params)
    ctrl = g.list(
        option="--trip",
        item=lambda grp: grp.controls_from(variant_iface, prefix="trip"),
        help_text="Trips",
        value=[variant_iface.default],
        on_change=changes.append,
    )

    item = ctrl._array.elements[0]  # type: ignore[attr-defined]
    item.elements["mode"]._on_change("train")  # type: ignore[attr-defined]
    item.elements["travel-train"].elements["tickets"]._on_change(4)  # type: ignore[attr-defined]

    assert changes[-2][0]["mode"] == "train"
    assert changes[-1][0]["travel-train"]["tickets"] == 4


def test_list_controls_from_delete_does_not_resurrect_by_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Editing one item then deleting it must not leak that item's value onto
    the item that takes its index.

    Each list item is mirrored in an index-keyed subgroup (``trip-0``,
    ``trip-1``), so an edit to item 0 writes a query param keyed by index 0.
    After deleting item 0, the surviving item is rebuilt at index 0 and the
    resolver reads the stale ``trip-0`` query param with priority over the
    seeded value, so the survivor wrongly shows the deleted item's value.
    Symptom: change the first of two trips to "train", delete the first, and
    the remaining trip shows "train" instead of the second trip's "car".
    """
    # Patch before constructing the Group so its query params are notebook-live;
    # QueryParams is captured at Group construction via from_notebook().
    monkeypatch.setattr(_options.mo, "running_in_notebook", lambda: True)
    fake_query_params: dict[str, typing.Any] = {}
    monkeypatch.setattr(_options.mo, "query_params", lambda: fake_query_params)

    variant_iface = moops.interface_of(variant_trip)
    trips: list[typing.Any] = [
        dict(variant_iface.default),
        dict(variant_iface.default),
    ]

    def build() -> typing.Any:
        def on_change(new: list[typing.Any]) -> None:
            trips[:] = [dict(item) for item in new]

        g = Group(cli_args=["script.py"])
        return g.list(
            option="--trip",
            item=lambda grp: grp.controls_from(variant_iface, prefix="trip"),
            help_text="Trips",
            value=[dict(item) for item in trips],
            on_change=on_change,
        )

    ctrl = build()
    ctrl._array.elements[0].elements["mode"]._on_change("train")  # type: ignore[attr-defined]

    # Rerun, then delete the (now "train") first item the way the remove button
    # does: read the live item values, drop index 0, and report through the
    # list's synced on_change so the list-level query param is rewritten too.
    ctrl = build()
    live = [element.value for element in ctrl._array.elements]  # type: ignore[attr-defined]
    ctrl._moops_reset_state(live[1:])  # type: ignore[attr-defined]

    ctrl = build()
    surviving = ctrl._array.elements[0]  # type: ignore[attr-defined]
    assert surviving.elements["mode"].value == "car"


def test_list_controls_from_nested_variant_selector_edit_updates_live_item_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = Group(cli_args=["child.py"])
    mode = source.dropdown(
        ["advanced", "simple"],
        value="advanced",
        option="--mode",
        help_text="Mode",
        allow_select_none=False,
    )
    mode_branches = source.variant("mode", mode)
    advanced = mode_branches["advanced"]
    detail = advanced.dropdown(
        ["basic", "custom"],
        value="basic",
        option="--detail",
        help_text="Detail level",
        allow_select_none=False,
    )
    detail_branches = advanced.variant("detail", detail)
    basic_count = detail_branches["basic"].number(
        value=1,
        option="--count",
        help_text="Count",
    )
    custom_name = detail_branches["custom"].text(
        value="example",
        option="--name",
        help_text="Name",
    )
    simple_count = mode_branches["simple"].number(
        value=2,
        option="--count",
        help_text="Count",
    )
    child_iface = source.interface(
        mode,
        advanced.interface(
            detail,
            detail_branches["basic"].interface(basic_count),
            detail_branches["custom"].interface(custom_name),
        ),
        mode_branches["simple"].interface(simple_count),
    )

    changes: list[list[typing.Any]] = []
    g = Group(cli_args=["script.py"])
    monkeypatch.setattr(_options.mo, "running_in_notebook", lambda: True)
    fake_query_params: dict[str, typing.Any] = {}
    monkeypatch.setattr(_options.mo, "query_params", lambda: fake_query_params)
    ctrl = g.list(
        option="--settings",
        item=lambda grp: grp.controls_from(child_iface, prefix="settings"),
        help_text="Settings",
        value=[
            {
                "mode": "advanced",
                "mode-advanced": {"detail": "custom"},
            }
        ],
        on_change=changes.append,
    )

    item = ctrl._array.elements[0]  # type: ignore[attr-defined]
    advanced_mirror = item.elements["mode-advanced"]
    # Drive the selector the way the frontend does, via marimo's _update.
    advanced_mirror.elements["detail"]._update(["basic"])  # type: ignore[attr-defined]

    assert changes[-1][0]["mode-advanced"]["detail"] == "basic"
    # The live list item value is read while handling later edits and list
    # mutations. It must reflect the nested selector edit immediately, not keep
    # the previous active branch until the next notebook rerun.
    assert item.value["mode-advanced"]["detail"] == "basic"


def test_list_controls_from_mapped_dropdown_edit_keeps_selected_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mirrored dropdown leaf whose option key differs from its mapped value
    must keep ``_selected_key`` as the option key after a frontend edit. The
    list change handler used to copy the on_change value (the mapped value) into
    ``_selected_key``, corrupting the key that serialization reads back."""
    source = Group(cli_args=["child.py"])
    mode = source.dropdown(
        {"slow": 1, "fast": 2},
        value="slow",
        option="--mode",
        help_text="Mode",
        allow_select_none=False,
    )
    child_iface = source.interface(mode)

    changes: list[list[typing.Any]] = []
    g = Group(cli_args=["script.py"])
    monkeypatch.setattr(_options.mo, "running_in_notebook", lambda: True)
    fake_query_params: dict[str, typing.Any] = {}
    monkeypatch.setattr(_options.mo, "query_params", lambda: fake_query_params)
    ctrl = g.list(
        option="--settings",
        item=lambda grp: grp.controls_from(child_iface, prefix="settings"),
        help_text="Settings",
        value=[{"mode": "slow"}],
        on_change=changes.append,
    )

    item = ctrl._array.elements[0]  # type: ignore[attr-defined]
    leaf = item.elements["mode"]
    # Drive the change the way the frontend does: marimo's _update converts the
    # option key to the mapped value and sets _selected_key to the key before
    # firing the change handler.
    leaf._update(["fast"])  # type: ignore[attr-defined]

    assert leaf.value == 2
    assert leaf._selected_key == "fast"  # type: ignore[attr-defined]
    assert _marimo_controls.ctrl_value(leaf) == "fast"
    assert item.value["mode"] == 2


def test_list_controls_from_variant_displays_only_active_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    variant_iface = moops.interface_of(variant_trip)
    g = Group(cli_args=["script.py"])
    monkeypatch.setattr(_options.mo, "running_in_notebook", lambda: True)
    fake_query_params: dict[str, typing.Any] = {}
    monkeypatch.setattr(_options.mo, "query_params", lambda: fake_query_params)
    ctrl = g.list(
        option="--trip",
        item=lambda grp: grp.controls_from(variant_iface, prefix="trip"),
        help_text="Trips",
        value=[
            {
                "mode": "train",
                "travel-car": {"distance": 120, "gas_price": 3.75},
                "travel-train": {"tickets": 4},
            }
        ],
        on_change=lambda _: None,
    )

    item = ctrl._array.elements[0]  # type: ignore[attr-defined]

    assert list(item._moops_visible_elements()) == ["mode", "travel-train"]


def test_list_controls_from_rejects_item_option_without_anchor(
    capsys: pytest.CaptureFixture[str],
) -> None:
    variant_iface = moops.interface_of(variant_trip)
    g = Group(cli_args=["script.py", "--mode", "train"])
    ctrl = g.list(
        option="--trip",
        item=lambda grp: grp.controls_from(variant_iface, prefix="trip"),
        help_text="Trips",
        value=[],
    )

    with pytest.raises(SystemExit) as exc_info:
        g.interface(ctrl)

    assert exc_info.value.code != 0
    assert "Unexpected argument: --mode" in capsys.readouterr().out


def test_list_controls_from_allows_following_sibling_options() -> None:
    variant_iface = moops.interface_of(variant_trip)
    g = Group(
        cli_args=[
            "script.py",
            "--trip",
            "--mode",
            "car",
            "--name",
            "Bob",
        ]
    )
    trips = g.list(
        option="--trip",
        item=lambda grp: grp.controls_from(variant_iface, prefix="trip"),
        help_text="Trips",
        value=[],
    )
    name = g.text(option="--name", help_text="Name")

    iface = g.interface(trips, name)

    assert iface.missing_options() == []
    assert trips.value == [
        {
            "mode": "car",
            "travel-car": {"distance": 120, "gas_price": 3.75},
            "travel-train": {"tickets": 2},
        }
    ]
    assert name.value == "Bob"


def test_list_controls_from_rejects_item_option_after_sibling_option(
    capsys: pytest.CaptureFixture[str],
) -> None:
    variant_iface = moops.interface_of(variant_trip)
    g = Group(
        cli_args=[
            "script.py",
            "--trip",
            "--mode",
            "car",
            "--name",
            "Bob",
            "--travel-train-tickets",
            "4",
        ]
    )
    trips = g.list(
        option="--trip",
        item=lambda grp: grp.controls_from(variant_iface, prefix="trip"),
        help_text="Trips",
        value=[],
    )
    name = g.text(option="--name", help_text="Name")

    with pytest.raises(SystemExit) as exc_info:
        g.interface(trips, name)

    assert exc_info.value.code != 0
    assert "Unexpected argument: --travel-train-tickets" in capsys.readouterr().out


def test_list_standalone_query_value_round_trips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generated standalone query values should hydrate the same list value."""
    source = Group(cli_args=["script.py"])
    source_ctrl = source.list(
        option="--factor",
        item=lambda grp: grp.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[2.0, 5.0],
    )
    query_values = source.interface(source_ctrl)._standalone_query_values()  # type: ignore[attr-defined]

    monkeypatch.setattr(group_module.mo, "running_in_notebook", lambda: True)
    monkeypatch.setattr(group_module.mo, "query_params", lambda: query_values)

    target = Group(cli_args=["script.py"])
    target_ctrl = target.list(
        option="--factor",
        item=lambda grp: grp.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[],
    )

    assert target_ctrl.value == [2.0, 5.0]


def test_list_subgroup_query_round_trips_non_serializable_mapped_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A list item that maps a dropdown to a non-JSON-serializable value (e.g.
    a class, like a torch optimizer) must still round-trip through the query
    param.

    Regression: ``SubgroupListControl.format_query_value`` json-dumped the
    resolved item values, hit ``TypeError`` on the non-serializable value, and
    returned ``None``, so the whole list's query param was silently dropped.
    Under an active preset that left the preset authoritative on every rerender,
    so editing any control snapped back to the preset value. The query
    representation must use the dropdown KEY, like everywhere else in moops.
    """

    # Classes are not JSON-serializable (like torch.optim.Adam) and, unlike
    # object() instances, survive deepcopy with identity so the round-trip can
    # be asserted against them.
    class Adam:
        pass

    class Sgd:
        pass

    mapping = {"adam": Adam, "sgd": Sgd}

    source = Group(cli_args=["script.py"])
    optimizer = source.dropdown(
        mapping,
        value="adam",
        option="--optimizer",
        help_text="Optimizer",
        allow_select_none=False,
    )
    child_iface = source.interface(optimizer)

    src_group = Group(cli_args=["script.py"])
    src_ctrl = src_group.list(
        option="--step",
        item=lambda grp: grp.controls_from(child_iface, prefix="step"),
        help_text="Steps",
        value=[{"optimizer": Adam}],
    )
    query_values = src_group.interface(src_ctrl)._standalone_query_values()  # type: ignore[attr-defined]

    # The list's query param must be present (it was silently dropped before).
    assert "step" in query_values

    # And it must hydrate back to the same mapped value.
    monkeypatch.setattr(group_module.mo, "running_in_notebook", lambda: True)
    monkeypatch.setattr(group_module.mo, "query_params", lambda: query_values)
    tgt_group = Group(cli_args=["script.py"])
    tgt_ctrl = tgt_group.list(
        option="--step",
        item=lambda grp: grp.controls_from(child_iface, prefix="step"),
        help_text="Steps",
        value=[],
    )

    assert tgt_ctrl.value == [{"optimizer": Adam}]


def test_list_subgroup_query_round_trips_non_default_nested_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-default value in a nested (variant subgroup) list item must survive
    the query round-trip.

    Regression: serializing the list query value via the CLI display token form
    combined an item's ``option value`` into a single token (e.g.
    ``"--travel-car-distance 250"``), which the parser could not read back, so
    the value collapsed to its template default on the next render.
    """
    iface = moops.interface_of(variant_trip)
    edited = [
        {
            "mode": "car",
            "travel-car": {"distance": 250, "gas_price": 3.75},
            "travel-train": {"tickets": 2},
        }
    ]

    source = Group(cli_args=["script.py"])
    src_ctrl = source.list(
        option="--trip",
        item=lambda grp: grp.controls_from(iface, prefix="trip"),
        help_text="Trip",
        value=edited,
    )
    query_values = source.interface(src_ctrl)._standalone_query_values()  # type: ignore[attr-defined]

    monkeypatch.setattr(group_module.mo, "running_in_notebook", lambda: True)
    monkeypatch.setattr(group_module.mo, "query_params", lambda: query_values)
    target = Group(cli_args=["script.py"])
    target_ctrl = target.list(
        option="--trip",
        item=lambda grp: grp.controls_from(iface, prefix="trip"),
        help_text="Trip",
        value=[],
    )

    assert target_ctrl.value[0]["travel-car"]["distance"] == 250


def test_list_empty_value_overrides_non_empty_default_in_query() -> None:
    """An explicitly empty list is user state, not absence of a query override."""
    g = Group(cli_args=["script.py"])
    ctrl = g.list(
        option="--factor",
        item=lambda grp: grp.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[1.0],
    )
    ctrl._value = []  # type: ignore[attr-defined]

    assert g.interface(ctrl)._standalone_query_values() == {  # type: ignore[attr-defined]
        "factor": "[]"
    }


def test_list_merged_dropdown_item_accepts_no_flag() -> None:
    """Merged lists must parse the item control's auxiliary flags too.

    A dropdown item with a non-None default formats a None item as --no-style;
    the same argument should be accepted when pasted back into the CLI.
    """
    source = Group(cli_args=["script.py"])
    source_ctrl = source.list(
        option="--style",
        item=lambda grp: grp.dropdown(
            ["a", "b"], value="a", option="--style", help_text="Style"
        ),
        help_text="Styles",
        value=[None],
    )
    args = source.interface(source_ctrl)._current_args()  # type: ignore[attr-defined]

    target = Group(cli_args=["script.py", *args.split()])
    target_ctrl = target.list(
        option="--style",
        item=lambda grp: grp.dropdown(
            ["a", "b"], value="a", option="--style", help_text="Style"
        ),
        help_text="Styles",
        value=[],
    )

    target.interface(target_ctrl)

    assert target_ctrl.value == [None]


def test_interactive_list_prompts_for_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In --interactive mode, list controls should prompt for items.

    The current prompt_interactive() stub returns {} unconditionally, so the
    list stays empty instead of collecting the user's inputs."""
    responses = iter(["2", "5", ""])  # two items, empty to stop

    def fake_input(_prompt: str) -> str:
        return next(responses)

    monkeypatch.setattr("builtins.input", fake_input)
    g = Group(cli_args=["script.py", "--interactive"])
    ctrl = g.list(
        option="--factor",
        item=lambda grp: grp.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[],
        on_change=lambda _: None,
    )
    g.interface(ctrl)
    assert ctrl.value == [2.0, 5.0]


def test_interactive_list_non_merged_anchor_prompts_for_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In --interactive mode, non-merged list controls should prompt for items."""
    responses = iter(["2", "5", ""])  # two items, empty to stop

    def fake_input(_prompt: str) -> str:
        return next(responses)

    monkeypatch.setattr("builtins.input", fake_input)
    g = Group(cli_args=["script.py", "--interactive"])
    ctrl = g.list(
        option="--add",
        item=lambda grp: grp.number(value=1.0, option="--factor", help_text="Factor"),
        help_text="Factors",
        value=[],
        on_change=lambda _: None,
    )
    g.interface(ctrl)
    assert ctrl.value == [2.0, 5.0]


def test_interactive_list_controls_from_prompts_for_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In --interactive mode, subgroup list controls should prompt for items."""
    child = Group(cli_args=["child.py"])
    name = child.text(value="", option="--name", help_text="Name")
    age = child.number(value=0, option="--age", help_text="Age")
    child_iface = child.interface(name, age)
    responses = iter(["Alice", "30", ""])

    def fake_input(_prompt: str) -> str:
        return next(responses)

    monkeypatch.setattr("builtins.input", fake_input)
    g = Group(cli_args=["script.py", "--interactive"])
    ctrl = g.list(
        option="--person",
        item=lambda grp: grp.controls_from(child_iface, prefix="person"),
        help_text="People",
        value=[],
    )

    g.interface(ctrl)

    assert ctrl.value == [{"name": "Alice", "age": 30}]


def test_file_browser_in_list_round_trips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A file_browser mirrored into an args.list item must round-trip. Its widget
    value is a tuple of file infos, but the list serializes each item leaf as a
    string (FileControl inherits TextControl.format_value), so rebuilding the
    list from the captured value raises AttributeError on the tuple. A
    file_browser works standalone (ctrl_value normalizes it to a path); the list
    path does not.
    """

    def fake_query_params() -> dict[str, str]:
        return {}

    monkeypatch.setattr(group_module.mo, "running_in_notebook", lambda: True)
    monkeypatch.setattr(group_module.mo, "query_params", fake_query_params)

    source = Group(cli_args=["child.py"])
    browser = source.file_browser(
        option="--state", multiple=False, help_text="State file"
    )
    child_iface = source.interface(browser)

    parent = Group(cli_args=["parent.py"])
    steps = parent.list(
        option="--step",
        item=lambda grp: grp.controls_from(child_iface, prefix="step"),
        help_text="Steps",
        value=[{}],
    )

    # Adding/editing an item rebuilds the list from its captured value, where the
    # mirrored file_browser leaf holds its tuple value — this must not raise.
    other = Group(cli_args=["parent.py"])
    other.list(
        option="--step",
        item=lambda grp: grp.controls_from(child_iface, prefix="step"),
        help_text="Steps",
        value=steps.value,
    )
