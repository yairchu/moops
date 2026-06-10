import pytest

from moops import Group


def test_invalid_arg_exits_nonzero() -> None:
    g = Group(cli_args=["script.py", "--unknown"])
    ctrl = g.switch(label="Verbose", help_text="Enable verbose output")
    with pytest.raises(SystemExit) as exc_info:
        g.interface(ctrl)
    assert exc_info.value.code != 0


def test_single_value_option_rejects_repeated_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py", "--name", "Alice", "--name", "Bob"])
    ctrl = g.text(label="Name", help_text="A name")

    with pytest.raises(SystemExit) as exc_info:
        g.interface(ctrl)

    assert exc_info.value.code != 0
    assert "--name was provided multiple times" in capsys.readouterr().out


def test_dropdown_no_flag_and_value_is_error(capsys: pytest.CaptureFixture[str]):
    g = Group(cli_args=["script.py", "--no-style", "--style", "snake_case"])
    ctrl = g.dropdown(
        ["snake_case", "camel_case"],
        value="camel_case",
        label="Style",
        help_text="Text style",
    )
    with pytest.raises(SystemExit) as exc_info:
        g.interface(ctrl)
    assert exc_info.value.code != 0
    assert "--no-style" in capsys.readouterr().out


def test_text_area_from_stdin_flag_with_value_is_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py", "--text-from-stdin=oops"])
    ctrl = g.text_area(option="--text", help_text="Input text")
    with pytest.raises(SystemExit) as exc_info:
        g.interface(ctrl)
    assert exc_info.value.code != 0
    output = capsys.readouterr().out
    assert "--text-from-stdin does not take a value, but was given: oops" in output


def test_split_dash_value_error_suggests_equals_form(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # A dash-leading non-numeric value is tokenized as an option, so
    # `--tag -dev` fails while `--tag=-dev` works. The error should point
    # the user at the working form.
    g = Group(cli_args=["script.py", "--tag", "-dev"])
    ctrl = g.text(option="--tag", help_text="Tag")
    with pytest.raises(SystemExit) as exc_info:
        g.interface(ctrl)
    assert exc_info.value.code != 0
    output = capsys.readouterr().out
    assert "--tag=-dev" in output


def test_variant_rejects_inactive_branch_options() -> None:
    g = Group(
        cli_args=[
            "script.py",
            "--mode",
            "car",
            "--travel-train-tickets",
            "5",
        ]
    )
    mode = g.dropdown(
        ["car", "train"],
        value="car",
        option="--mode",
        help_text="How to travel",
        allow_select_none=False,
    )
    travel = g.variant("travel", mode)

    distance = travel["car"].number(
        value=120,
        option="--distance",
        help_text="Driving distance in miles",
    )
    tickets = travel["train"].number(
        value=2,
        option="--tickets",
        help_text="Number of train tickets",
    )

    with pytest.raises(SystemExit) as exc_info:
        g.interface(
            mode,
            travel["car"].interface(distance),
            travel["train"].interface(tickets),
        )

    assert exc_info.value.code != 0
