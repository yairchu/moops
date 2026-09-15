import dataclasses
import enum
import typing

import pytest

from moops import Group

PixelResponse = enum.Enum(
    "PixelResponse", {"AUTO": "auto", "BOX": "box", "TRIANGLE": "triangle"}
)


@pytest.mark.parametrize(
    ("annotation", "default", "metadata_key"),
    [
        (typing.Literal["auto", "box", "triangle"], "triangle", "allow_select_none"),
        (PixelResponse, PixelResponse.TRIANGLE, "allow_select_none"),
        (int, 2, "allow_none"),
        (float, 2.5, "allow_none"),
    ],
    ids=["literal", "enum", "int", "float"],
)
@pytest.mark.parametrize("optional", [False, True], ids=["required", "optional"])
def test_dataclass_nullability_controls_no_flag(
    annotation: typing.Any,
    default: typing.Any,
    metadata_key: str,
    optional: bool,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_cls = dataclasses.make_dataclass(
        "Config",
        [
            (
                "response",
                annotation | None if optional else annotation,
                default,
            )
        ],
    )
    group = Group(cli_args=["script.py"])
    config = group.dataclass(config_cls)
    control = config.elements["response"]
    input_control = group._input_map.get(control)  # type: ignore[reportPrivateUsage]
    assert input_control is not None
    assert ("--no-response" in input_control.flags()) is optional
    if metadata_key == "allow_select_none":
        assert control._component_args["allow-select-none"] is optional  # type: ignore[reportPrivateUsage]
    assert config.value["response"] == default

    group = Group(cli_args=["script.py", "--no-response"])
    config = group.dataclass(config_cls)
    if optional:
        group.interface(*config.elements.values())
        assert config.value["response"] is None
    else:
        with pytest.raises(SystemExit) as exc_info:
            group.interface(*config.elements.values())
        assert exc_info.value.code != 0
        assert "Unexpected argument: --no-response" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("annotation", "default", "metadata_key"),
    [
        (typing.Literal["box", "triangle"], "box", "allow_select_none"),
        (int, 2, "allow_none"),
    ],
    ids=["choice", "number"],
)
@pytest.mark.parametrize("optional", [False, True], ids=["required", "optional"])
@pytest.mark.parametrize("override", [False, True], ids=["deny-none", "allow-none"])
def test_dataclass_rejects_nullability_metadata(
    annotation: typing.Any,
    default: typing.Any,
    metadata_key: str,
    optional: bool,
    override: bool,
) -> None:
    # Reject redundant metadata as well as metadata contradicting the type.
    config_cls = dataclasses.make_dataclass(
        "Config",
        [
            (
                "response",
                annotation | None if optional else annotation,
                dataclasses.field(default=default, metadata={metadata_key: override}),
            )
        ],
    )
    group = Group(cli_args=["script.py"])
    with pytest.raises(TypeError) as exc_info:
        group.dataclass(config_cls)
    message = str(exc_info.value)
    assert "response" in message
    assert metadata_key in message
    assert "None" in message
    assert "type" in message.lower() or "annotation" in message.lower()


@pytest.mark.parametrize("optional", [False, True])
def test_dataclass_nullability_choice_widget_and_help(
    optional: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    annotation = typing.Literal["auto", "box", "triangle"]
    config_cls = dataclasses.make_dataclass(
        "Config",
        [("response", annotation | None if optional else annotation, "triangle")],
    )
    group = Group(cli_args=["script.py", "--help"])
    config = group.dataclass(config_cls)
    control = config.elements["response"]
    # This marimo property controls whether the dropdown offers a blank selection.
    assert control._component_args["allow-select-none"] is optional  # type: ignore[reportPrivateUsage]
    with pytest.raises(SystemExit) as exc_info:
        group.interface(control)
    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "--response {auto|box|triangle}" in output
    assert ("--no-response" in output) is optional


@pytest.mark.parametrize(
    "annotation", [typing.Literal["box", "triangle"], PixelResponse]
)
def test_dataclass_nullability_required_choice_rejects_none_default(
    annotation: typing.Any,
) -> None:
    config_cls = dataclasses.make_dataclass("Config", [("response", annotation, None)])
    group = Group(cli_args=["script.py"])
    with pytest.raises(TypeError, match="response"):
        group.dataclass(config_cls)


@pytest.mark.parametrize(
    "annotation", [typing.Literal["box", "triangle"], PixelResponse, int, float]
)
def test_dataclass_nullability_optional_none_default_is_preserved(
    annotation: typing.Any,
) -> None:
    config_cls = dataclasses.make_dataclass(
        "Config", [("response", annotation | None, None)]
    )
    group = Group(cli_args=["script.py"])
    config = group.dataclass(config_cls)
    group.interface(*config.elements.values())
    assert config.value["response"] is None


def test_dataclass_nullability_annotated_clear() -> None:
    config_cls = dataclasses.make_dataclass(
        "Config",
        [("response", typing.Annotated[int | None, "Target word count"], 2)],
    )
    group = Group(cli_args=["script.py", "--no-response"])
    config = group.dataclass(config_cls)
    group.interface(*config.elements.values())
    assert config.value["response"] is None


@pytest.mark.parametrize(
    ("default", "cli_args"),
    [(None, []), ("box", ["--no-response"]), ("box", ["--response", "none"])],
    ids=["none-default", "clear-flag", "none-choice"],
)
def test_dataclass_literal_with_none_member_warns(
    default: typing.Any, cli_args: list[str]
) -> None:
    # A Literal that spells out None offers a 'none' choice *and* a cleared
    # state; both resolve to None, so the dropdown warns about the pair.
    config_cls = dataclasses.make_dataclass(
        "Config", [("response", typing.Literal["box", None], default)]
    )
    group = Group(cli_args=["script.py", *cli_args])
    with pytest.warns(UserWarning, match="easy to confuse"):
        config = group.dataclass(config_cls)
    group.interface(*config.elements.values())
    assert config.value["response"] is None
