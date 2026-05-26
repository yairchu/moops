from __future__ import annotations

import typing


def option_values(
    options: typing.Sequence[typing.Any] | dict[str, typing.Any],
) -> dict[str, typing.Any]:
    if isinstance(options, dict):
        return dict(options)
    return {str(opt): opt for opt in options}


def option_key(options: dict[str, typing.Any], value: typing.Any) -> str:
    if isinstance(value, str) and value in options:
        return value
    return next(
        (key for key, option_value in options.items() if value == option_value),
        str(value),
    )


def option_value(options: dict[str, typing.Any], value: typing.Any) -> typing.Any:
    return options[value] if isinstance(value, str) and value in options else value
