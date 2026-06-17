from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

_logger = logging.getLogger("boxim")


class EventEmitter:
    """事件发射器。

    提供同步/异步事件注册与触发机制，支持链式调用。

    示例：
        >>> emitter = EventEmitter()
        >>> emitter.on("data", lambda x: print(x))
        >>> import asyncio
        >>> asyncio.run(emitter.emit("data", "hello"))
        hello
    """

    def __init__(self) -> None:
        self._listeners: Dict[str, List[Callable[..., Any]]] = {}
        self._async_listeners: Dict[str, List[Callable[..., Any]]] = {}

    def on(self, event: str, callback: Callable[..., Any]) -> "EventEmitter":
        """注册事件监听器。

        根据回调是否为协程函数自动分组为同步或异步监听器。
        重复注册同一回调将被忽略。

        Args:
            event: 事件名称
            callback: 回调函数

        Returns:
            返回 self 以支持链式调用
        """
        if asyncio.iscoroutinefunction(callback):
            bucket = self._async_listeners.setdefault(event, [])
            if callback not in bucket:
                bucket.append(callback)
        else:
            bucket_sync = self._listeners.setdefault(event, [])
            if callback not in bucket_sync:
                bucket_sync.append(callback)
        return self

    def off(
        self,
        event: str,
        callback: Optional[Callable[..., Any]] = None,
    ) -> "EventEmitter":
        """移除事件监听器。

        Args:
            event: 事件名称
            callback: 要移除的回调；为 None 时移除该事件全部监听器

        Returns:
            返回 self 以支持链式调用
        """
        if callback is None:
            self._listeners.pop(event, None)
            self._async_listeners.pop(event, None)
            return self

        sync_bucket = self._listeners.get(event, [])
        if callback in sync_bucket:
            sync_bucket.remove(callback)

        async_bucket = self._async_listeners.get(event, [])
        if callback in async_bucket:
            async_bucket.remove(callback)

        return self

    def once(self, event: str, callback: Callable[..., Any]) -> "EventEmitter":
        """注册一次性事件监听器，触发后自动移除。

        Args:
            event: 事件名称
            callback: 回调函数

        Returns:
            返回 self 以支持链式调用
        """
        if asyncio.iscoroutinefunction(callback):

            async def _async_wrapper(*args: Any, **kwargs: Any) -> Any:
                self.off(event, _async_wrapper)
                return await callback(*args, **kwargs)

            return self.on(event, _async_wrapper)

        def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            self.off(event, _sync_wrapper)
            return callback(*args, **kwargs)

        return self.on(event, _sync_wrapper)

    async def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        """触发事件，依次调用同步和异步监听器。

        Args:
            event: 事件名称
            *args: 传递给监听器的位置参数
            **kwargs: 传递给监听器的关键字参数
        """
        for listener in list(self._listeners.get(event, [])):
            try:
                listener(*args, **kwargs)
            except Exception as exc:
                _logger.error("事件 %s 同步监听器异常: %s", event, exc)

        for listener in list(self._async_listeners.get(event, [])):
            try:
                await listener(*args, **kwargs)
            except Exception as exc:
                _logger.error("事件 %s 异步监听器异常: %s", event, exc)

    def emit_sync(self, event: str, *args: Any, **kwargs: Any) -> None:
        """仅触发同步监听器（不触发异步监听器）。

        Args:
            event: 事件名称
            *args: 传递给监听器的位置参数
            **kwargs: 传递给监听器的关键字参数
        """
        for listener in list(self._listeners.get(event, [])):
            try:
                listener(*args, **kwargs)
            except Exception as exc:
                _logger.error("事件 %s 同步监听器异常: %s", event, exc)


__all__ = ["EventEmitter"]
