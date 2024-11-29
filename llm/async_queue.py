import asyncio

from collections import deque

class AsyncQueueDequeueInterrupted(Exception):
    def __init__(self, message="AsyncQueue dequeue was interrupted"):
        self.message = message
        super().__init__(self.message)

class AsyncQueue:
    def __init__(self) -> None:
        self._data = deque([])
        self._presence_of_data = asyncio.Event()

    def enqueue(self, value):
        self._data.append(value)

        if len(self._data) == 1:
            self._presence_of_data.set()

    async def dequeue(self):
        await self._presence_of_data.wait()

        if len(self._data) < 1:
            raise AsyncQueueDequeueInterrupted("AsyncQueue was dequeue was interrupted")

        result = self._data.popleft()

        if not self._data:
            self._presence_of_data.clear()

        return result

    def size(self):
        result = len(self._data)
        return result

    def shutdown(self):
        self._presence_of_data.set()
