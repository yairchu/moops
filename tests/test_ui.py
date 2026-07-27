import pathlib

from moops import Group, ui


def test_fold_uses_control_label_and_value_and_lazily_retains_control(
    tmp_path: pathlib.Path,
) -> None:
    selected = tmp_path / "input.html"
    selected.write_text("input")
    control = Group(cli_args=["script.py"]).file_browser(
        value=selected,
        multiple=False,
        option="--input",
        label="Input <file>",
        help_text="File to process",
    )

    folded = ui.fold(control)
    rendered = folded.text

    assert "Input &lt;file&gt;" in rendered
    assert f"<strong>{selected}</strong>" in rendered
    assert "marimo-lazy" in rendered
    assert folded._children[0]._element is control  # type: ignore[reportPrivateUsage]
    assert ".moops-fold[open] > summary .moops-fold-collapsed" in rendered
