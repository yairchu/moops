import typing

from . import _options, interface


def create_control(
    group: typing.Any,
    iface: interface.Interface,
    cli: _options.InputControl,
) -> typing.Any:
    option = _unprefixed_option(iface, cli.option)
    if isinstance(cli, _options.FlagControl):
        return group.switch(
            value=cli.default,
            flag=option,
            help_text=cli.help_text,
        )
    if isinstance(cli, _options.MultiSelectControl):
        return group.multiselect(
            options=cli.select_opts,
            value=cli.default,
            option=option,
            help_text=cli.help_text,
        )
    if isinstance(cli, _options.NumberControl):
        return group.number(
            value=cli.default,
            option=option,
            help_text=cli.help_text,
        )
    if isinstance(cli, _options.RangeControl):
        return group.range_slider(
            start=cli.start,
            stop=cli.stop,
            steps=cli.allowed_values,
            value=cli.default,
            option=option,
            help_text=cli.help_text,
        )
    if isinstance(cli, _options.TextAreaControl):
        return group.text_area(
            value=cli.default,
            option=option,
            help_text=cli.help_text,
        )
    if isinstance(cli, _options.FileControl):
        return group.file_browser(
            initial_path=cli.default,
            option=option,
            help_text=cli.help_text,
            multiple=False,
        )
    if isinstance(cli, _options.MultiFileControl):
        return group.file_browser(
            initial_path=cli.default[0] if cli.default else "",
            option=option,
            help_text=cli.help_text,
            multiple=True,
        )
    if isinstance(cli, _options.TextControl):
        return group.text(
            value=cli.default,
            option=option,
            help_text=cli.help_text,
        )
    if isinstance(cli, _options.DropdownControl):
        return group.dropdown(
            options=cli.dropdown_opts,
            value=cli.default,
            option=option,
            help_text=cli.help_text,
            allow_select_none=cli.supports_none,
        )
    raise NotImplementedError(f"controls_from() does not support {type(cli).__name__}")


def _unprefixed_option(iface: interface.Interface, option: str) -> str:
    if iface.option_prefix and option.startswith(f"{iface.option_prefix}-"):
        return f"--{option[len(iface.option_prefix) :].lstrip('-')}"
    return option
