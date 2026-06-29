import pytest

import moops.group as group_module
from moops import Group


def test_parenthetical_units_colliding_on_option_raise() -> None:
    g = Group(cli_args=["script.py"])
    secs = g.number(label="Length (seconds)", help_text="Clip length in seconds")
    mins = g.number(label="Length (minutes)", help_text="Clip length in minutes")

    with pytest.raises(ValueError, match=r"--length.*parenthetical"):
        g.interface(secs, mins)


def test_duplicate_control_error_mentions_interface() -> None:
    g = Group(cli_args=["script.py"])
    ctrl = g.switch(label="Verbose", help_text="Enable verbose output")
    method = g.interface
    with pytest.raises(ValueError, match="Duplicate"):
        method(ctrl, ctrl)


def test_control_requires_label_or_option() -> None:
    g = Group(cli_args=["script.py"])

    with pytest.raises(ValueError, match="Either label or option must be provided"):
        g.text(help_text="Some option")


def test_dropdown_options_cannot_be_empty() -> None:
    g = Group(cli_args=["script.py"])

    with pytest.raises(ValueError, match="Dropdown options cannot be empty"):
        g.dropdown([], label="Style", help_text="Text style")


def test_notebook_dropdown_value_must_be_an_option(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(group_module.mo, "running_in_notebook", lambda: True)
    monkeypatch.setattr(group_module.mo, "query_params", lambda: dict[str, str]())

    g = Group(cli_args=["script.py"])

    with pytest.raises(ValueError, match="Dropdown value must be one of"):
        g.dropdown(["car", "train"], value="banana", label="Mode", help_text="Mode")


def test_duplicate_subgroup_interface_raises_error() -> None:
    g = Group(cli_args=["script.py"])
    sub = g.subgroup("x")
    ctrl = sub.switch(label="Verbose", help_text="Enable verbose output")
    iface = sub.interface(ctrl)
    with pytest.raises(ValueError, match="Duplicate"):
        g.interface(iface, iface)
