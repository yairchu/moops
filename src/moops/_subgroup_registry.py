"""Tracks live subgroup interfaces to detect missing args.interface() calls."""

import typing
import weakref

from . import interface


class SubgroupRegistry:
    """Tracks live subgroup interfaces to detect missing args.interface() calls."""

    def __init__(self) -> None:
        self._refs: dict[str, weakref.ReferenceType[interface.Interface]] = {}

    def register(self, iface: interface.Interface) -> None:
        self._refs = {
            prefix: ref for prefix, ref in self._refs.items() if ref() is not None
        }
        self._refs[iface.option_prefix] = weakref.ref(iface)

    def missing_options(self, controls: typing.Sequence[typing.Any]) -> list[str]:
        covered = {
            iface.option_prefix
            for ctrl in controls
            for iface in [interface.attached_interface(ctrl)]
            if iface is not None
        }
        missing: list[str] = []
        live_refs: dict[str, weakref.ReferenceType[interface.Interface]] = {}
        for prefix, ref in self._refs.items():
            iface = ref()
            if iface is None:
                continue
            live_refs[prefix] = ref
            if iface.option_prefix in covered:
                continue
            missing.extend(iface.input_options())
        self._refs = live_refs
        return missing
