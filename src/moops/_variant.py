import dataclasses
import typing

from . import _choice_options, _naming, _options


@dataclasses.dataclass(frozen=True)
class VariantContext:
    """Per-branch presentation state derived from ``Group.variant()``.

    These fields are always populated together by ``variant()`` and otherwise
    left at their defaults, so they travel as one value object shared between a
    ``Group`` and the ``Interface`` it builds. Lives here (rather than on
    ``Group``) so ``interface.py`` can read it without importing ``group``.
    """

    help_heading: str | None = None
    usage_placeholder: str | None = None
    usage_after_option: str | None = None
    selector_option: str | None = None
    selector_parent_prefix: str = ""
    key: str | None = None
    group_prefix: str | None = None
    short_options: bool = False


def selected_key(selector: typing.Any) -> typing.Any:
    if hasattr(selector, "_selected_key"):
        return selector._selected_key
    # A switch/checkbox used as a variant selector has no `_selected_key`. In
    # the controls_from mirroring path the selector is a freshly-cloned widget,
    # so reading `.value` trips marimo's "value accessed in its creating cell"
    # guard; the raw cached `_value` holds the same value without the guard.
    if hasattr(selector, "_value"):
        return selector._value
    return selector.value


def keys(selector: typing.Any) -> list[typing.Any]:
    input_control = getattr(selector, "_moops_input", None)
    if isinstance(input_control, _options.DropdownControl):
        return list(input_control.dropdown_opts)
    if isinstance(input_control, _options.FlagControl):
        return [False, True]
    raise TypeError("variant selector must be a moops dropdown, switch, or checkbox")


def key_text(key: typing.Any) -> str:
    if isinstance(key, bool):
        return str(key).lower()
    return _choice_options.cli_key(str(key))


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
        name = _naming.option_to_label(selector_option).upper()
        return f"[{name} OPTIONS]"
    return "[VARIANT OPTIONS]"
