from __future__ import annotations

import typing


def cli_key(key: str) -> str:
    return key.lower().replace(" ", "-")


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


def option_cli_keys(options: dict[str, typing.Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key in options:
        normalized = cli_key(key)
        if normalized in result:
            raise ValueError(
                f"Dropdown options {result[normalized]!r} and {key!r} both "
                f"normalize to CLI value {normalized!r}"
            )
        result[normalized] = key
    return result


def option_value(options: dict[str, typing.Any], value: typing.Any) -> typing.Any:
    return options[value] if isinstance(value, str) and value in options else value
