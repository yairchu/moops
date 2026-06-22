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


@app.cell(hide_code=True)
def _(args):
    args.md("# Dataclass config", notebook_only=True)
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
    args.md(
        f"**{config.title}** ({summary})\n\n"
        + "\n".join(f"- {section}" for section in section_labels)
    )
    return


if __name__ == "__main__":
    app.run()
