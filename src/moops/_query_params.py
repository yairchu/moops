import dataclasses
import sys
import threading
import time
import typing
import weakref

import marimo as mo

from . import _options

_MARIMO_RESERVED_PARAMS = frozenset({"file"})

# Quiet period before a live edit is written to the URL. marimo turns every
# query-param write into a browser `history.pushState`, so writing on every
# `on_change` of a dragged slider floods the Back button (and trips the
# browser's pushState rate limit). Deferring until the control settles makes
# each deliberate stop a single history entry.
# TODO: drop this once marimo reports drag-end / replaces history state.
DEBOUNCE_SECONDS = 0.3


def escape_url_key(key: str) -> str:
    return f"{key}_" if key in _MARIMO_RESERVED_PARAMS else key


@dataclasses.dataclass
class QueryParams:
    # marimo's query-params object (mo.query_params()), or None outside a
    # notebook. Duck-typed: get / __setitem__ / __iter__, plus an optional
    # remove() used when clearing a key.
    params: typing.Any
    prefix: str = ""
    _changed_values: dict[str, _options.CachedEdit] = dataclasses.field(
        default_factory=dict[str, _options.CachedEdit]
    )

    @classmethod
    def from_notebook(cls) -> "QueryParams":
        params = mo.query_params() if mo.running_in_notebook() else None
        if params is not None:
            # A rerun reads the URL to restore control values, so edits still
            # waiting on the debounce must land first.
            _flush(params)
        return cls(params)

    def subgroup(self, prefix: str) -> "QueryParams":
        return type(self)(
            params=self.params,
            prefix=f"{self.prefix}.{prefix}" if self.prefix else prefix,
            _changed_values=self._changed_values,
        )

    def get(self, key: str) -> str | None:
        params = self.params
        if params is None:
            return None
        _flush(params)
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
        _flush(params)
        return any(self._is_user_key(str(key)) for key in params)

    def changed_value(self, key: str) -> _options.CachedEdit | None:
        key = self._key(key)
        return self._changed_values.get(key)

    def forget_changed_value(self, key: str) -> None:
        self._changed_values.pop(self._key(key), None)

    def sync(
        self,
        control: _options.InputControl,
        key: str,
        value: typing.Any,
    ) -> None:
        self._set(key, control.format_query_value(value))

    def clear(self, key: str) -> None:
        self._set(key, None)

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
            if not control.accepts_live_value(value):
                return
            self._changed_values[self._key(key)] = control.cache_edit(value)
            self._set(key, control.format_query_value(value), debounce=True)
            if on_change is not None:
                on_change(value)

        return synced_on_change

    def _key(self, key: str) -> str:
        full = f"{self.prefix}.{key}" if self.prefix else key
        return escape_url_key(full)

    def _is_user_key(self, key: str) -> bool:
        if key == "file":
            return False
        return not self.prefix or key.startswith(f"{self.prefix}.")

    def _set(self, key: str, value: str | None, *, debounce: bool = False) -> None:
        params = self.params
        if params is None:
            return
        key = self._key(key)
        if debounce and _can_defer_writes():
            _deferred_writes(params).schedule(key, value)
        else:
            _flush(params)
            _write(params, key, value)


def _write(params: typing.Any, key: str, value: str | None) -> None:
    if value is None:
        remove = getattr(params, "remove", None)
        if callable(remove):
            remove(key)
        else:
            params.pop(key, None)
    elif params.get(key) != value:
        # Unchanged writes would still add a browser history entry.
        params[key] = value


def _can_defer_writes() -> bool:
    """Deferred writes need a `mo.Thread`, which can only reach the frontend
    from inside a running marimo kernel cell. Elsewhere (scripts, tests with
    fake params, Pyodide's cooperative threads) write immediately.
    """
    if sys.platform == "emscripten":
        return False
    try:
        from marimo._runtime.context import get_context
        from marimo._runtime.context.kernel_context import KernelRuntimeContext

        ctx = get_context()
    except Exception:
        return False
    return isinstance(ctx, KernelRuntimeContext) and ctx.cell_id is not None


class _DeferredWrites:
    """Pending URL writes for one marimo query-params object, flushed by a
    `mo.Thread` once no new edit arrived for `DEBOUNCE_SECONDS`.
    """

    def __init__(self, params: typing.Any) -> None:
        self._params = params
        # Held while writing too, so a reader that flushes never observes a
        # half-applied batch taken by the flusher thread.
        self._lock = threading.RLock()
        self._pending: dict[str, str | None] = {}
        self._deadline = 0.0
        self._flusher: mo.Thread | None = None

    def schedule(self, key: str, value: str | None) -> None:
        with self._lock:
            self._pending[key] = value
            self._deadline = time.monotonic() + DEBOUNCE_SECONDS
            if self._flusher is None:
                self._flusher = mo.Thread(target=self._run, daemon=True)
                self._flusher.start()

    def flush(self) -> None:
        with self._lock:
            pending, self._pending = self._pending, {}
            for key, value in pending.items():
                _write(self._params, key, value)

    def _run(self) -> None:
        thread = mo.current_thread()
        while True:
            with self._lock:
                remaining = self._deadline - time.monotonic()
                # should_exit: the controls' cell was invalidated; write now
                # rather than leave the URL behind the live values.
                if remaining <= 0 or thread.should_exit:
                    self._flusher = None
                    self.flush()
                    return
            time.sleep(min(remaining, 0.05))


_DEFERRED: "weakref.WeakKeyDictionary[typing.Any, _DeferredWrites]" = (
    weakref.WeakKeyDictionary()
)


def _deferred_writes(params: typing.Any) -> _DeferredWrites:
    writes = _DEFERRED.get(params)
    if writes is None:
        writes = _DEFERRED[params] = _DeferredWrites(params)
    return writes


def _flush(params: typing.Any) -> None:
    try:
        writes = _DEFERRED.get(params)
    except TypeError:  # unhashable / non-weakrefable fake params
        return
    if writes is not None:
        writes.flush()
