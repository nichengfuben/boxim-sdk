from __future__ import annotations

import asyncio
import json
import logging
import random
import ssl
from typing import Any, Callable, Dict, List, Optional, Union

import websockets
import websockets.exceptions

from boxim.util.config import SDKConfig
from boxim.util.enums import MessageType, WebSocketCommand
from boxim.util.events import EventEmitter
from boxim.util.exceptions import AuthError, NetworkError
from boxim.util.protocols import TokenStore

_logger = logging.getLogger("boxim")

MessageHandler = Callable[[Dict[str, Any], bool], None]
AsyncMessageHandler = Callable[[Dict[str, Any], bool], Any]


class WebSocketTransport(EventEmitter):
    """WebSocket 传输层。

    负责 WebSocket 连接管理、身份认证、消息分发、心跳保活和自动重连。

    发布的事件：
        - "connected": 连接建立成功
        - "disconnected": 连接断开
        - "authenticated": 认证成功
        - "message": 收到消息 (msg_data, is_group)
        - "private_message": 收到私聊消息 (msg_data)
        - "group_message": 收到群聊消息 (msg_data)
        - "rtc_message": 收到 RTC 信令消息 (msg_data, is_group)
        - "system_message": 收到系统消息 (msg_data)
        - "online_status": 在线状态变更 (msg_data)
        - "force_offline": 被强制下线 (msg_data)
        - "error": 发生异常 (exception)
        - "reconnecting": 正在重连 (attempt, delay)
    """

    def __init__(
        self,
        config: SDKConfig,
        token_store: Optional[TokenStore] = None,
    ) -> None:
        super().__init__()
        self._config = config
        self._token_store = token_store
        self._ws: Optional[Any] = None
        self._sync_handlers: List[MessageHandler] = []
        self._async_handlers: List[AsyncMessageHandler] = []
        self._running = False
        self._task: Optional[asyncio.Task[None]] = None
        self._heartbeat_task: Optional[asyncio.Task[None]] = None
        self._reconnect_count = 0
        self._connected = False
        self._filter_online_status = True
        self._bot_user_id: Optional[int] = None

    @property
    def is_connected(self) -> bool:
        """WebSocket 是否处于已连接状态。"""
        return self._connected and self._ws is not None

    @property
    def is_running(self) -> bool:
        """监听循环是否正在运行。"""
        return self._running

    def add_handler(
        self,
        handler: Union[MessageHandler, AsyncMessageHandler],
    ) -> None:
        """添加消息处理器，重复添加将被忽略。

        Args:
            handler: 同步或异步消息处理函数 (msg_data, is_group)
        """
        if asyncio.iscoroutinefunction(handler):
            if handler not in self._async_handlers:
                self._async_handlers.append(handler)
        else:
            if handler not in self._sync_handlers:
                self._sync_handlers.append(handler)

    def remove_handler(
        self,
        handler: Union[MessageHandler, AsyncMessageHandler],
    ) -> None:
        """移除已注册的消息处理器。

        Args:
            handler: 要移除的消息处理函数
        """
        if asyncio.iscoroutinefunction(handler):
            if handler in self._async_handlers:
                self._async_handlers.remove(handler)
        else:
            if handler in self._sync_handlers:
                self._sync_handlers.remove(handler)

    def set_filter_online_status(self, enabled: bool) -> None:
        """设置是否过滤在线状态消息（不派发给普通处理器）。

        Args:
            enabled: True 表示过滤，False 表示透传
        """
        self._filter_online_status = enabled

    def set_bot_user_id(self, user_id: int) -> None:
        """设置 bot 自身的 user_id，用于过滤自身发送的消息。

        登录成功后由 BoxIM 主类调用，WebSocket 消息分发时会检查 sendId
        是否与 bot_user_id 相同，相同则跳过，避免 bot 自己的消息被当作
        新消息重复处理。

        Args:
            user_id: bot 自身的用户 ID
        """
        self._bot_user_id = user_id
        _logger.debug("已设置 bot user_id: %s", user_id)

    async def connect(self) -> None:
        """建立 WebSocket 连接并完成身份认证。

        Raises:
            AuthError: 令牌未设置或认证失败
            NetworkError: 连接建立失败
        """
        ssl_context = self._build_ssl_context()
        token = self._resolve_access_token()
        if not token:
            raise AuthError("访问令牌未设置，请先登录")

        try:
            self._ws = await websockets.connect(
                self._config.ws_url,
                ssl=ssl_context,
                ping_interval=self._config.ws_ping_interval,
                ping_timeout=self._config.ws_ping_timeout,
            )
            await self._authenticate(token)
        except AuthError:
            raise
        except Exception as exc:
            _logger.error("WebSocket 连接失败: %s", exc)
            raise NetworkError(f"WebSocket 连接失败: {exc}") from exc

    def _build_ssl_context(self) -> ssl.SSLContext:
        """构建 SSL 上下文。

        Returns:
            ssl.SSLContext: 配置好的 SSL 上下文
        """
        ctx = ssl.create_default_context()
        if not self._config.ssl_verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def _resolve_access_token(self) -> Optional[str]:
        """多途径获取访问令牌。

        Returns:
            访问令牌字符串，不存在时返回 None
        """
        import os

        if self._token_store is not None:
            token_info = self._token_store.get_token()
            if token_info is not None and token_info.access_token:
                return token_info.access_token
            if hasattr(self._token_store, "get"):
                raw = self._token_store.get("ACCESS_TOKEN")  # type: ignore[attr-defined]
                if raw:
                    return str(raw)
        return os.environ.get("ACCESS_TOKEN")

    async def _authenticate(self, token: str) -> None:
        """发送认证消息并等待服务端响应。

        Args:
            token: 访问令牌

        Raises:
            AuthError: 认证失败或响应超时
        """
        auth_msg = json.dumps(
            {"cmd": WebSocketCommand.AUTH, "data": {"accessToken": token, "devId": random.randint(0, 999999)}}
        )
        await self._ws.send(auth_msg)
        _logger.debug("WebSocket 认证消息已发送")

        try:
            raw = await asyncio.wait_for(
                self._ws.recv(),
                timeout=self._config.ws_auth_timeout,
            )
        except asyncio.TimeoutError as exc:
            raise AuthError("认证响应超时") from exc

        try:
            resp = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AuthError("认证响应解析失败") from exc

        if resp is None:
            raise AuthError("服务器返回空响应")

        cmd = resp.get("cmd")
        if cmd == WebSocketCommand.AUTH:
            err = resp.get("data") or {}
            err_code = err.get("code") if isinstance(err, dict) else None
            if err_code is not None and err_code != 200:
                raise AuthError(
                    f"认证失败: {err.get('message', '未知错误')}"
                )

        self._connected = True
        self._reconnect_count = 0
        _logger.info("WebSocket 认证成功")
        await self.emit("connected")
        await self.emit("authenticated")

    async def start(self) -> None:
        """启动消息监听循环（非阻塞）。

        重复调用无副作用。
        """
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._listen_loop())

    async def stop(self) -> None:
        """停止消息监听，关闭 WebSocket 连接并释放资源。"""
        self._running = False
        self._connected = False

        await self._cancel_task(self._heartbeat_task)
        self._heartbeat_task = None

        await self._cancel_task(self._task)
        self._task = None

        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        await self.emit("disconnected")

    async def send(self, data: Dict[str, Any]) -> None:
        """发送 WebSocket 消息。

        Args:
            data: 要发送的消息字典
        """
        if self._ws is not None:
            await self._ws.send(json.dumps(data))

    @staticmethod
    async def _cancel_task(
        task: Optional[asyncio.Task[Any]],
    ) -> None:
        """安全取消并等待 asyncio 任务。

        Args:
            task: 要取消的任务，为 None 时无操作
        """
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _listen_loop(self) -> None:
        """消息监听主循环，自动处理重连逻辑。"""
        _logger.info("WebSocket 监听循环已启动")

        while self._running:
            try:
                if not self._ws or not self._connected:
                    _logger.info("WebSocket 未连接，尝试连接...")
                    await self.connect()
                    self._heartbeat_task = asyncio.create_task(
                        self._heartbeat_loop()
                    )

                try:
                    if self._ws is not None:
                        async for raw_message in self._ws:
                            if not self._running:
                                break
                            await self._process_raw_message(raw_message)
                finally:
                    await self._cancel_task(self._heartbeat_task)
                    self._heartbeat_task = None

            except websockets.exceptions.ConnectionClosed as exc:
                self._connected = False
                self._ws = None
                _logger.warning("WebSocket 连接关闭: %s", exc)
                await self.emit("disconnected")

                if not self._running or not self._config.ws_auto_reconnect:
                    break
                await self._wait_for_reconnect()

            except Exception as exc:
                self._connected = False
                self._ws = None
                _logger.error("WebSocket 异常: %s", exc)
                await self.emit("error", exc)

                if not self._running or not self._config.ws_auto_reconnect:
                    break
                await self._wait_for_reconnect()

    async def _wait_for_reconnect(self) -> None:
        """等待重连延迟并更新重连计数。"""
        delay = self._calculate_reconnect_delay()
        self._reconnect_count += 1
        _logger.info(
            "将在 %s 秒后重连 (第 %s 次)...",
            delay,
            self._reconnect_count,
        )
        await self.emit("reconnecting", self._reconnect_count, delay)
        await asyncio.sleep(delay)

    def _calculate_reconnect_delay(self) -> float:
        """计算指数退避重连延迟。

        Returns:
            重连延迟秒数，不超过最大值
        """
        delay = self._config.ws_reconnect_delay * (2**self._reconnect_count)
        return min(delay, self._config.ws_max_reconnect_delay)

    async def _process_raw_message(self, raw_message: str) -> None:
        """解析并路由原始 WebSocket 消息。

        Args:
            raw_message: 原始 JSON 字符串
        """
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError:
            _logger.warning("无法解析 WebSocket 消息: %s", raw_message[:100])
            return

        cmd = data.get("cmd")
        msg_data = data.get("data", {})
        _logger.debug("收到 WebSocket 消息: cmd=%s", cmd)

        if cmd == WebSocketCommand.AUTH:
            _logger.debug("收到认证响应消息")
            return
        if cmd == WebSocketCommand.HEARTBEAT:
            _logger.debug("收到心跳响应消息")
            return
        if cmd == WebSocketCommand.FORCE_OFFLINE:
            _logger.warning("收到强制下线消息")
            await self.emit("force_offline", msg_data)
            return

        if cmd in (
            WebSocketCommand.PRIVATE_MESSAGE,
            WebSocketCommand.GROUP_MESSAGE,
        ):
            await self._dispatch_chat_message(msg_data, cmd)

    async def _dispatch_chat_message(
        self,
        msg_data: Dict[str, Any],
        cmd: int,
    ) -> None:
        """分发聊天消息到各事件频道和处理器。

        Args:
            msg_data: 消息数据字典
            cmd: WebSocket 命令类型
        """
        is_group = cmd == WebSocketCommand.GROUP_MESSAGE
        msg_type = msg_data.get("type", 0)

        if self._filter_online_status and msg_type == MessageType.ONLINE_STATUS:
            await self.emit("online_status", msg_data)
            return

        # 过滤 bot 自己发送的消息（BoxIM 服务端会将自身发送的消息通过 WebSocket 回推）
        if self._is_self_message(msg_data):
            _logger.debug(
                "跳过 bot 自身发送的消息: id=%s, sendId=%s",
                msg_data.get("id"),
                msg_data.get("sendId"),
            )
            return

        if self._is_rtc_message_type(msg_type):
            await self.emit("rtc_message", msg_data, is_group)

        if msg_type in (
            MessageType.SYSTEM_NOTIFICATION,
            MessageType.TIP_TEXT,
        ):
            await self.emit("system_message", msg_data)

        event_name = "group_message" if is_group else "private_message"
        await self.emit(event_name, msg_data)
        await self.emit("message", msg_data, is_group)
        await self._dispatch_to_handlers(msg_data, is_group)

        _logger.debug(
            "%s消息: id=%s, type=%s, sender=%s",
            "群聊" if is_group else "私聊",
            msg_data.get("id"),
            msg_type,
            msg_data.get("sendId"),
        )

    @staticmethod
    def _is_rtc_message_type(msg_type: int) -> bool:
        """判断消息类型是否属于 RTC 信令范围。

        Args:
            msg_type: 消息类型整数值

        Returns:
            是否为 RTC 信令消息
        """
        return (100 <= msg_type < 120) or (200 <= msg_type < 230)

    def _is_self_message(self, msg_data: Dict[str, Any]) -> bool:
        """检查消息是否为 bot 自己发送的。

        当 bot_user_id 已设置且消息的 sendId 与之相同时，判定为自身消息。
        BoxIM 服务端会将 bot 自身发送的消息通过 WebSocket 回推，
        不过滤会导致 bot 把自己的回复当作新消息重复处理。

        Args:
            msg_data: 消息数据字典

        Returns:
            是否为 bot 自身发送的消息
        """
        if self._bot_user_id is None:
            return False
        send_id = msg_data.get("sendId")
        if send_id is None:
            return False
        return send_id == self._bot_user_id

    async def _dispatch_to_handlers(
        self,
        msg_data: Dict[str, Any],
        is_group: bool,
    ) -> None:
        """将消息分发给所有注册的处理器。

        Args:
            msg_data: 消息数据字典
            is_group: 是否为群聊消息
        """
        for handler in list(self._sync_handlers):
            try:
                handler(msg_data, is_group)
            except Exception as exc:
                _logger.error("同步消息处理器异常: %s", exc)

        for handler in list(self._async_handlers):
            try:
                await handler(msg_data, is_group)
            except Exception as exc:
                _logger.error("异步消息处理器异常: %s", exc)

    async def _heartbeat_loop(self) -> None:
        """WebSocket 心跳保活循环。"""
        while self._running and self._connected:
            try:
                if self._ws is not None:
                    heartbeat = json.dumps(
                        {"cmd": WebSocketCommand.HEARTBEAT, "data": {}}
                    )
                    await self._ws.send(heartbeat)
                    _logger.debug("心跳已发送")
                await asyncio.sleep(self._config.ws_heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                _logger.warning("心跳发送失败: %s", exc)
                break


__all__ = ["WebSocketTransport"]
