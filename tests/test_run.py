import asyncio

import marimo as mo
from examples import name_casing

import moops


def test_run_returns_result():
    result = moops.run(name_casing, input_text="Hello World", style="snake_case")
    assert result == "hello_world"


def test_run_default_values():
    result = moops.run(name_casing)
    assert result == "LoremIpsum"


def test_overridden_control_is_disabled():
    async def _run():
        args = moops.Group(cli_args=["script.py"])
        casing = args.subgroup("casing", overrides={"input_text": "hello"})
        result = await name_casing.app.embed(defs={"args": casing})
        input_text = result.defs["input_text"]
        assert isinstance(input_text, mo.ui.text_area)
        return input_text._component_args["disabled"]

    assert asyncio.run(_run()) is True
