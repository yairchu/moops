import inspect
import typing

import marimo as mo

from moops import Group


def test_group_ui_method_signatures_match_marimo() -> None:
    group_names = {
        name for name, _ in inspect.getmembers(Group, predicate=inspect.isfunction)
    }
    marimo_names = {name for name in dir(mo.ui) if not name.startswith("_")}
    shared = group_names & marimo_names

    # Some Group methods intentionally deviate from marimo signatures;
    # table only supports a specific subset of marimo's input types.
    signature_whitelist = {"table"}

    mismatches = {
        name: mismatches
        for name in shared
        if name not in signature_whitelist
        for mismatches in [
            _signature_mismatches(getattr(Group, name), getattr(mo.ui, name))
        ]
        if mismatches
    }

    assert not mismatches, "\n".join(
        [
            "Group UI method signature mismatches:\n",
            *[
                f"{name}: {'; '.join(method_mismatches)}"
                for name, method_mismatches in mismatches.items()
            ],
        ]
    )


def _signature_mismatches(
    group_func: typing.Callable[..., typing.Any],
    marimo_func: typing.Callable[..., typing.Any],
) -> list[str]:
    [*group_params] = inspect.signature(group_func).parameters.values()
    if group_params and group_params[0].name == "self":
        group_params = group_params[1:]

    moops_only = {"flag", "option", "help_text"}
    group_params = [param for param in group_params if param.name not in moops_only]
    group_params_by_name = {
        param.name: param
        for param in group_params
        if param.kind
        not in {
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        }
    }
    has_var_keyword = any(
        param.kind is inspect.Parameter.VAR_KEYWORD for param in group_params
    )
    mismatches: list[str] = []

    group_index = 0
    past_unsupported_disabled = False
    for mo_param in inspect.signature(marimo_func).parameters.values():
        if mo_param.kind is inspect.Parameter.KEYWORD_ONLY:
            g_param = group_params_by_name.get(mo_param.name)
            if g_param is None:
                if has_var_keyword:
                    continue
                mismatches.append(f"missing keyword-only param {mo_param.name!r}")
                continue
            mismatches.extend(_param_mismatches(group_func.__name__, g_param, mo_param))
            continue
        if (
            mo_param.name == "disabled"
            and group_index < len(group_params)
            and group_params[group_index].name != "disabled"
        ):
            past_unsupported_disabled = True
            continue
        if past_unsupported_disabled and mo_param.kind in {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        }:
            continue
        if group_index >= len(group_params):
            mismatches.append(f"missing param {mo_param.name!r} at index {group_index}")
            continue
        g_param = group_params[group_index]
        if g_param.kind in [
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ]:
            return mismatches
        if g_param.kind is not mo_param.kind or g_param.name != mo_param.name:
            mismatches.append(
                f"index {group_index}: expected "
                f"{mo_param.kind.name} {mo_param.name!r}, "
                f"got {g_param.kind.name} {g_param.name!r}"
            )
            group_index += 1
            continue
        mismatches.extend(_param_mismatches(group_func.__name__, g_param, mo_param))
        group_index += 1
    return mismatches


def _param_mismatches(
    group_method_name: str,
    group_param: inspect.Parameter,
    marimo_param: inspect.Parameter,
) -> list[str]:
    name = marimo_param.name
    if group_param.kind is not marimo_param.kind:
        return [
            f"kind mismatch for {name!r}: "
            f"group={group_param.kind.name}, marimo={marimo_param.kind.name}"
        ]
    if group_param.name == "label" or (
        group_method_name == "file_browser" and group_param.name == "on_change"
    ):
        return []
    mismatches: list[str] = []
    if group_param.default != marimo_param.default:
        mismatches.append(
            f"default mismatch for {name!r}: "
            f"group={group_param.default!r}, marimo={marimo_param.default!r}"
        )
    if _annotation_text(group_param) != _annotation_text(marimo_param):
        mismatches.append(
            f"annotation mismatch for {name!r}: "
            f"group={_annotation_text(group_param)!r}, "
            f"marimo={_annotation_text(marimo_param)!r}"
        )
    return mismatches


def _annotation_text(param: inspect.Parameter) -> str:
    annotation = param.annotation
    if annotation is inspect.Parameter.empty:
        return ""
    return str(annotation).replace("typing.", "").replace("pathlib.Path", "Path")
