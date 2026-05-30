import typing

from . import _options


def selected_key(selector: typing.Any) -> typing.Any:
    if hasattr(selector, "_selected_key"):
        return selector._selected_key
    return selector.value


def keys(selector: typing.Any) -> list[typing.Any]:
    input_control = getattr(selector, "_moops_input", None)
    if isinstance(input_control, _options.DropdownControl):
        return list(input_control.dropdown_opts)
    if isinstance(input_control, _options.FlagControl):
        return [False, True]
    raise TypeError("variant selector must be a moops dropdown, switch, or checkbox")


def key_text(key: typing.Any) -> str:
    return str(key).lower() if isinstance(key, bool) else str(key)


def control_option(control: typing.Any) -> str | None:
    input_control = getattr(control, "_moops_input", None)
    return (
        input_control.option
        if isinstance(input_control, _options.InputControl)
        else None
    )


def help_heading(selector_option: str | None, key_text: str) -> str:
    if selector_option:
        return f"Options for {selector_option} {key_text}"
    return f"Options for {key_text}"


def usage_placeholder(selector_option: str | None) -> str:
    if selector_option:
        name = selector_option.lstrip("-").replace("-", " ").upper()
        return f"[{name} OPTIONS]"
    return "[VARIANT OPTIONS]"
