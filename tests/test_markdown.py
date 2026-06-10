import typing

import marimo as mo
import pytest

import moops.group as group_module
from moops import Group


def test_subgroup_markdown_demotes_headings_in_notebooks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rendered: list[str] = []

    def fake_md(text: str) -> mo.Html:
        rendered.append(text)
        return typing.cast(mo.Html, object())

    # Patch before constructing: output_mode is set from running_in_notebook()
    # at construction, and the notebook branch of __init__ reads query_params().
    monkeypatch.setattr(group_module.mo, "running_in_notebook", lambda: True)
    monkeypatch.setattr(group_module.mo, "query_params", lambda: dict[str, str]())
    monkeypatch.setattr(group_module.mo, "md", fake_md)

    g = Group(cli_args=["script.py"])
    sub = g.subgroup("embedded")

    sub.md("# Title\n## Section\n```\n# Not a title\n```\n####### Not a heading\n")

    assert rendered == [
        "## Title\n### Section\n```\n# Not a title\n```\n####### Not a heading\n"
    ]


def test_subgroup_markdown_demotes_indented_converted_mo_md(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rendered: list[str] = []

    def fake_md(text: str) -> mo.Html:
        rendered.append(text)
        return typing.cast(mo.Html, object())

    monkeypatch.setattr(group_module.mo, "running_in_notebook", lambda: True)
    monkeypatch.setattr(group_module.mo, "query_params", lambda: dict[str, str]())
    monkeypatch.setattr(group_module.mo, "md", fake_md)

    g = Group(cli_args=["script.py"])
    sub = g.subgroup("embedded")

    sub.md(
        """
    # Converted title

    ```
    # Not a title
    ```
    """
    )

    assert rendered == [
        "\n    ## Converted title\n\n    ```\n    # Not a title\n    ```\n    "
    ]


def test_subgroup_markdown_demotes_headings_in_cli(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py"])
    sub = g.subgroup("embedded")

    sub.md("# Title\n## Section\n```\n# Not a title\n```")

    assert (
        capsys.readouterr().out == "## Title\n### Section\n```\n# Not a title\n```\n\n"
    )


def test_cli_markdown_strips_language_fence(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py"])

    g.md("```python\nprint('hello')\n```")

    assert capsys.readouterr().out == "print('hello')\n\n"


def test_cli_markdown_preserves_separate_inline_code_spans(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py"])

    g.md("`first` and `second`")

    assert capsys.readouterr().out == "`first` and `second`\n\n"


def test_cli_markdown_preserves_separate_fenced_blocks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py"])

    # Two separate fenced blocks: the first and last lines are fences, but
    # they do not wrap the whole text, so nothing should be stripped.
    text = "```\na = 1\n```\nprose between blocks\n```\nb = 2\n```"
    g.md(text)

    assert capsys.readouterr().out == f"{text}\n\n"


def test_subgroup_markdown_heading_offset_is_configurable(
    capsys: pytest.CaptureFixture[str],
) -> None:
    g = Group(cli_args=["script.py"])
    same_level = g.subgroup("same", markdown_heading_offset=0)
    deeper = g.subgroup("deeper", markdown_heading_offset=2)

    same_level.md("# Same")
    deeper.md("# Deeper")

    assert capsys.readouterr().out == "# Same\n\n### Deeper\n\n"
