import dataclasses
import typing

import marimo as mo

from . import _options


@dataclasses.dataclass
class QueryParams:
    params: typing.Any | None
    prefix: str = ""

    @classmethod
    def from_notebook(cls) -> "QueryParams":
        return cls(mo.query_params() if mo.running_in_notebook() else None)

    def subgroup(self, prefix: str) -> "QueryParams":
        return type(self)(
            params=self.params,
            prefix=f"{self.prefix}.{prefix}" if self.prefix else prefix,
        )

    def get(self, key: str) -> str | None:
        params = self.params
        if params is None:
            return None
        raw: typing.Any = params.get(self._key(key))
        if raw is None:
            return None
        if isinstance(raw, list):
            return str(typing.cast(object, raw[-1])) if raw else None
        return str(typing.cast(object, raw))

    def has_user_params(self) -> bool:
        params = self.params
        if params is None:
            return False
        return any(self._is_user_key(str(key)) for key in params)

    def sync(
        self,
        control: _options.InputControl,
        key: str,
        value: typing.Any,
    ) -> None:
        self._set(key, control.format_query_value(value))

    def on_change(
        self,
        control: _options.InputControl,
        key: str,
        on_change: typing.Callable[[typing.Any], None] | None,
        *,
        disabled: bool,
    ) -> typing.Callable[[typing.Any], None] | None:
        if self.params is None or disabled:
            return on_change

        def synced_on_change(value: typing.Any) -> None:
            self._set(key, control.format_query_value(value))
            if on_change is not None:
                on_change(value)

        return synced_on_change

    def _key(self, key: str) -> str:
        return f"{self.prefix}.{key}" if self.prefix else key

    def _is_user_key(self, key: str) -> bool:
        if key == "file":
            return False
        if not self.prefix:
            return True
        return key.startswith(f"{self.prefix}.")

    def _set(self, key: str, value: str | None) -> None:
        params = self.params
        if params is None:
            return
        key = self._key(key)
        if value is None:
            remove = getattr(params, "remove", None)
            if callable(remove):
                remove(key)
            else:
                typing.cast(typing.MutableMapping[str, typing.Any], params).pop(
                    key, None
                )
        else:
            params[key] = value
