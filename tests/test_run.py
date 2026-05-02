import asyncio
import typing

import hypothesis
import marimo as mo

import moops
import moops.testing
from examples import name_casing, notebook


def test_run_returns_result() -> None:
    result = moops.run(name_casing, text="Hello World", style="snake_case")
    assert result == "hello_world"


def test_run_default_values() -> None:
    result = moops.run(name_casing)
    assert result == "LoremIpsum"


_name_casing_args = moops.testing.notebook_args(name_casing)
_name_casing_defaults = _name_casing_args.default


@hypothesis.given(_name_casing_args.strategy())
def test_name_casing_preserves_alphanumeric_count(kwargs: dict[str, typing.Any]):
    result = moops.run(name_casing, **kwargs)
    input_text = kwargs.get("text", _name_casing_defaults["text"])
    assert not input_text.isascii() or sum(c.isalnum() for c in result) == sum(
        c.isalnum() for c in input_text
    )


def test_run_propagates_kwargs_to_subgroup_controls() -> None:
    # Default inputs: name="", be_polite=False, times=1 → greeting "Hey there!"
    # style="snake_case" must reach the embedded name_casing subgroup
    assert moops.run(notebook, casing={"style": "snake_case"}) == "hey_there!"
    assert moops.run(notebook, casing={"style": "camel_case"}) == "HeyThere!"


def test_defaults_supports_run_form() -> None:
    assert (
        moops.run(notebook, **moops.testing.notebook_args(notebook).default) is not None
    )


def test_overridden_control_is_disabled() -> None:
    async def _run() -> None:
        args = moops.Group(cli_args=["script.py"])
        casing = args.subgroup("casing", overrides={"text": "hello"})
        result = await name_casing.app.embed(defs={"args": casing})
        input_text = result.defs["input_text"]
        assert isinstance(input_text, mo.ui.text_area)
        return input_text._component_args["disabled"]  # type: ignore

    assert asyncio.run(_run()) is True
