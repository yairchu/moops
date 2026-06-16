import asyncio
import concurrent.futures
import types
import typing
import unittest.mock

import hypothesis
import marimo as mo
import pytest

import moops
from examples.composition import name_casing, notebook


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


def test_script_mode_embed_keep_retains_named_defs() -> None:
    # Lean script-mode embeds keep only `result` by default, dropping other
    # definitions a parent may need (e.g. a ground-truth alongside the result).
    # `keep` opts named definitions back in.
    async def _embed(keep: tuple[str, ...]) -> typing.Any:
        args = moops.Group(cli_args=["script.py"])
        return await moops.embed(name_casing.app, defs={"args": args}, keep=keep)

    lean = asyncio.run(_embed(()))
    assert "input_text" not in lean.defs
    kept = asyncio.run(_embed(("input_text",)))
    assert "input_text" in kept.defs
    assert kept.defs["result"] == lean.defs["result"]


def test_embed_keep_rejects_bare_string() -> None:
    with pytest.raises(TypeError, match="not a string"):
        asyncio.run(moops.embed(name_casing.app, keep="input_text"))  # type: ignore[arg-type]


def test_passthrough_equality_keeps_embed_cache_warm() -> None:
    # marimo's embed-output cache compares the `defs` it was handed, so two
    # Passthroughs forwarding the same result must compare equal -- otherwise a
    # cell that rebuilds `Passthrough(input_result)` on every re-run keeps
    # missing the cache and resets the embedded notebook's UI.
    result = object()
    assert moops.Passthrough({"result": result}) == moops.Passthrough(
        {"result": result}
    )
    assert moops.Passthrough({"result": result}) != moops.Passthrough(
        {"result": object()}
    )
    # Resultless passthroughs (e.g. interface-only) are interchangeable too.
    assert moops.Passthrough({}) == moops.Passthrough({})
    assert moops.Passthrough({"result": result}) != object()
    # Equal passthroughs must hash equal to stay usable as set/dict members.
    assert hash(moops.Passthrough({"result": result})) == hash(
        moops.Passthrough({"result": result})
    )


def test_passthrough_keep_rejects_bare_string() -> None:
    with pytest.raises(TypeError, match="not a string"):
        moops.Passthrough({"result": object()}, keep="input_text")  # type: ignore[arg-type]


def test_passthrough_supports_script_mode_embed() -> None:
    # An embedded notebook that calls moops.embed(override, ...) -- rather than
    # override.embed(...) directly -- routes through _embed_in_script -> app.run
    # in script mode.  A Passthrough injected as that override must therefore
    # support .run, not just .embed; otherwise this raises
    # AttributeError: 'Passthrough' object has no attribute 'run'.
    # Passing the Passthrough directly (no cast) also asserts, via pyright,
    # that it structurally satisfies the _App protocol moops.embed expects.
    pt = moops.Passthrough({"result": "hello"})
    out = asyncio.run(moops.embed(pt, defs={"args": object()}))
    assert out.defs.get("result") == "hello"


def test_moops_embed_rejects_app_defined_in_same_cell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeApp:
        def clone(self) -> "_FakeApp":
            return self

        async def embed(self, defs: dict[str, typing.Any] | None = None) -> typing.Any:
            return defs

        def run(
            self, defs: dict[str, typing.Any]
        ) -> tuple[typing.Iterable[typing.Any], typing.Mapping[str, object]]:
            return (), defs

    def defining_cells(var: str) -> set[str]:
        return {"cell-1"} if var == "child_app" else set()

    app = _FakeApp()
    context = types.SimpleNamespace(
        execution_context=types.SimpleNamespace(cell_id="cell-1"),
        graph=types.SimpleNamespace(get_defining_cells=defining_cells),
        globals={"child_app": app},
    )
    monkeypatch.setattr("moops._embed.mo.running_in_notebook", lambda: True)
    monkeypatch.setattr("marimo._runtime.context.get_context", lambda: context)

    with pytest.raises(
        RuntimeError,
        match=r"App\.embed\(\) cannot be called in the cell that imports the app",
    ):
        asyncio.run(moops.embed(app))


def test_run_does_not_use_thread_outside_async_context() -> None:
    # When there is no running event loop, run() should call app.run directly,
    # not via a ThreadPoolExecutor. A thread is only needed to avoid blocking
    # an existing event loop. Use a notebook without embed cells: moops.embed
    # legitimately offloads script-mode embeds to a thread regardless of how
    # the parent notebook was invoked.
    thread_pool_created: list[bool] = []
    real_tpe = concurrent.futures.ThreadPoolExecutor

    class _TrackingTPE(real_tpe):  # type: ignore[misc]
        def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
            thread_pool_created.append(True)
            super().__init__(*args, **kwargs)

    with unittest.mock.patch("concurrent.futures.ThreadPoolExecutor", _TrackingTPE):
        moops.run(name_casing)

    assert not thread_pool_created, (
        "run() should not use a thread outside async context"
    )


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


def test_interface_of_produces_no_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    # group.md() and similar should not print to stdout during interface queries.
    moops.interface_of(name_casing)
    assert capsys.readouterr().out == ""


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


def test_embedded_summary_links_to_current_standalone_query_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("moops.interface._running_in_edit_mode", lambda: True)
    args = moops.Group(cli_args=["script.py", "--no-casing-style"])
    casing = args.subgroup("casing", overrides={"text": "hello world"})
    result = asyncio.run(name_casing.app.embed(defs={"args": casing}))
    interface = result.defs["interface"]
    assert isinstance(interface, moops.Interface)
    html = typing.cast(typing.Any, interface)._subgroup_summary().text
    assert (
        'href="/?file=examples%2Fcomposition%2Fname_casing.py'
        '&amp;style=&amp;text=hello+world"' in html
    )
    assert 'target="_blank"' in html
