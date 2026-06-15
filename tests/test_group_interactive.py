import pytest

from moops import Group


def test_interactive_ctrl_c_exits_cleanly(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_input(_prompt: str) -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", fake_input)
    g = Group(cli_args=["script.py", "--interactive"])
    with pytest.raises(SystemExit) as exc_info:
        g.switch(label="Verbose", help_text="Enable verbose output")
    assert exc_info.value.code == 1
    assert "Aborted." in capsys.readouterr().out


def test_interactive_range_bad_numbers_reprompts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(["10,abc", "20,80"])

    def fake_input(_prompt: str) -> str:
        return next(responses)

    monkeypatch.setattr("builtins.input", fake_input)
    g = Group(cli_args=["script.py", "--interactive"])
    ctrl = g.range_slider(
        start=0, stop=100, value=[10, 50], label="Range", help_text="A range"
    )
    g.interface(ctrl)
    assert ctrl.value == [20, 80]


def test_interactive_flag_invalid_input_reprompts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(["maybe", "y"])

    def fake_input(_prompt: str) -> str:
        return next(responses)

    monkeypatch.setattr("builtins.input", fake_input)
    g = Group(cli_args=["script.py", "--interactive"])
    ctrl = g.switch(label="Verbose", help_text="Enable verbose output")
    g.interface(ctrl)
    assert ctrl.value is True


def test_interactive_dropdown_none_value_not_treated_as_sentinel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dropdown with "none" as an allowed value: selecting it by text should not
    be treated as the no-selection sentinel."""
    responses = iter(["none"])

    def fake_input(_prompt: str) -> str:
        return next(responses)

    monkeypatch.setattr("builtins.input", fake_input)
    g = Group(cli_args=["script.py", "--interactive"])
    ctrl = g.dropdown(
        ["none", "some"],
        value="some",
        label="Mode",
        help_text="Mode",
        allow_select_none=False,
    )
    g.interface(ctrl)
    assert ctrl.value == "none"


def test_interactive_multiselect_invalid_input_reprompts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(["a,typo", "a,c"])

    def fake_input(_prompt: str) -> str:
        return next(responses)

    monkeypatch.setattr("builtins.input", fake_input)
    g = Group(cli_args=["script.py", "--interactive"])
    ctrl = g.multiselect(
        ["a", "b", "c"],
        value=["b"],
        label="Tags",
        help_text="Tags",
    )
    g.interface(ctrl)
    assert ctrl.value == ["a", "c"]


def test_interactive_multiselect_accepts_numbered_choices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(["1,3"])

    def fake_input(_prompt: str) -> str:
        return next(responses)

    monkeypatch.setattr("builtins.input", fake_input)
    g = Group(cli_args=["script.py", "--interactive"])
    ctrl = g.multiselect(
        ["a", "b", "c"],
        value=["b"],
        label="Tags",
        help_text="Tags",
    )
    g.interface(ctrl)
    assert ctrl.value == ["a", "c"]


def test_interactive_multiselect_eof_after_invalid_input_keeps_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(["typo"])

    def fake_input(_prompt: str) -> str:
        try:
            return next(responses)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr("builtins.input", fake_input)
    g = Group(cli_args=["script.py", "--interactive"])
    ctrl = g.multiselect(
        ["a", "b", "c"],
        value=["b"],
        label="Tags",
        help_text="Tags",
    )
    g.interface(ctrl)
    assert ctrl.value == ["b"]
