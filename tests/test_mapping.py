import pytest

from moops import Group


def test_mapping_can_remove_its_last_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("moops._list_options.mo.running_in_notebook", lambda: True)
    monkeypatch.setattr("moops.group.mo.running_in_notebook", lambda: True)
    params: dict[str, str] = {}
    monkeypatch.setattr("moops.group.mo.query_params", lambda: params)
    changes: list[dict[int, float]] = []
    group = Group(cli_args=["script.py"])
    mapping = group.mapping(
        option="--item",
        help_text="Sparse items",
        key=int,
        value=float,
        default={0: 1.0},
        on_change=changes.append,
    )

    list_ui = mapping._list_ui
    item_row = list_ui._display._live_children[0]
    remove_button = item_row._live_children[4]
    remove_button._on_click(None)

    assert changes == [{}]
