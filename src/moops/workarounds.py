"""Workarounds for limitations in marimo's async execution model."""

import asyncio
import concurrent.futures
import typing


def run_in_thread_if_in_async(
    fn: typing.Callable[..., typing.Any],
    *args: typing.Any,
    **kwargs: typing.Any,
) -> typing.Any:
    """Call fn(*args, **kwargs), using a thread only when inside a running event loop.

    Marimo runs notebook cells as async coroutines, so any call to
    ``asyncio.run()`` from within a cell raises::

        RuntimeError: asyncio.run() cannot be called from a running event loop

    This helper detects that situation and offloads the call to a worker thread
    that has its own fresh event loop, avoiding the conflict.
    Outside an async context the function is called directly with no overhead.

    See marimo issues:
    * https://github.com/marimo-team/marimo/issues/9572
    * https://github.com/marimo-team/marimo/issues/9646
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return fn(*args, **kwargs)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(fn, *args, **kwargs).result()
