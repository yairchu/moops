# /// script
# dependencies = [
#     "marimo>=0.23.1",
#     "moops>=0.13.5",
# ]
# ///

import marimo

__generated_with = "0.23.10"
app = marimo.App(width="medium")

with app.setup:
    import dataclasses
    from typing import Literal


@app.cell(hide_code=True)
def _(args):
    args.md(
        """
        # Dataclass config

        Field types determine whether controls allow an empty value.
        `list_style` and `report_year` are required values; `audience` and
        `word_budget` include `None` in their types and can be cleared.
        Try `--no-audience --no-word-budget` on the CLI, or inspect `--help`
        to see which fields offer a `--no-...` flag.
        """,
        notebook_only=True,
    )
    return


@app.cell
def _(args, report_config):
    interface = args.interface(*report_config.elements.values())
    interface
    return


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import moops

    return (moops,)


@app.class_definition
@dataclasses.dataclass(frozen=True)
class ReportConfig:
    title: str = "Quarterly review"
    list_style: Literal["bullets", "numbered"] = "bullets"
    audience: Literal["internal", "external"] | None = "internal"
    report_year: int = 2026
    word_budget: int | None = dataclasses.field(
        default=1200,
        metadata={"help_text": "Target word count; clear for no limit"},
    )
    sections: int = dataclasses.field(
        default=3,
        metadata={
            "help_text": "Number of report sections",
            "start": 1,
            "stop": 12,
        },
    )
    include_summary: bool = True


@app.cell
def _(moops):
    args = moops.Group()
    return (args,)


@app.cell
def _(args, mo):
    report_config = args.dataclass(ReportConfig)
    mo.callout(mo.vstack([args.md("## Parameters"), *report_config.values()]))
    return (report_config,)


@app.cell
def _(report_config):
    config = ReportConfig(**report_config.value)
    section_labels = [f"Section {i}" for i in range(1, config.sections + 1)]
    return config, section_labels


@app.cell
def _(args, config, section_labels):
    summary = "with summary" if config.include_summary else "without summary"
    audience = "general audience" if config.audience is None else config.audience
    budget = (
        "No word limit"
        if config.word_budget is None
        else f"Target: {config.word_budget} words"
    )
    section_lines = [
        f"{i}. {section}" if config.list_style == "numbered" else f"- {section}"
        for i, section in enumerate(section_labels, start=1)
    ]
    args.md(
        f"**{config.title} — {config.report_year}** ({summary})\n\n"
        f"Audience: {audience}. {budget}.\n\n" + "\n".join(section_lines)
    )
    return


if __name__ == "__main__":
    app.run()
