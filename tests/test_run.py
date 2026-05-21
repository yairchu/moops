import asyncio
import types
import typing

import hypothesis
import marimo as mo
import pytest

import moops
from examples import name_casing, notebook


def test_is_interface_query_set_for_help_and_interface_of() -> None:
    assert not moops.Group(cli_args=["script.py"]).is_interface_query
    assert moops.Group(cli_args=["script.py", "--help"]).is_interface_query
    assert moops.Group.for_interface_query().is_interface_query

    parent = moops.Group.for_interface_query()
    child = parent.subgroup("sub")
    assert child.is_interface_query


def test_script_mode_embed_forwards_interface() -> None:
    # _embed_in_script must forward the embedded notebook's real interface so
    # parent notebooks can see subgroup controls.  Without the fix,
    # result.defs["interface"] is always an empty Interface(controls=()).
    async def _embed() -> moops.Interface:
        args = moops.Group(cli_args=["script.py"])
        result = await moops.embed(name_casing.app, defs={"args": args})
        return typing.cast(moops.Interface, result.defs["interface"])

    iface = asyncio.run(_embed())
    assert len(iface.controls) > 0


def test_run_works_from_async_context() -> None:
    # moops.run() called from within a running event loop must not crash with
    # "asyncio.run() cannot be called from a running event loop".
    async def _call() -> typing.Any:
        return moops.run(notebook)

    assert asyncio.run(_call()) is not None


def test_run_returns_result() -> None:
    result = moops.run(name_casing, text="Hello World", style="snake_case")
    assert result == "hello_world"


def test_run_default_values() -> None:
    result = moops.run(name_casing)
    assert result == "LoremIpsum"


class _AppWithoutResult:
    def run(self, defs: dict[str, typing.Any]) -> tuple[None, dict[str, typing.Any]]:
        return None, {}


def test_run_requires_result_variable() -> None:
    module = types.ModuleType("missing_result")
    module.app = _AppWithoutResult()  # type: ignore[attr-defined]
    with pytest.raises(RuntimeError, match=r"missing_result.*'result'"):
        moops.run(module)


_name_casing_interface: moops.Interface = moops.interface_of(name_casing)
_name_casing_defaults: dict[str, typing.Any] = _name_casing_interface.default


@hypothesis.given(_name_casing_interface.strategy())
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
    iface = moops.interface_of(notebook)
    assert moops.run(notebook, **iface.default) is not None


def test_cur_values_excludes_overridden_controls() -> None:
    args = moops.Group.with_overrides({"style": "snake_case"})
    result = asyncio.run(name_casing.app.embed(defs={"args": args}))
    iface = typing.cast(moops.Interface, result.defs["interface"])
    assert "--style" not in iface.cur_values()


def test_overridden_control_is_disabled() -> None:
    args = moops.Group(cli_args=["script.py"])
    casing = args.subgroup("casing", overrides={"text": "hello"})
    result = asyncio.run(name_casing.app.embed(defs={"args": casing}))
    input_text = result.defs["input_text"]
    assert isinstance(input_text, mo.ui.text_area)
    assert input_text._component_args["disabled"] is True  # type: ignore


def test_embedded_summary_links_to_current_standalone_query_params() -> None:
    args = moops.Group(cli_args=["script.py", "--no-casing-style"])
    casing = args.subgroup("casing", overrides={"text": "hello world"})
    result = asyncio.run(name_casing.app.embed(defs={"args": casing}))
    interface = result.defs["interface"]
    assert isinstance(interface, moops.Interface)
    html = typing.cast(typing.Any, interface)._subgroup_summary().text
    assert (
        'href="/?file=examples%2Fname_casing.py&amp;style=&amp;text=hello+world"'
        in html
    )
    assert 'target="_blank"' in html
