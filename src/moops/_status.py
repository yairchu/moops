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
        show_rate: bool = True,
        show_eta: bool = True,
        remove_on_exit: bool = False,
        disabled: bool = False,
    ) -> None:
        del show_rate, show_eta
        if collection is not None and total is None:
            if not isinstance(collection, collections.abc.Sized):
                raise TypeError("Cannot determine length; pass total")
            total = len(collection)
        if total is None:
            raise ValueError("total is required")
        self.collection = collection
        self.title = title
        self.subtitle = subtitle
        self.completion_title = completion_title
        self.completion_subtitle = completion_subtitle
        self.total = total
        self.current = 0
        self.disabled = disabled
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
        if self.collection is None:
            raise RuntimeError("progress_bar needs a collection to iterate")
        if isinstance(self.collection, collections.abc.AsyncIterable):
            raise RuntimeError("Use async for with async collections")
        try:
            for item in self.collection:
                yield item
                self.update()
        finally:
            self.close()

    async def __aiter__(self) -> collections.abc.AsyncIterator[S]:
        if self.collection is None:
            raise RuntimeError("progress_bar needs a collection to iterate")
        if not isinstance(self.collection, collections.abc.AsyncIterable):
            raise RuntimeError("Use for with sync collections")
        try:
            async for item in self.collection:
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
        self.current += increment
        self.title = self.title if title is None else title
        self.subtitle = self.subtitle if subtitle is None else subtitle
        if self._bar is not None:
            self._bar.set_description_str(self._desc(), refresh=False)
            self._bar.update(increment)
        else:
            self._emit()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.completion_title is not None or self.completion_subtitle is not None:
            self.update(
                increment=0,
                title=self.completion_title,
                subtitle=self.completion_subtitle,
            )
        if self._bar is not None:
            self._bar.close()

    def _desc(self) -> str:
        label = self.title or "Progress"
        detail = f" - {self.subtitle}" if self.subtitle else ""
        return f"{label}{detail}"

    def _emit(self) -> None:
        if not self.disabled:
            print(f"{self._desc()}: {self.current}/{self.total}")


class Spinner:
    def __init__(
        self,
        title: str | None = None,
        subtitle: str | None = None,
        remove_on_exit: bool = True,
        *,
        disabled: bool = False,
    ) -> None:
        self.title = title
        self.subtitle = subtitle
        self.remove_on_exit = remove_on_exit
        self.disabled = disabled
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
            if self.remove_on_exit:
                self._clear_line()
            else:
                self._write_line(self._desc(), newline=True)
            return
        if not self.remove_on_exit:
            print("Done")

    def update(
        self,
        *,
        title: str | None = None,
        subtitle: str | None = None,
    ) -> None:
        self.title = self.title if title is None else title
        self.subtitle = self.subtitle if subtitle is None else subtitle
        if self._thread is not None:
            self._render_frame(next(self._frames))
        else:
            self._emit()

    def _desc(self) -> str:
        label = self.title or "Working"
        detail = f" - {self.subtitle}" if self.subtitle else ""
        return f"{label}{detail}"

    def _emit(self) -> None:
        if not self.disabled:
            print(self._desc())

    def _can_animate(self) -> bool:
        return (
            not self.disabled
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
