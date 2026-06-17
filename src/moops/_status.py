from __future__ import annotations

import collections.abc
import itertools
import sys
import threading
import typing

try:
    from tqdm.auto import tqdm
except ImportError:
    tqdm = None  # type: ignore[assignment]

S = typing.TypeVar("S")


class DisabledSpinner:
    def __enter__(self) -> DisabledSpinner:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: typing.Any,
    ) -> None:
        del exc_type, exc_value, traceback

    def update(
        self,
        *,
        title: str | None = None,
        subtitle: str | None = None,
    ) -> None:
        del title, subtitle

    def close(self) -> None:
        pass


class ProgressBar(typing.Generic[S]):
    def __init__(
        self,
        collection: (
            collections.abc.Collection[S]
            | collections.abc.Iterator[S]
            | collections.abc.AsyncIterable[S]
            | None
        ) = None,
        *,
        title: str | None = None,
        subtitle: str | None = None,
        completion_title: str | None = None,
        completion_subtitle: str | None = None,
        total: int | None = None,
        remove_on_exit: bool = False,
        disabled: bool = False,
        **kwargs: typing.Any,
    ) -> None:
        if collection is not None and total is None:
            if not isinstance(collection, collections.abc.Sized):
                raise TypeError("Cannot determine length; pass total")
            total = len(collection)
        if total is None:
            raise ValueError("total is required")
        self._collection = collection
        self._title = title
        self._subtitle = subtitle
        self._completion_title = completion_title
        self._completion_subtitle = completion_subtitle
        self._total = total
        self._current = 0
        self._disabled = disabled
        self._closed = False
        self._bar = (
            None
            if tqdm is None
            else tqdm(
                total=total,
                desc=self._desc(),
                disable=disabled,
                leave=not remove_on_exit,
            )
        )
        if self._bar is None:
            self._emit()

    def __iter__(self) -> collections.abc.Iterator[S]:
        if self._collection is None:
            raise RuntimeError("progress_bar needs a collection to iterate")
        if isinstance(self._collection, collections.abc.AsyncIterable):
            raise RuntimeError("Use async for with async collections")
        try:
            for item in self._collection:
                yield item
                self.update()
        finally:
            self.close()

    async def __aiter__(self) -> collections.abc.AsyncIterator[S]:
        if self._collection is None:
            raise RuntimeError("progress_bar needs a collection to iterate")
        if not isinstance(self._collection, collections.abc.AsyncIterable):
            raise RuntimeError("Use for with sync collections")
        try:
            async for item in self._collection:
                yield item
                self.update()
        finally:
            self.close()

    def __enter__(self) -> ProgressBar[S]:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: typing.Any,
    ) -> None:
        del exc_type, exc_value, traceback
        self.close()

    def update(
        self,
        *,
        increment: int = 1,
        title: str | None = None,
        subtitle: str | None = None,
    ) -> None:
        self._current += increment
        self._title = self._title if title is None else title
        self._subtitle = self._subtitle if subtitle is None else subtitle
        if self._bar is not None:
            self._bar.set_description_str(self._desc(), refresh=False)
            self._bar.update(increment)
        else:
            self._emit()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._completion_title is not None or self._completion_subtitle is not None:
            self.update(
                increment=0,
                title=self._completion_title,
                subtitle=self._completion_subtitle,
            )
        if self._bar is not None:
            self._bar.close()

    def _desc(self) -> str:
        label = self._title or "Progress"
        detail = f" - {self._subtitle}" if self._subtitle else ""
        return f"{label}{detail}"

    def _emit(self) -> None:
        if not self._disabled:
            print(f"{self._desc()}: {self._current}/{self._total}")


class Spinner:
    def __init__(
        self,
        title: str | None = None,
        subtitle: str | None = None,
        remove_on_exit: bool = True,
        *,
        disabled: bool = False,
    ) -> None:
        self._title = title
        self._subtitle = subtitle
        self._remove_on_exit = remove_on_exit
        self._disabled = disabled
        self._stream = sys.stderr
        self._closed = False
        self._rendered_len = 0
        self._frames = itertools.cycle("-\\|/")
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        if self._can_animate():
            self._render_frame(next(self._frames))
            self._thread = threading.Thread(target=self._animate, daemon=True)
            self._thread.start()
        else:
            self._emit()

    def __enter__(self) -> Spinner:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: typing.Any,
    ) -> None:
        del exc_type, exc_value, traceback
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._thread is not None:
            self._stop.set()
            self._thread.join(timeout=0.5)
            if self._remove_on_exit:
                self._clear_line()
            else:
                self._write_line(self._desc(), newline=True)
            return
        if not self._remove_on_exit:
            print("Done")

    def update(
        self,
        *,
        title: str | None = None,
        subtitle: str | None = None,
    ) -> None:
        self._title = self._title if title is None else title
        self._subtitle = self._subtitle if subtitle is None else subtitle
        if self._thread is not None:
            self._render_frame(next(self._frames))
        else:
            self._emit()

    def _desc(self) -> str:
        label = self._title or "Working"
        detail = f" - {self._subtitle}" if self._subtitle else ""
        return f"{label}{detail}"

    def _emit(self) -> None:
        if not self._disabled:
            print(self._desc())

    def _can_animate(self) -> bool:
        return (
            not self._disabled
            and hasattr(self._stream, "isatty")
            and self._stream.isatty()
        )

    def _animate(self) -> None:
        while not self._stop.wait(0.1):
            self._render_frame(next(self._frames))

    def _render_frame(self, frame: str) -> None:
        self._write_line(f"{frame} {self._desc()}")

    def _write_line(self, text: str, *, newline: bool = False) -> None:
        padded = text.ljust(self._rendered_len)
        self._stream.write("\r" + padded + ("\n" if newline else ""))
        self._stream.flush()
        self._rendered_len = max(self._rendered_len, len(text))

    def _clear_line(self) -> None:
        if self._rendered_len:
            self._stream.write("\r" + (" " * self._rendered_len) + "\r")
            self._stream.flush()
