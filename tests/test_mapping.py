import pytest

from moops import Group, composites


def test_mapping_rejects_equals_in_string_key() -> None:
    with pytest.raises(ValueError, match="Mapping key must not contain ="):
        composites.mapping(
            Group(cli_args=["script.py"]),
            option="--item",
            help_text="Items",
            default={"a=b": "c"},
        )


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        ("invalid", "Mapping entry must be KEY=VALUE"),
        ("not-an-int=1", "Mapping key must be int"),
        ("0=1", "Mapping contains duplicate key"),
    ],
)
def test_mapping_rejects_invalid_cli_entries(
    entry: str,
    message: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli_args = ["script.py", "--item", entry]
    if entry == "0=1":
        cli_args.extend(["--item", "0=2"])
    group = Group(cli_args=cli_args)
    mapping = composites.mapping(
        group,
        option="--item",
        help_text="Sparse items",
        key=int,
        value=float,
    )

    with pytest.raises(SystemExit) as exc_info:
        group.interface(mapping)

    assert exc_info.value.code != 0
    assert message in capsys.readouterr().out


def test_mapping_can_append_after_rerender(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("moops._list_options.mo.running_in_notebook", lambda: True)
    monkeypatch.setattr("moops.group.mo.running_in_notebook", lambda: True)
    params: dict[str, str] = {}
    monkeypatch.setattr("moops.group.mo.query_params", lambda: params)
    changes: list[dict[int, float]] = []
    group = Group(cli_args=["script.py"])

    first_mapping = composites.mapping(
        group,
        option="--item",
        help_text="Sparse items",
        key=int,
        value=float,
        default={},
        on_change=changes.append,
    )
    first_mapping._add_btn._on_click(None)  # pyright: ignore[reportPrivateUsage]
    second_mapping = composites.mapping(
        group,
        option="--item",
        help_text="Sparse items",
        key=int,
        value=float,
        default=changes[-1],
        on_change=changes.append,
    )

    second_mapping._add_btn._on_click(None)  # pyright: ignore[reportPrivateUsage]

    assert changes[-1] == {0: 0.0, 1: 0.0}


def test_mapping_allows_clearing_a_numeric_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("moops._list_options.mo.running_in_notebook", lambda: True)
    monkeypatch.setattr("moops.group.mo.running_in_notebook", lambda: True)
    params: dict[str, str] = {}
    monkeypatch.setattr("moops.group.mo.query_params", lambda: params)
    changes: list[dict[int, float]] = []
    mapping = composites.mapping(
        Group(cli_args=["script.py"]),
        option="--item",
        help_text="Sparse items",
        key=int,
        value=float,
        default={0: 1.0},
        on_change=changes.append,
    )

    item_row = mapping._list_ui._display._live_children[0]  # pyright: ignore[reportPrivateUsage]
    key_input = item_row._live_children[5]
    key_input._on_change(None)

    assert changes == []
    composites.mapping(
        Group(cli_args=["script.py"]),
        option="--item",
        help_text="Sparse items",
        key=int,
        value=float,
        default={0: 1.0},
        on_change=changes.append,
    )


def test_mapping_can_remove_its_last_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("moops._list_options.mo.running_in_notebook", lambda: True)
    monkeypatch.setattr("moops.group.mo.running_in_notebook", lambda: True)
    params: dict[str, str] = {}
    monkeypatch.setattr("moops.group.mo.query_params", lambda: params)
    changes: list[dict[int, float]] = []
    group = Group(cli_args=["script.py"])
    mapping = composites.mapping(
        group,
        option="--item",
        help_text="Sparse items",
        key=int,
        value=float,
        default={0: 1.0},
        on_change=changes.append,
    )

    list_ui = mapping._list_ui  # pyright: ignore[reportPrivateUsage]
    item_row = list_ui._display._live_children[0]
    remove_button = item_row._live_children[4]
    remove_button._on_click(None)

    assert changes == [{}]


def test_mapping_current_args_reflect_live_widget_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("moops._list_options.mo.running_in_notebook", lambda: True)
    monkeypatch.setattr("moops.group.mo.running_in_notebook", lambda: True)
    params: dict[str, str] = {}
    monkeypatch.setattr("moops.group.mo.query_params", lambda: params)
    group = Group(cli_args=["script.py"])
    mapping = composites.mapping(
        group,
        option="--item",
        help_text="Sparse items",
        key=int,
        value=float,
        default={0: 1.0},
        on_change=lambda _: None,
    )
    interface = group.interface(mapping)

    item_row = mapping._list_ui._display._live_children[0]  # pyright: ignore[reportPrivateUsage]
    item_row._live_children[5]._value = 2
    item_row._live_children[6]._value = 3.5

    assert interface._current_args() == "--item 2=3.5"  # pyright: ignore[reportPrivateUsage]
