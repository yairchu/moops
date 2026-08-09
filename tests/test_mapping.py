import asyncio
import typing

import marimo as mo
import pytest
from marimo._ast.app import InternalApp
from marimo._config.config import DEFAULT_CONFIG
from marimo._messaging.types import KernelStreams, NoopStream
from marimo._runtime.app.kernel_runner import (  # pyright: ignore[reportMissingTypeStubs]
    AppKernelRunner,
)
from marimo._runtime.commands import AppMetadata, UpdateUIElementCommand
from marimo._runtime.context.kernel_context import initialize_kernel_context
from marimo._runtime.context.types import teardown_context
from marimo._runtime.patches import create_main_module
from marimo._runtime.runner.hooks import NotebookCellHooks
from marimo._runtime.runtime import Kernel
from marimo._session.model import SessionMode

from moops import Group, composites


def test_mapping_can_be_nested_in_marimo_dictionary() -> None:
    mapping = composites.mapping(
        Group(cli_args=["script.py"]),
        option="--item",
        help_text="Items",
        default={"a": "b"},
    )

    container = mo.ui.dictionary({"mapping": mapping})

    assert container.value == {"mapping": {"a": "b"}}


def test_mapping_preserves_dictionary_value_through_controls_from(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    params: dict[str, str] = {}
    monkeypatch.setattr("moops.group.mo.running_in_notebook", lambda: True)
    monkeypatch.setattr("moops.group.mo.query_params", lambda: params)
    source = Group(cli_args=["source.py"])
    mapping = composites.mapping(
        source,
        option="--item",
        help_text="Items",
        key=int,
        value=float,
        default={1: 2.0},
    )
    source_interface = source.interface(mapping)

    target = Group(cli_args=["target.py"])
    mirrored = target.controls_from(source_interface, prefix="source")

    assert mirrored.value == {"item": {1: 2.0}}


def test_mapping_edit_reruns_dependent_cell() -> None:
    app = mo.App()

    @app.cell
    def _() -> tuple[typing.Any]:
        import moops

        return (moops,)

    @app.cell
    def _(moops: typing.Any) -> tuple[typing.Any]:
        mapping = moops.composites.mapping(
            moops.Group(cli_args=["script.py"]),
            option="--item",
            help_text="Items",
            key=int,
            value=float,
            default={0: 1.0},
        )
        return (mapping,)

    @app.cell
    def _(mapping: typing.Any) -> tuple[typing.Any]:
        observed = mapping.value
        return (observed,)

    async def edit_mapping() -> dict[int, float]:
        internal_app = InternalApp(app)
        streams = KernelStreams(
            stream=NoopStream(), stdout=None, stderr=None, stdin=None
        )
        kernel = Kernel(
            cell_configs={},
            app_metadata=AppMetadata(
                {}, {}, app_config=internal_app.config, filename="<test>"
            ),
            user_config=DEFAULT_CONFIG,
            streams=streams,
            module=create_main_module("<test>", input_override=None),
            enqueue_control_request=lambda _: None,
            hooks=NotebookCellHooks(),
        )
        initialize_kernel_context(
            kernel=kernel,
            streams=streams,
            virtual_file_storage=None,
            mode=SessionMode.EDIT,
        )
        try:
            runner = AppKernelRunner(internal_app)
            await runner.run(set(internal_app.execution_order))

            mapping = runner.globals["mapping"]
            first_entry = mapping._list_ui._array.elements[0]
            key_input = first_entry.elements["key"]
            updated = await runner.set_ui_element_value(
                UpdateUIElementCommand(
                    object_ids=[key_input._id],
                    values=[2],
                ),
                notify_frontend=False,
            )

            assert updated
            assert key_input._value == 2
            assert mapping.value == {2: 1.0}
            return typing.cast(dict[int, float], runner.globals["observed"])
        finally:
            teardown_context()

    assert asyncio.run(edit_mapping()) == {2: 1.0}


def test_mapping_rejects_invalid_typed_default() -> None:
    with pytest.raises(ValueError, match="Mapping key must be int"):
        composites.mapping(
            Group(cli_args=["script.py"]),
            option="--item",
            help_text="Items",
            key=int,
            value=float,
            default={"not-an-int": 1.0},
        )


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


def test_mapping_rejects_duplicate_nan_float_keys() -> None:
    group = Group(cli_args=["script.py", "--item", "nan=1", "--item", "nan=2"])
    mapping = composites.mapping(
        group,
        option="--item",
        help_text="Sparse items",
        key=float,
        value=int,
    )

    with pytest.raises(SystemExit):
        group.interface(mapping)


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

    first_entry = mapping._list_ui._array.elements[0]  # pyright: ignore[reportPrivateUsage]
    key_input = first_entry.elements["key"]
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


@pytest.mark.parametrize("field", ["key", "value"])
def test_mapping_rejects_fractional_integer_widget_edits(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
) -> None:
    monkeypatch.setattr("moops._list_options.mo.running_in_notebook", lambda: True)
    monkeypatch.setattr("moops.group.mo.running_in_notebook", lambda: True)
    params: dict[str, str] = {}
    monkeypatch.setattr("moops.group.mo.query_params", lambda: params)
    changes: list[dict[int, int]] = []
    mapping = composites.mapping(
        Group(cli_args=["script.py"]),
        option="--item",
        help_text="Items",
        key=int,
        value=int,
        default={0: 0},
        on_change=changes.append,
    )

    first_entry = mapping._list_ui._array.elements[0]  # pyright: ignore[reportPrivateUsage]
    integer_input = first_entry.elements[field]
    integer_input._on_change(1.5)

    assert changes == []


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

    first_entry = mapping._list_ui._array.elements[0]  # pyright: ignore[reportPrivateUsage]
    first_entry.elements["key"]._value = 2
    first_entry.elements["value"]._value = 3.5

    assert interface._current_args() == "--item 2=3.5"  # pyright: ignore[reportPrivateUsage]
