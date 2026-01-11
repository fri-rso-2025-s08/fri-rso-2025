import asyncio
from collections.abc import Awaitable, Callable
from typing import Literal


class AsyncValue[T]:
    _value: T
    _avail: asyncio.Event

    def __init__(self, value: T) -> None:
        self._value = value
        self._avail = asyncio.Event()

    async def put(self, value: T):
        self._value = value
        self._avail.set()
        self._avail = asyncio.Event()

    def get(self) -> tuple[T, Callable[[], Awaitable[Literal[True]]]]:
        return self._value, self._avail.wait
