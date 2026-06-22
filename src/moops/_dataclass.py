from __future__ import annotations

import dataclasses
import enum
import types
import typing

import marimo as mo

Numeric = int | float
T = typing.TypeVar("T")


def controls_for_dataclass(
    group: typing.Any,
    cls: type[T],
) -> mo.ui.dictionary:
    if not dataclasses.is_dataclass(cls):
        raise TypeError("args.dataclass() expects a dataclass type")
    hints = typing.get_type_hints(cls, include_extras=True)
    controls: dict[str, typing.Any] = {}
    for field in dataclasses.fields(cls):
        if not field.init:
            continue
        default = _default(field)
        if default is dataclasses.MISSING:
            raise TypeError(
                f"Dataclass field {field.name!r} has no default; "
                "required fields are not supported"
            )
        controls[field.name] = _control_for_field(
            group, field, hints.get(field.name), default
        )
    return mo.ui.dictionary(controls)


def _default(field: dataclasses.Field[typing.Any]) -> typing.Any:
    if field.default is not dataclasses.MISSING:
        return field.default
    if field.default_factory is not dataclasses.MISSING:
        return field.default_factory()
    return dataclasses.MISSING


def _control_for_field(
    group: typing.Any,
    field: dataclasses.Field[typing.Any],
    annotation: object,
    default: typing.Any,
) -> typing.Any:
    label = str(field.metadata.get("label", field.name.replace("_", " ")))
    help_text = str(
        field.metadata.get(
            "help_text",
            f"Disable {label}" if default is True else label,
        )
    )
    kwargs = {
        key: field.metadata[key]
        for key in ("option", "start", "stop", "step")
        if key in field.metadata
    }
    typ = _simple_type(annotation, default)
    if typ is bool:
        if default is None:
            raise TypeError(
                f"Cannot infer a moops control for dataclass field {field.name!r}"
            )
        return group.switch(value=default, label=label, help_text=help_text, **kwargs)
    if typ is str:
        return group.text(value=default, label=label, help_text=help_text, **kwargs)
    if typ is int or typ is float:
        value = typing.cast(Numeric, default)
        return group.number(value=value, label=label, help_text=help_text, **kwargs)
    if isinstance(typ, tuple | dict):
        return group.dropdown(
            typ, value=default, label=label, help_text=help_text, **kwargs
        )
    raise TypeError(f"Cannot infer a moops control for dataclass field {field.name!r}")


def _simple_type(annotation: object, default: typing.Any) -> object:
    origin = typing.get_origin(annotation)
    if origin in {typing.Union, types.UnionType}:
        choices = [arg for arg in typing.get_args(annotation) if arg is not type(None)]
        if len(choices) == 1:
            annotation = choices[0]
            origin = typing.get_origin(annotation)
    if origin is typing.Literal:
        return typing.get_args(annotation)
    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        return {member.name: member for member in annotation}
    if annotation in {bool, str, int, float}:
        return annotation
    if default is not None:
        typ = typing.cast(object, type(default))
        if typ is bool or typ is str or typ is int or typ is float:
            return typ
        if isinstance(default, enum.Enum):
            return {member.name: member for member in type(default)}
    return None
