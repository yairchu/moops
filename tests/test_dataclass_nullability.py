import dataclasses
import enum
import typing

import pytest

from moops import Group

PixelResponse = enum.Enum(
    "PixelResponse", {"NONE": "none", "BOX": "box", "TRIANGLE": "triangle"}
)


@pytest.mark.parametrize(
    ("annotation", "default", "metadata_key"),
    [
        (typing.Literal["none", "box", "triangle"], "triangle", "allow_select_none"),
        (PixelResponse, PixelResponse.TRIANGLE, "allow_select_none"),
        (int, 2, "allow_none"),
        (float, 2.5, "allow_none"),
    ],
    ids=["literal", "enum", "int", "float"],
)
@pytest.mark.parametrize(
    ("optional", "override", "allows_none"),
    [
        (False, None, False),
        (True, None, True),
        (False, True, True),
        (True, False, False),
    ],
    ids=["required", "optional", "opt-in", "opt-out"],
)
def test_dataclass_nullability_controls_no_flag(
    annotation: typing.Any,
    default: typing.Any,
    metadata_key: str,
    optional: bool,
    override: bool | None,
    allows_none: bool,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_cls = dataclasses.make_dataclass(
        "Config",
        [
            (
                "response",
                annotation | None if optional else annotation,
                dataclasses.field(
                    default=default,
                    metadata={} if override is None else {metadata_key: override},
                ),
            )
        ],
    )
    group = Group(cli_args=["script.py"])
    config = group.dataclass(config_cls)
    control = config.elements["response"]
    input_control = group._input_map.get(control)  # type: ignore[reportPrivateUsage]
    assert input_control is not None
    assert ("--no-response" in input_control.flags()) is allows_none
    if metadata_key == "allow_select_none":
        assert control._component_args["allow-select-none"] is allows_none  # type: ignore[reportPrivateUsage]
    assert config.value["response"] == default

    group = Group(cli_args=["script.py", "--no-response"])
    config = group.dataclass(config_cls)
    if allows_none:
        group.interface(*config.elements.values())
        assert config.value["response"] is None
    else:
        with pytest.raises(SystemExit) as exc_info:
            group.interface(*config.elements.values())
        assert exc_info.value.code != 0
        assert "Unexpected argument: --no-response" in capsys.readouterr().out


@pytest.mark.parametrize("optional", [False, True])
def test_dataclass_nullability_choice_widget_and_help(
    optional: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    annotation = typing.Literal["none", "box", "triangle"]
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
    assert "--response {none|box|triangle}" in output
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


@pytest.mark.parametrize(
    ("annotation", "default", "cli_args"),
    [
        (typing.Literal["box", None], None, []),
        (typing.Literal["box", None], "box", ["--no-response"]),
        (typing.Annotated[int | None, "Target word count"], 2, ["--no-response"]),
    ],
    ids=["literal-none-default", "literal-clear", "annotated-clear"],
)
def test_dataclass_nullability_nested_none(
    annotation: typing.Any, default: typing.Any, cli_args: list[str]
) -> None:
    config_cls = dataclasses.make_dataclass(
        "Config", [("response", annotation, default)]
    )
    group = Group(cli_args=["script.py", *cli_args])
    config = group.dataclass(config_cls)
    group.interface(*config.elements.values())
    assert config.value["response"] is None
