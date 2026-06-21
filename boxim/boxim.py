from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Union

from boxim.util.rtc import RTCCallSession
from boxim.util.config import SDKConfig
from boxim.util.container import Container
from boxim.util.decorators import async_require_login, require_login
from boxim.util.env import EnvManager
from boxim.util.enums import (
    MessageType,
    QRLoginStatus,
    RegistrationMode,
    RTCMode,
    TerminalType,
)
from boxim.util.exceptions import AuthError, RTCError, ValidationError
from boxim.util.logging_util import setup_logging
from boxim.util.message_builder import MessageBuilder
from boxim.util.models import (
    CaptchaCode,
    Friend,
    FriendRequest,
    Group,
    Message,
    QRLoginInfo,
    Sticker,
    StickerAlbum,
    SystemConfig,
    SystemMessage,
    TokenInfo,
    User,
)
from boxim.util.protocols import TokenStore
from boxim.util.transport_http import HTTPTransport
from boxim.util.transport_ws import WebSocketTransport
from boxim.util.uploader import FileUploader

_logger = logging.getLogger("boxim")

MessageHandler = Callable[[Dict[str, Any], bool], None]
AsyncMessageHandler = Callable[[Dict[str, Any], bool], Any]


class BoxIM:
    """BoxIM SDK 主类。

    功能完整的即时通讯 SDK，支持：
    - 用户认证和管理（登录/注册/修改密码/重置密码/二维码登录）
    - 好友和群组管理（增删改查/权限/禁言/置顶/免打扰）
    - 消息收发（文本/图片/文件/语音/视频/贴纸/名片/合并转发）
    - WebSocket 实时消息（自动重连/心跳/事件驱动）
    - WebRTC 音视频通话（私聊/群聊/屏幕共享/流式处理/AI 实时流）
    - 离线消息拉取与历史记录查询
    - 好友请求管理与黑名单
    - 贴纸系统（专辑/自定义/搜索）
    - 验证码管理（图片/短信/邮件）
    - 投诉举报与系统配置
    - 依赖注入与高度可配置

    使用示例：
        >>> im = BoxIM().login("username", "password")
        >>> im.send_text(123, "你好")

        >>> async with BoxIM() as im:
        ...     await im.alogin("user", "pass")
        ...     await im.asend_text(123, "你好")
    """

    def __init__(
        self,
        config: Optional[SDKConfig] = None,
        container: Optional[Container] = None,
        token_store: Optional[TokenStore] = None,
        base_url: Optional[str] = None,
        ws_url: Optional[str] = None,
        auto_refresh_token: bool = True,
        debug: bool = False,
    ) -> None:
        """初始化 BoxIM 客户端。

        Args:
            config: SDK 配置（优先级最高，指定后忽略其他简便参数）
            container: 依赖注入容器
            token_store: 自定义令牌存储实现
            base_url: API 基础 URL（简便参数）
            ws_url: WebSocket URL（简便参数）
            auto_refresh_token: 是否自动刷新过期令牌
            debug: 是否开启调试模式（DEBUG 日志级别）
        """
        self._config = self._build_config(
            config, base_url, ws_url, auto_refresh_token, debug
        )
        self._container = container or Container()
        self._token_store = self._resolve_token_store(token_store)

        self._register_core_dependencies()

        self._http = HTTPTransport(self._config, self._token_store)
        self._container.register_singleton("http", self._http)

        self._ws = WebSocketTransport(self._config, self._token_store)
        self._container.register_singleton("ws", self._ws)

        self._uploader = FileUploader(self._http, self._config)
        self._container.register_singleton("uploader", self._uploader)

        self._active_calls: Dict[str, RTCCallSession] = {}

        self._logger = setup_logging(
            level=self._config.log_level,
            fmt=self._config.log_format,
        )

    @staticmethod
    def _build_config(
        config: Optional[SDKConfig],
        base_url: Optional[str],
        ws_url: Optional[str],
        auto_refresh_token: bool,
        debug: bool,
    ) -> SDKConfig:
        """构建 SDK 配置对象。

        Args:
            config: 外部传入的配置，优先使用
            base_url: API 基础 URL
            ws_url: WebSocket URL
            auto_refresh_token: 是否自动刷新令牌
            debug: 调试模式

        Returns:
            SDKConfig: 最终使用的配置对象
        """
        if config is not None:
            return config
        return SDKConfig(
            base_url=base_url or SDKConfig.base_url,
            ws_url=ws_url or SDKConfig.ws_url,
            auto_refresh_token=auto_refresh_token,
            debug=debug,
        )

    def _resolve_token_store(
        self, token_store: Optional[TokenStore]
    ) -> TokenStore:
        """解析令牌存储实现。

        优先级：显式传入 > 容器注册 > 默认 EnvManager。

        Args:
            token_store: 显式传入的令牌存储

        Returns:
            TokenStore: 解析到的令牌存储实现
        """
        if token_store is not None:
            return token_store
        if self._container.has("token_store"):
            return self._container.resolve("token_store")
        env = EnvManager()
        self._env = env
        return env  # type: ignore[return-value]

    def _register_core_dependencies(self) -> None:
        """向依赖注入容器注册核心依赖。"""
        self._container.register_singleton("config", self._config)
        self._container.register_singleton(
            "token_store", self._token_store
        )

    # ======================================================================
    # 属性访问
    # ======================================================================

    @property
    def config(self) -> SDKConfig:
        """获取 SDK 配置对象。"""
        return self._config

    @property
    def http(self) -> HTTPTransport:
        """获取 HTTP 传输层实例。"""
        return self._http

    @property
    def ws(self) -> WebSocketTransport:
        """获取 WebSocket 传输层实例。"""
        return self._ws

    @property
    def uploader(self) -> FileUploader:
        """获取文件上传器实例。"""
        return self._uploader

    @property
    def container(self) -> Container:
        """获取依赖注入容器。"""
        return self._container

    @property
    def token_store(self) -> TokenStore:
        """获取令牌存储实现。"""
        return self._token_store

    @property
    def active_calls(self) -> Dict[str, RTCCallSession]:
        """获取当前活跃通话会话字典（session_id -> RTCCallSession）。"""
        return self._active_calls

    # ======================================================================
    # 上下文管理器
    # ======================================================================

    def __enter__(self) -> "BoxIM":
        """进入同步上下文管理器。"""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """退出同步上下文管理器，释放同步资源。"""
        self.close()

    async def __aenter__(self) -> "BoxIM":
        """进入异步上下文管理器。"""
        return self

    async def __aexit__(
        self, exc_type: Any, exc_val: Any, exc_tb: Any
    ) -> None:
        """退出异步上下文管理器，释放所有资源。"""
        await self.aclose()

    def close(self) -> None:
        """关闭客户端，释放同步资源。"""
        self._http.close()

    async def aclose(self) -> None:
        """异步关闭客户端，结束活跃通话并释放所有资源。"""
        for call in list(self._active_calls.values()):
            if call.is_active:
                try:
                    await call.hangup()
                except Exception as exc:
                    _logger.warning("结束通话异常: %s", exc)

        await self._ws.stop()
        await self._http.aclose()

    # ======================================================================
    # 认证相关
    # ======================================================================

    def login(
        self,
        username: str,
        password: str,
        terminal: TerminalType = TerminalType.WEB,
    ) -> "BoxIM":
        """同步登录。

        Args:
            username: 用户名/邮箱/手机号
            password: 密码
            terminal: 终端类型

        Returns:
            返回 self 以支持链式调用

        示例：
            >>> im = BoxIM().login("user", "pass")
        """
        data = {
            "userName": username,
            "password": password,
            "terminal": int(terminal),
        }
        result = self._http.request("POST", "/api/login", json_data=data)
        token_info = TokenInfo.from_dict(result)
        self._token_store.save_token(token_info)

        user_info = self.get_me()
        self._save_user_id(user_info.get("id"))

        self._logger.info("登录成功: %s", username)
        return self

    async def alogin(
        self,
        username: str,
        password: str,
        terminal: TerminalType = TerminalType.WEB,
    ) -> "BoxIM":
        """异步登录。

        Args:
            username: 用户名/邮箱/手机号
            password: 密码
            terminal: 终端类型

        Returns:
            返回 self 以支持链式调用
        """
        data = {
            "userName": username,
            "password": password,
            "terminal": int(terminal),
        }
        result = await self._http.arequest(
            "POST", "/api/login", json_data=data
        )
        token_info = TokenInfo.from_dict(result)
        self._token_store.save_token(token_info)

        user_info = await self.aget_me()
        self._save_user_id(user_info.get("id"))

        self._logger.info("登录成功: %s", username)
        return self

    def _save_user_id(self, user_id: Any) -> None:
        """将用户 ID 持久化到令牌存储中（如果支持）。

        同时将 bot_user_id 设置到 WebSocket transport，
        用于过滤 bot 自身发送的消息，避免消息回推导致重复处理。

        Args:
            user_id: 用户 ID
        """
        if hasattr(self._token_store, "set"):
            self._token_store.set("USER_ID", user_id)  # type: ignore[attr-defined]
        # 同步到 WebSocket transport，过滤自身消息
        if self._ws is not None and user_id is not None:
            try:
                self._ws.set_bot_user_id(int(user_id))
            except (ValueError, TypeError):
                pass

    def register(
        self,
        mode: RegistrationMode,
        user_name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        code: Optional[str] = None,
        password: str = "",
        confirm_password: str = "",
        nick_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """用户注册。

        Args:
            mode: 注册方式（username/phone/email）
            user_name: 用户名（username 模式必填）
            phone: 手机号（phone 模式必填）
            email: 邮箱（email 模式必填）
            code: 验证码（phone/email 模式必填）
            password: 密码
            confirm_password: 确认密码
            nick_name: 昵称

        Returns:
            Dict[str, Any]: 注册结果

        Raises:
            ValidationError: 参数不满足注册模式要求
        """
        data = self._build_register_data(
            mode, user_name, phone, email, code,
            password, confirm_password, nick_name,
        )
        return self._http.request("POST", "/api/register", json_data=data)

    async def aregister(
        self,
        mode: RegistrationMode,
        user_name: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        code: Optional[str] = None,
        password: str = "",
        confirm_password: str = "",
        nick_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """异步用户注册。

        参数同 register()。
        """
        data = self._build_register_data(
            mode, user_name, phone, email, code,
            password, confirm_password, nick_name,
        )
        return await self._http.arequest(
            "POST", "/api/register", json_data=data
        )

    @staticmethod
    def _build_register_data(
        mode: RegistrationMode,
        user_name: Optional[str],
        phone: Optional[str],
        email: Optional[str],
        code: Optional[str],
        password: str,
        confirm_password: str,
        nick_name: Optional[str],
    ) -> Dict[str, Any]:
        """构建注册请求数据字典。

        Args:
            mode: 注册方式
            user_name: 用户名
            phone: 手机号
            email: 邮箱
            code: 验证码
            password: 密码
            confirm_password: 确认密码
            nick_name: 昵称

        Returns:
            Dict[str, Any]: 注册请求数据字典

        Raises:
            ValidationError: 参数不满足注册模式要求
        """
        data: Dict[str, Any] = {
            "mode": mode.value,
            "password": password,
            "confirmPassword": confirm_password,
        }

        if mode == RegistrationMode.USERNAME:
            if not user_name:
                raise ValidationError("用户名注册模式需要提供 user_name")
            data["userName"] = user_name
        elif mode == RegistrationMode.PHONE:
            if not phone or not code:
                raise ValidationError(
                    "手机号注册模式需要提供 phone 和 code"
                )
            data["phone"] = phone
            data["code"] = code
        elif mode == RegistrationMode.EMAIL:
            if not email or not code:
                raise ValidationError(
                    "邮箱注册模式需要提供 email 和 code"
                )
            data["email"] = email
            data["code"] = code

        if nick_name:
            data["nickName"] = nick_name

        return data

    @require_login
    def refresh_token(self) -> "BoxIM":
        """刷新访问令牌（同步）。

        Returns:
            返回 self 以支持链式调用

        Raises:
            AuthError: 无可用刷新令牌
        """
        token_info = self._token_store.get_token()
        if not token_info or not token_info.refresh_token:
            raise AuthError("没有可用的刷新令牌")

        result = self._http.request(
            "PUT",
            "/api/refreshToken",
            headers={"refreshToken": token_info.refresh_token},
        )
        self._token_store.save_token(TokenInfo.from_dict(result))
        self._logger.info("令牌刷新成功")
        return self

    @async_require_login
    async def arefresh_token(self) -> "BoxIM":
        """异步刷新访问令牌。

        Returns:
            返回 self 以支持链式调用

        Raises:
            AuthError: 无可用刷新令牌
        """
        token_info = self._token_store.get_token()
        if not token_info or not token_info.refresh_token:
            raise AuthError("没有可用的刷新令牌")

        result = await self._http.arequest(
            "PUT",
            "/api/refreshToken",
            headers={"refreshToken": token_info.refresh_token},
        )
        self._token_store.save_token(TokenInfo.from_dict(result))
        self._logger.info("令牌刷新成功")
        return self

    @require_login
    def modify_password(
        self, old_password: str, new_password: str
    ) -> Dict[str, Any]:
        """修改密码。

        Args:
            old_password: 旧密码
            new_password: 新密码

        Returns:
            Dict[str, Any]: 操作结果
        """
        data = {"oldPwd": old_password, "newPwd": new_password}
        return self._http.request("PUT", "/api/resetPwd", json_data=data)

    @async_require_login
    async def amodify_password(
        self, old_password: str, new_password: str
    ) -> Dict[str, Any]:
        """异步修改密码。

        Args:
            old_password: 旧密码
            new_password: 新密码

        Returns:
            Dict[str, Any]: 操作结果
        """
        data = {"oldPwd": old_password, "newPwd": new_password}
        return await self._http.arequest(
            "PUT", "/api/resetPwd", json_data=data
        )

    def reset_password(
        self,
        mode: RegistrationMode,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        code: str = "",
        password: str = "",
        confirm_password: str = "",
    ) -> Dict[str, Any]:
        """通过手机号或邮箱验证码重置密码。

        Args:
            mode: 重置方式（phone/email）
            phone: 手机号（phone 模式必填）
            email: 邮箱（email 模式必填）
            code: 验证码
            password: 新密码
            confirm_password: 确认密码

        Returns:
            Dict[str, Any]: 操作结果
        """
        data = self._build_reset_password_data(
            mode, phone, email, code, password, confirm_password
        )
        return self._http.request("PUT", "/api/resetPwd", json_data=data)

    async def areset_password(
        self,
        mode: RegistrationMode,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        code: str = "",
        password: str = "",
        confirm_password: str = "",
    ) -> Dict[str, Any]:
        """异步重置密码。

        参数同 reset_password()。
        """
        data = self._build_reset_password_data(
            mode, phone, email, code, password, confirm_password
        )
        return await self._http.arequest(
            "PUT", "/api/resetPwd", json_data=data
        )

    @staticmethod
    def _build_reset_password_data(
        mode: RegistrationMode,
        phone: Optional[str],
        email: Optional[str],
        code: str,
        password: str,
        confirm_password: str,
    ) -> Dict[str, Any]:
        """构建重置密码请求数据字典。

        Args:
            mode: 重置方式
            phone: 手机号
            email: 邮箱
            code: 验证码
            password: 新密码
            confirm_password: 确认密码

        Returns:
            Dict[str, Any]: 请求数据字典
        """
        data: Dict[str, Any] = {
            "mode": mode.value,
            "code": code,
            "password": password,
            "confirmPassword": confirm_password,
        }
        if mode == RegistrationMode.PHONE:
            data["phone"] = phone
        elif mode == RegistrationMode.EMAIL:
            data["email"] = email
        return data

    # ======================================================================
    # 二维码登录
    # ======================================================================

    def generate_qr_login(self) -> QRLoginInfo:
        """生成二维码登录信息。

        Returns:
            QRLoginInfo: 包含二维码内容、图片（base64）和过期时间的对象
        """
        data = self._http.request("POST", "/api/qrLogin/generate")
        return QRLoginInfo.from_dict(data)

    async def agenerate_qr_login(self) -> QRLoginInfo:
        """异步生成二维码登录信息。

        Returns:
            QRLoginInfo: 二维码登录信息对象
        """
        data = await self._http.arequest("POST", "/api/qrLogin/generate")
        return QRLoginInfo.from_dict(data)

    def check_qr_login_status(self, qr_code: str) -> Dict[str, Any]:
        """检查二维码登录状态。

        Args:
            qr_code: 二维码字符串

        Returns:
            Dict[str, Any]: 登录状态，确认后包含 accessToken
        """
        return self._http.request(
            "GET", f"/api/qrLogin/status/{qr_code}"
        )

    async def acheck_qr_login_status(self, qr_code: str) -> Dict[str, Any]:
        """异步检查二维码登录状态。

        Args:
            qr_code: 二维码字符串

        Returns:
            Dict[str, Any]: 登录状态
        """
        return await self._http.arequest(
            "GET", f"/api/qrLogin/status/{qr_code}"
        )

    def qr_login_wait(
        self,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> "BoxIM":
        """二维码登录（自动轮询等待扫码确认）。

        Args:
            poll_interval: 轮询间隔（秒）
            timeout: 超时时间（秒）

        Returns:
            返回 self 以支持链式调用

        Raises:
            AuthError: 登录超时或二维码已过期

        示例：
            >>> qr = im.generate_qr_login()
            >>> print(f"请扫描二维码: {qr.qr_image}")
            >>> im.qr_login_wait()
        """


        qr_info = self.generate_qr_login()
        self._logger.info(
            "二维码已生成，等待扫码... (过期时间: %ss)", qr_info.expires_in
        )

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                status = self.check_qr_login_status(qr_info.qr_code)
                if status and isinstance(status, dict):
                    login_info = status.get("loginInfo") or status
                    if login_info.get("accessToken"):
                        token_info = TokenInfo.from_dict(login_info)
                        self._token_store.save_token(token_info)
                        user_info = self.get_me()
                        self._save_user_id(user_info.get("id"))
                        self._logger.info("二维码登录成功")
                        return self
                    login_status = status.get("status", "")
                    if login_status == QRLoginStatus.EXPIRED.value:
                        raise AuthError("二维码已过期")
            except AuthError:
                raise
            except Exception as exc:
                _logger.debug("轮询二维码状态异常: %s", exc)

            time.sleep(poll_interval)

        raise AuthError("二维码登录超时")

    async def aqr_login_wait(
        self,
        poll_interval: float = 2.0,
        timeout: float = 300.0,
    ) -> "BoxIM":
        """异步二维码登录（自动轮询等待扫码确认）。

        Args:
            poll_interval: 轮询间隔（秒）
            timeout: 超时时间（秒）

        Returns:
            返回 self 以支持链式调用

        Raises:
            AuthError: 登录超时或二维码已过期
        """
        qr_info = await self.agenerate_qr_login()
        self._logger.info(
            "二维码已生成，等待扫码... (过期时间: %ss)", qr_info.expires_in
        )

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                status = await self.acheck_qr_login_status(qr_info.qr_code)
                if status and isinstance(status, dict):
                    login_info = status.get("loginInfo") or status
                    if login_info.get("accessToken"):
                        token_info = TokenInfo.from_dict(login_info)
                        self._token_store.save_token(token_info)
                        user_info = await self.aget_me()
                        self._save_user_id(user_info.get("id"))
                        self._logger.info("二维码登录成功")
                        return self
                    login_status = status.get("status", "")
                    if login_status == QRLoginStatus.EXPIRED.value:
                        raise AuthError("二维码已过期")
            except AuthError:
                raise
            except Exception as exc:
                _logger.debug("轮询二维码状态异常: %s", exc)

            await asyncio.sleep(poll_interval)

        raise AuthError("二维码登录超时")

    # ======================================================================
    # 用户相关
    # ======================================================================

    @require_login
    def get_me(self) -> Dict[str, Any]:
        """获取当前登录用户信息。

        Returns:
            Dict[str, Any]: 用户信息字典
        """
        return self._http.request("GET", "/api/user/self")

    @async_require_login
    async def aget_me(self) -> Dict[str, Any]:
        """异步获取当前登录用户信息。

        Returns:
            Dict[str, Any]: 用户信息字典
        """
        return await self._http.arequest("GET", "/api/user/self")

    @property
    def me(self) -> Dict[str, Any]:
        """当前登录用户信息（属性访问）。

        示例：
            >>> user_id = im.me["id"]
            >>> nickname = im.me["nickName"]
        """
        return self.get_me()

    @require_login
    def get_user(self, user_id: int) -> User:
        """根据 ID 获取用户信息。

        Args:
            user_id: 用户 ID

        Returns:
            User: 用户对象
        """
        data = self._http.request("GET", f"/api/user/find/{user_id}")
        return User.from_dict(data)

    @async_require_login
    async def aget_user(self, user_id: int) -> User:
        """异步根据 ID 获取用户信息。

        Args:
            user_id: 用户 ID

        Returns:
            User: 用户对象
        """
        data = await self._http.arequest("GET", f"/api/user/find/{user_id}")
        return User.from_dict(data)

    @require_login
    def search_users(self, keyword: str) -> List[User]:
        """搜索用户（按 ID/昵称/手机号/邮箱）。

        Args:
            keyword: 搜索关键词

        Returns:
            List[User]: 匹配的用户列表
        """
        data = self._http.request(
            "GET", "/api/user/search", params={"name": keyword}
        )
        return [User.from_dict(u) for u in data] if data else []

    @async_require_login
    async def asearch_users(self, keyword: str) -> List[User]:
        """异步搜索用户。

        Args:
            keyword: 搜索关键词

        Returns:
            List[User]: 匹配的用户列表
        """
        data = await self._http.arequest(
            "GET", "/api/user/search", params={"name": keyword}
        )
        return [User.from_dict(u) for u in data] if data else []

    @require_login
    def update_profile(self, **kwargs: Any) -> "BoxIM":
        """更新个人资料。

        先获取当前完整资料，再合并要更新的字段，确保服务器不会
        因为缺少字段而重置数据。

        Args:
            **kwargs: 要更新的字段（nickName/sex/signature/headImage 等）

        Returns:
            返回 self 以支持链式调用
        """
        current = self.get_me()
        current.update(kwargs)
        self._http.request("PUT", "/api/user/update", json_data=current)
        return self

    @async_require_login
    async def aupdate_profile(self, **kwargs: Any) -> "BoxIM":
        """异步更新个人资料。

        先获取当前完整资料，再合并要更新的字段，确保服务器不会
        因为缺少字段而重置数据。

        Args:
            **kwargs: 要更新的字段

        Returns:
            返回 self 以支持链式调用
        """
        current = await self.aget_me()
        current.update(kwargs)
        await self._http.arequest("PUT", "/api/user/update", json_data=current)
        return self

    @require_login
    def get_online_terminals(
        self, user_ids: Union[int, List[int]]
    ) -> List[Dict[str, Any]]:
        """获取用户在线终端信息。

        Args:
            user_ids: 用户 ID 或 ID 列表

        Returns:
            List[Dict[str, Any]]: 在线终端信息列表
        """
        user_ids_str = self._ids_to_str(user_ids)
        return self._http.request(
            "GET",
            "/api/user/terminal/online",
            params={"userIds": user_ids_str},
        )

    @async_require_login
    async def aget_online_terminals(
        self, user_ids: Union[int, List[int]]
    ) -> List[Dict[str, Any]]:
        """异步获取用户在线终端信息。

        Args:
            user_ids: 用户 ID 或 ID 列表

        Returns:
            List[Dict[str, Any]]: 在线终端信息列表
        """
        user_ids_str = self._ids_to_str(user_ids)
        return await self._http.arequest(
            "GET",
            "/api/user/terminal/online",
            params={"userIds": user_ids_str},
        )

    @staticmethod
    def _ids_to_str(user_ids: Union[int, List[int]]) -> str:
        """将用户 ID 或 ID 列表转换为逗号分隔字符串。

        Args:
            user_ids: 单个 ID 或 ID 列表

        Returns:
            逗号分隔的 ID 字符串
        """
        if isinstance(user_ids, list):
            return ",".join(map(str, user_ids))
        return str(user_ids)

    # ======================================================================
    # 好友相关
    # ======================================================================

    @require_login
    def get_friends(self) -> List[Friend]:
        """获取好友列表。

        Returns:
            List[Friend]: 好友对象列表
        """
        data = self._http.request("GET", "/api/friend/list")
        return [Friend.from_dict(f) for f in data] if data else []

    @async_require_login
    async def aget_friends(self) -> List[Friend]:
        """异步获取好友列表。

        Returns:
            List[Friend]: 好友对象列表
        """
        data = await self._http.arequest("GET", "/api/friend/list")
        return [Friend.from_dict(f) for f in data] if data else []

    @property
    def friends(self) -> List[Friend]:
        """好友列表（属性访问）。"""
        return self.get_friends()

    @require_login
    def get_friend_info(self, user_id: int) -> Friend:
        """获取指定好友信息。

        Args:
            user_id: 好友用户 ID

        Returns:
            Friend: 好友对象
        """
        data = self._http.request("GET", f"/api/friend/find/{user_id}")
        return Friend.from_dict(data)

    @async_require_login
    async def aget_friend_info(self, user_id: int) -> Friend:
        """异步获取指定好友信息。

        Args:
            user_id: 好友用户 ID

        Returns:
            Friend: 好友对象
        """
        data = await self._http.arequest("GET", f"/api/friend/find/{user_id}")
        return Friend.from_dict(data)

    @require_login
    def add_friend(self, user_id: int, remark: Optional[str] = None) -> "BoxIM":
        """发送好友请求。

        Args:
            user_id: 目标用户 ID
            remark: 附言

        Returns:
            返回 self 以支持链式调用
        """
        data: Dict[str, Any] = {"friendId": user_id}
        if remark:
            data["remark"] = remark
        self._http.request(
            "POST", "/api/friend/request/apply", json_data=data
        )
        return self

    @async_require_login
    async def aadd_friend(
        self, user_id: int, remark: Optional[str] = None
    ) -> "BoxIM":
        """异步发送好友请求。

        Args:
            user_id: 目标用户 ID
            remark: 附言

        Returns:
            返回 self 以支持链式调用
        """
        data: Dict[str, Any] = {"friendId": user_id}
        if remark:
            data["remark"] = remark
        await self._http.arequest(
            "POST", "/api/friend/request/apply", json_data=data
        )
        return self

    @require_login
    def delete_friend(self, user_id: int) -> "BoxIM":
        """删除好友。

        Args:
            user_id: 好友用户 ID

        Returns:
            返回 self 以支持链式调用
        """
        self._http.request("DELETE", f"/api/friend/delete/{user_id}")
        return self

    @async_require_login
    async def adelete_friend(self, user_id: int) -> "BoxIM":
        """异步删除好友。

        Args:
            user_id: 好友用户 ID

        Returns:
            返回 self 以支持链式调用
        """
        await self._http.arequest("DELETE", f"/api/friend/delete/{user_id}")
        return self

    @require_login
    def set_friend_dnd(self, user_id: int, dnd: bool) -> "BoxIM":
        """设置好友免打扰状态。

        Args:
            user_id: 好友 ID
            dnd: 是否免打扰

        Returns:
            返回 self 以支持链式调用
        """
        data = {"friendId": user_id, "isDnd": dnd}
        self._http.request("PUT", "/api/friend/dnd", json_data=data)
        return self

    @async_require_login
    async def aset_friend_dnd(self, user_id: int, dnd: bool) -> "BoxIM":
        """异步设置好友免打扰状态。

        Args:
            user_id: 好友 ID
            dnd: 是否免打扰

        Returns:
            返回 self 以支持链式调用
        """
        data = {"friendId": user_id, "isDnd": dnd}
        await self._http.arequest("PUT", "/api/friend/dnd", json_data=data)
        return self

    @require_login
    def set_friend_top(self, user_id: int, top: bool) -> "BoxIM":
        """设置好友置顶状态。

        Args:
            user_id: 好友 ID
            top: 是否置顶

        Returns:
            返回 self 以支持链式调用
        """
        data = {"friendId": user_id, "isTop": top}
        self._http.request("PUT", "/api/friend/top", json_data=data)
        return self

    @async_require_login
    async def aset_friend_top(self, user_id: int, top: bool) -> "BoxIM":
        """异步设置好友置顶状态。

        Args:
            user_id: 好友 ID
            top: 是否置顶

        Returns:
            返回 self 以支持链式调用
        """
        data = {"friendId": user_id, "isTop": top}
        await self._http.arequest("PUT", "/api/friend/top", json_data=data)
        return self

    @require_login
    def update_friend_remark(self, user_id: int, remark: str) -> "BoxIM":
        """更新好友备注名。

        Args:
            user_id: 好友 ID
            remark: 新备注名

        Returns:
            返回 self 以支持链式调用
        """
        data = {"friendId": user_id, "remarkNickName": remark}
        self._http.request(
            "PUT", "/api/friend/update/remark", json_data=data
        )
        return self

    @async_require_login
    async def aupdate_friend_remark(self, user_id: int, remark: str) -> "BoxIM":
        """异步更新好友备注名。

        Args:
            user_id: 好友 ID
            remark: 新备注名

        Returns:
            返回 self 以支持链式调用
        """
        data = {"friendId": user_id, "remarkNickName": remark}
        await self._http.arequest(
            "PUT", "/api/friend/update/remark", json_data=data
        )
        return self

    # ======================================================================
    # 好友请求相关
    # ======================================================================

    @require_login
    def get_friend_requests(self) -> List[FriendRequest]:
        """获取好友请求列表。

        Returns:
            List[FriendRequest]: 好友请求对象列表
        """
        data = self._http.request("GET", "/api/friend/request/list")
        return [FriendRequest.from_dict(r) for r in data] if data else []

    @async_require_login
    async def aget_friend_requests(self) -> List[FriendRequest]:
        """异步获取好友请求列表。

        Returns:
            List[FriendRequest]: 好友请求对象列表
        """
        data = await self._http.arequest("GET", "/api/friend/request/list")
        return [FriendRequest.from_dict(r) for r in data] if data else []

    @property
    def friend_requests(self) -> List[FriendRequest]:
        """好友请求列表（属性访问）。"""
        return self.get_friend_requests()

    @require_login
    def accept_friend_request(self, request_id: int) -> "BoxIM":
        """接受好友请求。

        Args:
            request_id: 好友请求 ID

        Returns:
            返回 self 以支持链式调用
        """
        self._http.request(
            "POST",
            "/api/friend/request/approve",
            params={"id": request_id},
        )
        return self

    @async_require_login
    async def aaccept_friend_request(self, request_id: int) -> "BoxIM":
        """异步接受好友请求。

        Args:
            request_id: 好友请求 ID

        Returns:
            返回 self 以支持链式调用
        """
        await self._http.arequest(
            "POST",
            "/api/friend/request/approve",
            params={"id": request_id},
        )
        return self

    @require_login
    def reject_friend_request(self, request_id: int) -> "BoxIM":
        """拒绝好友请求。

        Args:
            request_id: 好友请求 ID

        Returns:
            返回 self 以支持链式调用
        """
        self._http.request(
            "POST",
            "/api/friend/request/reject",
            params={"id": request_id},
        )
        return self

    @async_require_login
    async def areject_friend_request(self, request_id: int) -> "BoxIM":
        """异步拒绝好友请求。

        Args:
            request_id: 好友请求 ID

        Returns:
            返回 self 以支持链式调用
        """
        await self._http.arequest(
            "POST",
            "/api/friend/request/reject",
            params={"id": request_id},
        )
        return self

    @require_login
    def recall_friend_request(self, request_id: int) -> "BoxIM":
        """撤回好友请求。

        Args:
            request_id: 好友请求 ID

        Returns:
            返回 self 以支持链式调用
        """
        self._http.request(
            "POST",
            "/api/friend/request/recall",
            params={"id": request_id},
        )
        return self

    @async_require_login
    async def arecall_friend_request(self, request_id: int) -> "BoxIM":
        """异步撤回好友请求。

        Args:
            request_id: 好友请求 ID

        Returns:
            返回 self 以支持链式调用
        """
        await self._http.arequest(
            "POST",
            "/api/friend/request/recall",
            params={"id": request_id},
        )
        return self

    @require_login
    def send_friend_request(
        self, user_id: int, message: Optional[str] = None
    ) -> "BoxIM":
        """发送好友请求（add_friend 的别名）。

        Args:
            user_id: 目标用户 ID
            message: 附言

        Returns:
            返回 self 以支持链式调用
        """
        return self.add_friend(user_id, remark=message)

    @async_require_login
    async def asend_friend_request(
        self, user_id: int, message: Optional[str] = None
    ) -> "BoxIM":
        """异步发送好友请求。

        Args:
            user_id: 目标用户 ID
            message: 附言

        Returns:
            返回 self 以支持链式调用
        """
        return await self.aadd_friend(user_id, remark=message)

    # ======================================================================
    # 黑名单相关
    # ======================================================================

    @require_login
    def add_to_blacklist(self, user_id: int) -> "BoxIM":
        """将用户加入黑名单。

        Args:
            user_id: 目标用户 ID

        Returns:
            返回 self 以支持链式调用
        """
        self._http.request(
            "POST", "/api/blacklist/add", params={"userId": user_id}
        )
        return self

    @async_require_login
    async def aadd_to_blacklist(self, user_id: int) -> "BoxIM":
        """异步将用户加入黑名单。

        Args:
            user_id: 目标用户 ID

        Returns:
            返回 self 以支持链式调用
        """
        await self._http.arequest(
            "POST", "/api/blacklist/add", params={"userId": user_id}
        )
        return self

    @require_login
    def remove_from_blacklist(self, user_id: int) -> "BoxIM":
        """将用户从黑名单移除。

        Args:
            user_id: 目标用户 ID

        Returns:
            返回 self 以支持链式调用
        """
        self._http.request(
            "DELETE", "/api/blacklist/remove", params={"userId": user_id}
        )
        return self

    @async_require_login
    async def aremove_from_blacklist(self, user_id: int) -> "BoxIM":
        """异步将用户从黑名单移除。

        Args:
            user_id: 目标用户 ID

        Returns:
            返回 self 以支持链式调用
        """
        await self._http.arequest(
            "DELETE", "/api/blacklist/remove", params={"userId": user_id}
        )
        return self

    @require_login
    def get_blacklist(self) -> List[User]:
        """获取黑名单用户列表。

        Returns:
            List[User]: 被拉黑的用户列表
        """
        data = self._http.request("GET", "/api/blacklist/list")
        return [User.from_dict(u) for u in data] if data else []

    @async_require_login
    async def aget_blacklist(self) -> List[User]:
        """异步获取黑名单用户列表。

        Returns:
            List[User]: 被拉黑的用户列表
        """
        data = await self._http.arequest("GET", "/api/blacklist/list")
        return [User.from_dict(u) for u in data] if data else []

    # ======================================================================
    # 群组相关
    # ======================================================================

    @require_login
    def get_groups(self) -> List[Group]:
        """获取群组列表。

        Returns:
            List[Group]: 群组对象列表
        """
        data = self._http.request("GET", "/api/group/list")
        return [Group.from_dict(g) for g in data] if data else []

    @async_require_login
    async def aget_groups(self) -> List[Group]:
        """异步获取群组列表。

        Returns:
            List[Group]: 群组对象列表
        """
        data = await self._http.arequest("GET", "/api/group/list")
        return [Group.from_dict(g) for g in data] if data else []

    @property
    def groups(self) -> List[Group]:
        """群组列表（属性访问）。"""
        return self.get_groups()

    @require_login
    def create_group(self, name: str, member_ids: List[int]) -> Group:
        """创建群组。

        Args:
            name: 群组名称
            member_ids: 初始成员 ID 列表

        Returns:
            Group: 创建的群组对象
        """
        data = {"name": name, "memberIds": member_ids}
        result = self._http.request(
            "POST", "/api/group/create", json_data=data
        )
        return Group.from_dict(result)

    @async_require_login
    async def acreate_group(self, name: str, member_ids: List[int]) -> Group:
        """异步创建群组。

        Args:
            name: 群组名称
            member_ids: 初始成员 ID 列表

        Returns:
            Group: 创建的群组对象
        """
        data = {"name": name, "memberIds": member_ids}
        result = await self._http.arequest(
            "POST", "/api/group/create", json_data=data
        )
        return Group.from_dict(result)

    @require_login
    def get_group_info(self, group_id: int) -> Group:
        """获取群组信息。

        Args:
            group_id: 群组 ID

        Returns:
            Group: 群组对象
        """
        data = self._http.request("GET", f"/api/group/find/{group_id}")
        return Group.from_dict(data)

    @async_require_login
    async def aget_group_info(self, group_id: int) -> Group:
        """异步获取群组信息。

        Args:
            group_id: 群组 ID

        Returns:
            Group: 群组对象
        """
        data = await self._http.arequest("GET", f"/api/group/find/{group_id}")
        return Group.from_dict(data)

    @require_login
    def modify_group(self, group_id: int, **kwargs: Any) -> "BoxIM":
        """修改群组信息。

        Args:
            group_id: 群组 ID
            **kwargs: 要修改的字段（name/notice/headImage/remarkGroupName 等）

        Returns:
            返回 self 以支持链式调用
        """
        data = {"id": group_id, **kwargs}
        self._http.request("PUT", "/api/group/modify", json_data=data)
        return self

    @async_require_login
    async def amodify_group(self, group_id: int, **kwargs: Any) -> "BoxIM":
        """异步修改群组信息。

        Args:
            group_id: 群组 ID
            **kwargs: 要修改的字段

        Returns:
            返回 self 以支持链式调用
        """
        data = {"id": group_id, **kwargs}
        await self._http.arequest("PUT", "/api/group/modify", json_data=data)
        return self

    @require_login
    def delete_group(self, group_id: int) -> "BoxIM":
        """解散群组（仅群主可用）。

        Args:
            group_id: 群组 ID

        Returns:
            返回 self 以支持链式调用
        """
        self._http.request("DELETE", f"/api/group/delete/{group_id}")
        return self

    @async_require_login
    async def adelete_group(self, group_id: int) -> "BoxIM":
        """异步解散群组。

        Args:
            group_id: 群组 ID

        Returns:
            返回 self 以支持链式调用
        """
        await self._http.arequest("DELETE", f"/api/group/delete/{group_id}")
        return self

    @require_login
    def quit_group(self, group_id: int) -> "BoxIM":
        """退出群组（群主不可退，需解散）。

        Args:
            group_id: 群组 ID

        Returns:
            返回 self 以支持链式调用
        """
        self._http.request("DELETE", f"/api/group/quit/{group_id}")
        return self

    @async_require_login
    async def aquit_group(self, group_id: int) -> "BoxIM":
        """异步退出群组。

        Args:
            group_id: 群组 ID

        Returns:
            返回 self 以支持链式调用
        """
        await self._http.arequest("DELETE", f"/api/group/quit/{group_id}")
        return self

    @require_login
    def get_group_members(self, group_id: int, version: int = 0) -> List[User]:
        """获取群组成员列表（支持增量更新）。

        Args:
            group_id: 群组 ID
            version: 本地缓存版本号，服务端只返回更新部分

        Returns:
            List[User]: 成员用户列表
        """
        data = self._http.request(
            "GET",
            f"/api/group/members/{group_id}",
            params={"version": version},
        )
        return [User.from_dict(u) for u in data] if data else []

    @async_require_login
    async def aget_group_members(
        self, group_id: int, version: int = 0
    ) -> List[User]:
        """异步获取群组成员列表。

        Args:
            group_id: 群组 ID
            version: 本地缓存版本号

        Returns:
            List[User]: 成员用户列表
        """
        data = await self._http.arequest(
            "GET",
            f"/api/group/members/{group_id}",
            params={"version": version},
        )
        return [User.from_dict(u) for u in data] if data else []

    @require_login
    def get_group_online_members(self, group_id: int) -> List[int]:
        """获取群组在线成员 ID 列表。

        Args:
            group_id: 群组 ID

        Returns:
            List[int]: 在线成员 ID 列表
        """
        return (
            self._http.request(
                "GET", f"/api/group/members/online/{group_id}"
            )
            or []
        )

    @async_require_login
    async def aget_group_online_members(self, group_id: int) -> List[int]:
        """异步获取群组在线成员 ID 列表。

        Args:
            group_id: 群组 ID

        Returns:
            List[int]: 在线成员 ID 列表
        """
        return (
            await self._http.arequest(
                "GET", f"/api/group/members/online/{group_id}"
            )
            or []
        )

    @require_login
    def invite_to_group(self, group_id: int, user_ids: List[int]) -> "BoxIM":
        """邀请成员进群。

        Args:
            group_id: 群组 ID
            user_ids: 被邀请用户 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        data = {"groupId": group_id, "friendIds": user_ids}
        self._http.request("POST", "/api/group/invite", json_data=data)
        return self

    @async_require_login
    async def ainvite_to_group(
        self, group_id: int, user_ids: List[int]
    ) -> "BoxIM":
        """异步邀请成员进群。

        Args:
            group_id: 群组 ID
            user_ids: 被邀请用户 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        data = {"groupId": group_id, "friendIds": user_ids}
        await self._http.arequest("POST", "/api/group/invite", json_data=data)
        return self

    @require_login
    def remove_group_members(
        self, group_id: int, user_ids: List[int]
    ) -> "BoxIM":
        """将成员移出群组。

        Args:
            group_id: 群组 ID
            user_ids: 要移出的成员 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        data = {"groupId": group_id, "userIds": user_ids}
        self._http.request(
            "DELETE", "/api/group/members/remove", json_data=data
        )
        return self

    @async_require_login
    async def aremove_group_members(
        self, group_id: int, user_ids: List[int]
    ) -> "BoxIM":
        """异步将成员移出群组。

        Args:
            group_id: 群组 ID
            user_ids: 要移出的成员 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        data = {"groupId": group_id, "userIds": user_ids}
        await self._http.arequest(
            "DELETE", "/api/group/members/remove", json_data=data
        )
        return self

    @require_login
    def join_group(
        self, group_id: int, token: Optional[str] = None
    ) -> "BoxIM":
        """申请加入群聊。

        Args:
            group_id: 群组 ID
            token: 群名片 Token（可选，通过分享链接加入时使用）

        Returns:
            返回 self 以支持链式调用
        """
        data: Dict[str, Any] = {"groupId": group_id}
        if token:
            data["token"] = token
        self._http.request("POST", "/api/group/join", json_data=data)
        return self

    @async_require_login
    async def ajoin_group(
        self, group_id: int, token: Optional[str] = None
    ) -> "BoxIM":
        """异步申请加入群聊。

        Args:
            group_id: 群组 ID
            token: 群名片 Token（可选）

        Returns:
            返回 self 以支持链式调用
        """
        data: Dict[str, Any] = {"groupId": group_id}
        if token:
            data["token"] = token
        await self._http.arequest("POST", "/api/group/join", json_data=data)
        return self

    @require_login
    def get_group_card_token(self, group_id: int) -> str:
        """获取群名片分享 Token。

        Args:
            group_id: 群组 ID

        Returns:
            str: 群名片 Token 字符串
        """
        result = self._http.request(
            "GET", f"/api/group/card/token/{group_id}"
        )
        if isinstance(result, str):
            return result
        return result.get("token", "")

    @async_require_login
    async def aget_group_card_token(self, group_id: int) -> str:
        """异步获取群名片分享 Token。

        Args:
            group_id: 群组 ID

        Returns:
            str: 群名片 Token 字符串
        """
        result = await self._http.arequest(
            "GET", f"/api/group/card/token/{group_id}"
        )
        if isinstance(result, str):
            return result
        return result.get("token", "")

    @require_login
    def set_group_dnd(self, group_id: int, dnd: bool) -> "BoxIM":
        """设置群组免打扰状态。

        Args:
            group_id: 群组 ID
            dnd: 是否免打扰

        Returns:
            返回 self 以支持链式调用
        """
        data = {"groupId": group_id, "isDnd": dnd}
        self._http.request("PUT", "/api/group/dnd", json_data=data)
        return self

    @async_require_login
    async def aset_group_dnd(self, group_id: int, dnd: bool) -> "BoxIM":
        """异步设置群组免打扰状态。

        Args:
            group_id: 群组 ID
            dnd: 是否免打扰

        Returns:
            返回 self 以支持链式调用
        """
        data = {"groupId": group_id, "isDnd": dnd}
        await self._http.arequest("PUT", "/api/group/dnd", json_data=data)
        return self

    @require_login
    def set_group_top(self, group_id: int, top: bool) -> "BoxIM":
        """设置群组置顶状态。

        Args:
            group_id: 群组 ID
            top: 是否置顶

        Returns:
            返回 self 以支持链式调用
        """
        data = {"groupId": group_id, "isTop": top}
        self._http.request("PUT", "/api/group/top", json_data=data)
        return self

    @async_require_login
    async def aset_group_top(self, group_id: int, top: bool) -> "BoxIM":
        """异步设置群组置顶状态。

        Args:
            group_id: 群组 ID
            top: 是否置顶

        Returns:
            返回 self 以支持链式调用
        """
        data = {"groupId": group_id, "isTop": top}
        await self._http.arequest("PUT", "/api/group/top", json_data=data)
        return self

    @require_login
    def set_group_muted(self, group_id: int, muted: bool) -> "BoxIM":
        """设置群组全员禁言。

        Args:
            group_id: 群组 ID
            muted: 是否禁言

        Returns:
            返回 self 以支持链式调用
        """
        data = {"id": group_id, "isMuted": muted}
        self._http.request("PUT", "/api/group/muted", json_data=data)
        return self

    @async_require_login
    async def aset_group_muted(self, group_id: int, muted: bool) -> "BoxIM":
        """异步设置群组全员禁言。

        Args:
            group_id: 群组 ID
            muted: 是否禁言

        Returns:
            返回 self 以支持链式调用
        """
        data = {"id": group_id, "isMuted": muted}
        await self._http.arequest("PUT", "/api/group/muted", json_data=data)
        return self

    @require_login
    def set_group_allow_invite(self, group_id: int, allow: bool) -> "BoxIM":
        """设置是否允许群成员邀请他人。

        Args:
            group_id: 群组 ID
            allow: 是否允许

        Returns:
            返回 self 以支持链式调用
        """
        data = {"groupId": group_id, "isAllowInvite": allow}
        self._http.request("PUT", "/api/group/allowInvite", json_data=data)
        return self

    @async_require_login
    async def aset_group_allow_invite(
        self, group_id: int, allow: bool
    ) -> "BoxIM":
        """异步设置是否允许群成员邀请他人。

        Args:
            group_id: 群组 ID
            allow: 是否允许

        Returns:
            返回 self 以支持链式调用
        """
        data = {"groupId": group_id, "isAllowInvite": allow}
        await self._http.arequest(
            "PUT", "/api/group/allowInvite", json_data=data
        )
        return self

    @require_login
    def set_group_allow_share_card(
        self, group_id: int, allow: bool
    ) -> "BoxIM":
        """设置是否允许群成员分享群名片。

        Args:
            group_id: 群组 ID
            allow: 是否允许

        Returns:
            返回 self 以支持链式调用
        """
        data = {"groupId": group_id, "isAllowShareCard": allow}
        self._http.request(
            "PUT", "/api/group/allowShareCard", json_data=data
        )
        return self

    @async_require_login
    async def aset_group_allow_share_card(
        self, group_id: int, allow: bool
    ) -> "BoxIM":
        """异步设置是否允许群成员分享群名片。

        Args:
            group_id: 群组 ID
            allow: 是否允许

        Returns:
            返回 self 以支持链式调用
        """
        data = {"groupId": group_id, "isAllowShareCard": allow}
        await self._http.arequest(
            "PUT", "/api/group/allowShareCard", json_data=data
        )
        return self

    @require_login
    def set_group_member_muted(
        self,
        group_id: int,
        user_ids: Union[int, List[int]],
        muted: bool,
    ) -> "BoxIM":
        """设置群成员禁言状态。

        Args:
            group_id: 群组 ID
            user_ids: 成员 ID 或 ID 列表
            muted: 是否禁言

        Returns:
            返回 self 以支持链式调用
        """
        ids = [user_ids] if isinstance(user_ids, int) else user_ids
        data = {"groupId": group_id, "userIds": ids, "isMuted": muted}
        self._http.request(
            "PUT", "/api/group/members/muted", json_data=data
        )
        return self

    @async_require_login
    async def aset_group_member_muted(
        self,
        group_id: int,
        user_ids: Union[int, List[int]],
        muted: bool,
    ) -> "BoxIM":
        """异步设置群成员禁言状态。

        Args:
            group_id: 群组 ID
            user_ids: 成员 ID 或 ID 列表
            muted: 是否禁言

        Returns:
            返回 self 以支持链式调用
        """
        ids = [user_ids] if isinstance(user_ids, int) else user_ids
        data = {"groupId": group_id, "userIds": ids, "isMuted": muted}
        await self._http.arequest(
            "PUT", "/api/group/members/muted", json_data=data
        )
        return self

    @require_login
    def add_group_manager(
        self, group_id: int, user_ids: Union[int, List[int]]
    ) -> "BoxIM":
        """添加群组管理员（仅群主）。

        Args:
            group_id: 群组 ID
            user_ids: 用户 ID 或 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        ids = [user_ids] if isinstance(user_ids, int) else user_ids
        data = {"groupId": group_id, "userIds": ids}
        self._http.request(
            "POST", "/api/group/manager/add", json_data=data
        )
        return self

    @async_require_login
    async def aadd_group_manager(
        self, group_id: int, user_ids: Union[int, List[int]]
    ) -> "BoxIM":
        """异步添加群组管理员。

        Args:
            group_id: 群组 ID
            user_ids: 用户 ID 或 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        ids = [user_ids] if isinstance(user_ids, int) else user_ids
        data = {"groupId": group_id, "userIds": ids}
        await self._http.arequest(
            "POST", "/api/group/manager/add", json_data=data
        )
        return self

    @require_login
    def remove_group_manager(
        self, group_id: int, user_ids: Union[int, List[int]]
    ) -> "BoxIM":
        """移除群组管理员（仅群主）。

        Args:
            group_id: 群组 ID
            user_ids: 用户 ID 或 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        ids = [user_ids] if isinstance(user_ids, int) else user_ids
        data = {"groupId": group_id, "userIds": ids}
        self._http.request(
            "DELETE", "/api/group/manager/remove", json_data=data
        )
        return self

    @async_require_login
    async def aremove_group_manager(
        self, group_id: int, user_ids: Union[int, List[int]]
    ) -> "BoxIM":
        """异步移除群组管理员。

        Args:
            group_id: 群组 ID
            user_ids: 用户 ID 或 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        ids = [user_ids] if isinstance(user_ids, int) else user_ids
        data = {"groupId": group_id, "userIds": ids}
        await self._http.arequest(
            "DELETE", "/api/group/manager/remove", json_data=data
        )
        return self

    @require_login
    def set_group_top_message(
        self, group_id: int, message_id: int
    ) -> "BoxIM":
        """设置群组置顶消息。

        Args:
            group_id: 群组 ID
            message_id: 消息 ID

        Returns:
            返回 self 以支持链式调用
        """
        self._http.request(
            "POST",
            f"/api/group/setTopMessage/{group_id}",
            params={"messageId": message_id},
        )
        return self

    @async_require_login
    async def aset_group_top_message(
        self, group_id: int, message_id: int
    ) -> "BoxIM":
        """异步设置群组置顶消息。

        Args:
            group_id: 群组 ID
            message_id: 消息 ID

        Returns:
            返回 self 以支持链式调用
        """
        await self._http.arequest(
            "POST",
            f"/api/group/setTopMessage/{group_id}",
            params={"messageId": message_id},
        )
        return self

    @require_login
    def remove_group_top_message(self, group_id: int) -> "BoxIM":
        """移除群组置顶消息。

        Args:
            group_id: 群组 ID

        Returns:
            返回 self 以支持链式调用
        """
        self._http.request(
            "DELETE", f"/api/group/removeTopMessage/{group_id}"
        )
        return self

    @async_require_login
    async def aremove_group_top_message(self, group_id: int) -> "BoxIM":
        """异步移除群组置顶消息。

        Args:
            group_id: 群组 ID

        Returns:
            返回 self 以支持链式调用
        """
        await self._http.arequest(
            "DELETE", f"/api/group/removeTopMessage/{group_id}"
        )
        return self

    @require_login
    def hide_group_top_message(self, group_id: int) -> "BoxIM":
        """隐藏群组置顶消息（仅对自己隐藏）。

        Args:
            group_id: 群组 ID

        Returns:
            返回 self 以支持链式调用
        """
        self._http.request(
            "DELETE", f"/api/group/hideTopMessage/{group_id}"
        )
        return self

    @async_require_login
    async def ahide_group_top_message(self, group_id: int) -> "BoxIM":
        """异步隐藏群组置顶消息。

        Args:
            group_id: 群组 ID

        Returns:
            返回 self 以支持链式调用
        """
        await self._http.arequest(
            "DELETE", f"/api/group/hideTopMessage/{group_id}"
        )
        return self

    # ======================================================================
    # 消息相关 - 私聊
    # ======================================================================

    @require_login
    def send_text(self, user_id: int, text: str) -> "BoxIM":
        """发送私聊文本消息。

        Args:
            user_id: 接收用户 ID
            text: 文本内容

        Returns:
            返回 self 以支持链式调用
        """
        self._send_private_message(user_id, text, MessageType.TEXT)
        return self

    @async_require_login
    async def asend_text(self, user_id: int, text: str) -> "BoxIM":
        """异步发送私聊文本消息。

        Args:
            user_id: 接收用户 ID
            text: 文本内容

        Returns:
            返回 self 以支持链式调用
        """
        await self._asend_private_message(user_id, text, MessageType.TEXT)
        return self

    @require_login
    def send_image(self, user_id: int, image_path: str) -> "BoxIM":
        """发送私聊图片消息。

        Args:
            user_id: 接收用户 ID
            image_path: 本地图片文件路径

        Returns:
            返回 self 以支持链式调用
        """
        result = self._uploader.upload_image(image_path)
        content = MessageBuilder.image_from_upload(result)
        self._send_private_message(user_id, content, MessageType.IMAGE)
        return self

    @async_require_login
    async def asend_image(self, user_id: int, image_path: str) -> "BoxIM":
        """异步发送私聊图片消息。

        Args:
            user_id: 接收用户 ID
            image_path: 本地图片文件路径

        Returns:
            返回 self 以支持链式调用
        """
        result = await self._uploader.aupload_image(image_path)
        content = MessageBuilder.image_from_upload(result)
        await self._asend_private_message(user_id, content, MessageType.IMAGE)
        return self

    @require_login
    def send_file(self, user_id: int, file_path: str) -> "BoxIM":
        """发送私聊文件消息。

        Args:
            user_id: 接收用户 ID
            file_path: 本地文件路径

        Returns:
            返回 self 以支持链式调用
        """
        result = self._uploader.upload_file(file_path)
        content = MessageBuilder.file_from_upload(result)
        self._send_private_message(user_id, content, MessageType.FILE)
        return self

    @async_require_login
    async def asend_file(self, user_id: int, file_path: str) -> "BoxIM":
        """异步发送私聊文件消息。

        Args:
            user_id: 接收用户 ID
            file_path: 本地文件路径

        Returns:
            返回 self 以支持链式调用
        """
        result = await self._uploader.aupload_file(file_path)
        content = MessageBuilder.file_from_upload(result)
        await self._asend_private_message(user_id, content, MessageType.FILE)
        return self

    @require_login
    def send_voice(
        self, user_id: int, voice_path: str, duration: int = 3
    ) -> "BoxIM":
        """发送私聊语音消息。

        Args:
            user_id: 接收用户 ID
            voice_path: 本地语音文件路径
            duration: 语音时长（秒）

        Returns:
            返回 self 以支持链式调用
        """
        result = self._uploader.upload_file(voice_path)
        content = MessageBuilder.voice(result.url, duration)
        self._send_private_message(user_id, content, MessageType.VOICE)
        return self

    @async_require_login
    async def asend_voice(
        self, user_id: int, voice_path: str, duration: int = 3
    ) -> "BoxIM":
        """异步发送私聊语音消息。

        Args:
            user_id: 接收用户 ID
            voice_path: 本地语音文件路径
            duration: 语音时长（秒）

        Returns:
            返回 self 以支持链式调用
        """
        result = await self._uploader.aupload_file(voice_path)
        content = MessageBuilder.voice(result.url, duration)
        await self._asend_private_message(user_id, content, MessageType.VOICE)
        return self

    @require_login
    def send_video(self, user_id: int, video_path: str) -> "BoxIM":
        """发送私聊视频消息。

        Args:
            user_id: 接收用户 ID
            video_path: 本地视频文件路径

        Returns:
            返回 self 以支持链式调用
        """
        result = self._uploader.upload_video(video_path)
        content = MessageBuilder.video_from_upload(result)
        self._send_private_message(user_id, content, MessageType.VIDEO)
        return self

    @async_require_login
    async def asend_video(self, user_id: int, video_path: str) -> "BoxIM":
        """异步发送私聊视频消息。

        Args:
            user_id: 接收用户 ID
            video_path: 本地视频文件路径

        Returns:
            返回 self 以支持链式调用
        """
        result = await self._uploader.aupload_video(video_path)
        content = MessageBuilder.video_from_upload(result)
        await self._asend_private_message(user_id, content, MessageType.VIDEO)
        return self

    @require_login
    def send_sticker(self, user_id: int, sticker_id: int) -> "BoxIM":
        """发送私聊贴纸消息。

        Args:
            user_id: 接收用户 ID
            sticker_id: 贴纸 ID

        Returns:
            返回 self 以支持链式调用
        """
        content = MessageBuilder.sticker(sticker_id)
        self._send_private_message(user_id, content, MessageType.STICKER)
        return self

    @async_require_login
    async def asend_sticker(self, user_id: int, sticker_id: int) -> "BoxIM":
        """异步发送私聊贴纸消息。

        Args:
            user_id: 接收用户 ID
            sticker_id: 贴纸 ID

        Returns:
            返回 self 以支持链式调用
        """
        content = MessageBuilder.sticker(sticker_id)
        await self._asend_private_message(
            user_id, content, MessageType.STICKER
        )
        return self

    @require_login
    def send_user_card(
        self,
        user_id: int,
        target_user_id: int,
        target_nickname: str,
        target_head_image: str,
    ) -> "BoxIM":
        """发送私聊个人名片。

        Args:
            user_id: 接收用户 ID
            target_user_id: 名片中的用户 ID
            target_nickname: 名片中的用户昵称
            target_head_image: 名片中的用户头像 URL

        Returns:
            返回 self 以支持链式调用
        """
        content = MessageBuilder.user_card(
            target_user_id, target_nickname, target_head_image
        )
        self._send_private_message(user_id, content, MessageType.USER_CARD)
        return self

    @async_require_login
    async def asend_user_card(
        self,
        user_id: int,
        target_user_id: int,
        target_nickname: str,
        target_head_image: str,
    ) -> "BoxIM":
        """异步发送私聊个人名片。

        Args:
            user_id: 接收用户 ID
            target_user_id: 名片中的用户 ID
            target_nickname: 名片中的用户昵称
            target_head_image: 名片中的用户头像 URL

        Returns:
            返回 self 以支持链式调用
        """
        content = MessageBuilder.user_card(
            target_user_id, target_nickname, target_head_image
        )
        await self._asend_private_message(
            user_id, content, MessageType.USER_CARD
        )
        return self

    @require_login
    def send_group_card(
        self,
        user_id: int,
        group_id: int,
        group_name: str,
        group_head_image: str,
    ) -> "BoxIM":
        """发送私聊群聊名片。

        Args:
            user_id: 接收用户 ID
            group_id: 名片中的群组 ID
            group_name: 名片中的群组名称
            group_head_image: 名片中的群组头像 URL

        Returns:
            返回 self 以支持链式调用
        """
        content = MessageBuilder.group_card(
            group_id, group_name, group_head_image
        )
        self._send_private_message(user_id, content, MessageType.GROUP_CARD)
        return self

    @async_require_login
    async def asend_group_card(
        self,
        user_id: int,
        group_id: int,
        group_name: str,
        group_head_image: str,
    ) -> "BoxIM":
        """异步发送私聊群聊名片。

        Args:
            user_id: 接收用户 ID
            group_id: 名片中的群组 ID
            group_name: 名片中的群组名称
            group_head_image: 名片中的群组头像 URL

        Returns:
            返回 self 以支持链式调用
        """
        content = MessageBuilder.group_card(
            group_id, group_name, group_head_image
        )
        await self._asend_private_message(
            user_id, content, MessageType.GROUP_CARD
        )
        return self

    @require_login
    def recall_private_message(self, message_id: int) -> "BoxIM":
        """撤回私聊消息。

        Args:
            message_id: 消息 ID

        Returns:
            返回 self 以支持链式调用
        """
        self._http.request(
            "DELETE", f"/api/message/private/recall/{message_id}"
        )
        return self

    @async_require_login
    async def arecall_private_message(self, message_id: int) -> "BoxIM":
        """异步撤回私聊消息。

        Args:
            message_id: 消息 ID

        Returns:
            返回 self 以支持链式调用
        """
        await self._http.arequest(
            "DELETE", f"/api/message/private/recall/{message_id}"
        )
        return self

    @require_login
    def mark_private_read(
        self, friend_id: int, message_id: Optional[int] = None
    ) -> "BoxIM":
        """标记私聊消息为已读。

        Args:
            friend_id: 好友 ID
            message_id: 消息 ID（可选，标记到该消息为止）

        Returns:
            返回 self 以支持链式调用
        """
        params: Dict[str, Any] = {"friendId": friend_id}
        if message_id is not None:
            params["messageId"] = message_id
        self._http.request(
            "PUT",
            "/api/message/private/readed",
            params=params,
        )
        return self

    @async_require_login
    async def amark_private_read(
        self, friend_id: int, message_id: Optional[int] = None
    ) -> "BoxIM":
        """异步标记私聊消息为已读。

        Args:
            friend_id: 好友 ID
            message_id: 消息 ID（可选）

        Returns:
            返回 self 以支持链式调用
        """
        params: Dict[str, Any] = {"friendId": friend_id}
        if message_id is not None:
            params["messageId"] = message_id
        await self._http.arequest(
            "PUT",
            "/api/message/private/readed",
            params=params,
        )
        return self

    @require_login
    def get_max_read_private_message_id(self, friend_id: int) -> int:
        """获取最大已读私聊消息 ID。

        Args:
            friend_id: 好友 ID

        Returns:
            int: 最大已读消息 ID
        """
        result = self._http.request(
            "GET",
            "/api/message/private/maxReadedId",
            params={"friendId": friend_id},
        )
        return int(result) if result is not None else 0

    @async_require_login
    async def aget_max_read_private_message_id(self, friend_id: int) -> int:
        """异步获取最大已读私聊消息 ID。

        Args:
            friend_id: 好友 ID

        Returns:
            int: 最大已读消息 ID
        """
        result = await self._http.arequest(
            "GET",
            "/api/message/private/maxReadedId",
            params={"friendId": friend_id},
        )
        return int(result) if result is not None else 0

    @require_login
    def load_private_offline_message(self, min_id: int) -> List[Dict[str, Any]]:
        """拉取私聊离线消息。

        Args:
            min_id: 最小消息 ID（拉取该 ID 之后的消息）

        Returns:
            List[Dict[str, Any]]: 离线消息列表
        """
        return (
            self._http.request(
                "GET",
                "/api/message/private/loadOfflineMessage",
                params={"minId": min_id},
            )
            or []
        )

    @async_require_login
    async def aload_private_offline_message(
        self, min_id: int
    ) -> List[Dict[str, Any]]:
        """异步拉取私聊离线消息。

        Args:
            min_id: 最小消息 ID

        Returns:
            List[Dict[str, Any]]: 离线消息列表
        """
        return (
            await self._http.arequest(
                "GET",
                "/api/message/private/loadOfflineMessage",
                params={"minId": min_id},
            )
            or []
        )

    @require_login
    def get_private_message_history(
        self,
        friend_id: int,
        local_ids: Optional[List[int]] = None,
        min_seq_no: Optional[int] = None,
        max_seq_no: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """获取私聊消息历史记录。

        支持两种查询模式：
        - 按 localIds 查询: ``get_private_message_history(fid, local_ids=[1,2])``
        - 按 seqNo 范围查询: ``get_private_message_history(fid, min_seq_no=0, max_seq_no=100)``

        Args:
            friend_id: 好友 ID
            local_ids: 本地消息 ID 列表（模式 1）
            min_seq_no: 最小序列号（模式 2）
            max_seq_no: 最大序列号（模式 2）

        Returns:
            List[Dict[str, Any]]: 消息历史列表
        """
        data: Dict[str, Any] = {"friendId": friend_id}
        if local_ids is not None:
            data["localIds"] = local_ids
        if min_seq_no is not None:
            data["minSeqNo"] = min_seq_no
        if max_seq_no is not None:
            data["maxSeqNo"] = max_seq_no
        return (
            self._http.request(
                "POST",
                "/api/message/private/history",
                json_data=data,
            )
            or []
        )

    @async_require_login
    async def aget_private_message_history(
        self,
        friend_id: int,
        local_ids: Optional[List[int]] = None,
        min_seq_no: Optional[int] = None,
        max_seq_no: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """异步获取私聊消息历史记录。

        参数同 get_private_message_history()。
        """
        data: Dict[str, Any] = {"friendId": friend_id}
        if local_ids is not None:
            data["localIds"] = local_ids
        if min_seq_no is not None:
            data["minSeqNo"] = min_seq_no
        if max_seq_no is not None:
            data["maxSeqNo"] = max_seq_no
        return (
            await self._http.arequest(
                "POST",
                "/api/message/private/history",
                json_data=data,
            )
            or []
        )

    @require_login
    def delete_private_messages(
        self, chat_id: int, message_ids: List[int]
    ) -> "BoxIM":
        """删除私聊消息。

        Args:
            chat_id: 聊天对象用户 ID
            message_ids: 要删除的消息 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        data = {"chatId": chat_id, "messageIds": message_ids}
        self._http.request(
            "DELETE", "/api/message/private/deleteMessage", json_data=data
        )
        return self

    @async_require_login
    async def adelete_private_messages(
        self, chat_id: int, message_ids: List[int]
    ) -> "BoxIM":
        """异步删除私聊消息。

        Args:
            chat_id: 聊天对象用户 ID
            message_ids: 要删除的消息 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        data = {"chatId": chat_id, "messageIds": message_ids}
        await self._http.arequest(
            "DELETE", "/api/message/private/deleteMessage", json_data=data
        )
        return self

    @require_login
    def delete_private_chat(self, chat_id: int) -> "BoxIM":
        """删除私聊会话（清空与某好友的全部消息）。

        Args:
            chat_id: 聊天对象用户 ID

        Returns:
            返回 self 以支持链式调用
        """
        data = {"chatId": chat_id}
        self._http.request(
            "DELETE", "/api/message/private/deleteChat", json_data=data
        )
        return self

    @async_require_login
    async def adelete_private_chat(self, chat_id: int) -> "BoxIM":
        """异步删除私聊会话。

        Args:
            chat_id: 聊天对象用户 ID

        Returns:
            返回 self 以支持链式调用
        """
        data = {"chatId": chat_id}
        await self._http.arequest(
            "DELETE", "/api/message/private/deleteChat", json_data=data
        )
        return self

    def _send_private_message(
        self,
        user_id: int,
        content: str,
        msg_type: MessageType,
        receipt: bool = False,
        quote_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """发送私聊消息（内部方法）。

        Args:
            user_id: 接收用户 ID
            content: 消息内容
            msg_type: 消息类型
            receipt: 是否需要已读回执
            quote_message_id: 引用消息 ID

        Returns:
            Dict[str, Any]: 发送结果
        """
        data: Dict[str, Any] = {
            "recvId": user_id,
            "content": content,
            "type": int(msg_type),
            "localId": MessageBuilder.generate_local_id(),
            "receipt": receipt,
        }
        if quote_message_id is not None:
            data["quoteMessageId"] = quote_message_id
        return self._http.request(
            "POST", "/api/message/private/send", json_data=data
        )

    async def _asend_private_message(
        self,
        user_id: int,
        content: str,
        msg_type: MessageType,
        receipt: bool = False,
        quote_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """异步发送私聊消息（内部方法）。

        Args:
            user_id: 接收用户 ID
            content: 消息内容
            msg_type: 消息类型
            receipt: 是否需要已读回执
            quote_message_id: 引用消息 ID

        Returns:
            Dict[str, Any]: 发送结果
        """
        data: Dict[str, Any] = {
            "recvId": user_id,
            "content": content,
            "type": int(msg_type),
            "localId": MessageBuilder.generate_local_id(),
            "receipt": receipt,
        }
        if quote_message_id is not None:
            data["quoteMessageId"] = quote_message_id
        return await self._http.arequest(
            "POST", "/api/message/private/send", json_data=data
        )

    @require_login
    def send_private_raw(
        self,
        user_id: int,
        content: str,
        msg_type: MessageType,
        receipt: bool = False,
        quote_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """发送原始私聊消息（开发者完全控制消息内容）。

        Args:
            user_id: 接收用户 ID
            content: 消息内容（JSON 字符串或文本）
            msg_type: 消息类型
            receipt: 是否需要已读回执
            quote_message_id: 引用消息 ID

        Returns:
            Dict[str, Any]: 发送结果
        """
        return self._send_private_message(
            user_id, content, msg_type, receipt, quote_message_id
        )

    @async_require_login
    async def asend_private_raw(
        self,
        user_id: int,
        content: str,
        msg_type: MessageType,
        receipt: bool = False,
        quote_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """异步发送原始私聊消息。

        Args:
            user_id: 接收用户 ID
            content: 消息内容
            msg_type: 消息类型
            receipt: 是否需要已读回执
            quote_message_id: 引用消息 ID

        Returns:
            Dict[str, Any]: 发送结果
        """
        return await self._asend_private_message(
            user_id, content, msg_type, receipt, quote_message_id
        )

    # ======================================================================
    # 消息相关 - 群聊
    # ======================================================================

    @require_login
    def send_group_text(
        self,
        group_id: int,
        text: str,
        at_users: Optional[List[int]] = None,
    ) -> "BoxIM":
        """发送群聊文本消息。

        Args:
            group_id: 群组 ID
            text: 文本内容
            at_users: @ 的用户 ID 列表，-1 表示 @所有人

        Returns:
            返回 self 以支持链式调用
        """
        self._send_group_message(group_id, text, MessageType.TEXT, at_users)
        return self

    @async_require_login
    async def asend_group_text(
        self,
        group_id: int,
        text: str,
        at_users: Optional[List[int]] = None,
    ) -> "BoxIM":
        """异步发送群聊文本消息。

        Args:
            group_id: 群组 ID
            text: 文本内容
            at_users: @ 的用户 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        await self._asend_group_message(
            group_id, text, MessageType.TEXT, at_users
        )
        return self

    @require_login
    def send_group_image(
        self,
        group_id: int,
        image_path: str,
        at_users: Optional[List[int]] = None,
    ) -> "BoxIM":
        """发送群聊图片消息。

        Args:
            group_id: 群组 ID
            image_path: 本地图片文件路径
            at_users: @ 的用户 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        result = self._uploader.upload_image(image_path)
        content = MessageBuilder.image_from_upload(result)
        self._send_group_message(
            group_id, content, MessageType.IMAGE, at_users
        )
        return self

    @async_require_login
    async def asend_group_image(
        self,
        group_id: int,
        image_path: str,
        at_users: Optional[List[int]] = None,
    ) -> "BoxIM":
        """异步发送群聊图片消息。

        Args:
            group_id: 群组 ID
            image_path: 本地图片文件路径
            at_users: @ 的用户 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        result = await self._uploader.aupload_image(image_path)
        content = MessageBuilder.image_from_upload(result)
        await self._asend_group_message(
            group_id, content, MessageType.IMAGE, at_users
        )
        return self

    @require_login
    def send_group_file(
        self,
        group_id: int,
        file_path: str,
        at_users: Optional[List[int]] = None,
    ) -> "BoxIM":
        """发送群聊文件消息。

        Args:
            group_id: 群组 ID
            file_path: 本地文件路径
            at_users: @ 的用户 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        result = self._uploader.upload_file(file_path)
        content = MessageBuilder.file_from_upload(result)
        self._send_group_message(
            group_id, content, MessageType.FILE, at_users
        )
        return self

    @async_require_login
    async def asend_group_file(
        self,
        group_id: int,
        file_path: str,
        at_users: Optional[List[int]] = None,
    ) -> "BoxIM":
        """异步发送群聊文件消息。

        Args:
            group_id: 群组 ID
            file_path: 本地文件路径
            at_users: @ 的用户 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        result = await self._uploader.aupload_file(file_path)
        content = MessageBuilder.file_from_upload(result)
        await self._asend_group_message(
            group_id, content, MessageType.FILE, at_users
        )
        return self

    @require_login
    def send_group_voice(
        self,
        group_id: int,
        voice_path: str,
        duration: int = 3,
        at_users: Optional[List[int]] = None,
    ) -> "BoxIM":
        """发送群聊语音消息。

        Args:
            group_id: 群组 ID
            voice_path: 本地语音文件路径
            duration: 语音时长（秒）
            at_users: @ 的用户 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        result = self._uploader.upload_file(voice_path)
        content = MessageBuilder.voice(result.url, duration)
        self._send_group_message(
            group_id, content, MessageType.VOICE, at_users
        )
        return self

    @async_require_login
    async def asend_group_voice(
        self,
        group_id: int,
        voice_path: str,
        duration: int = 3,
        at_users: Optional[List[int]] = None,
    ) -> "BoxIM":
        """异步发送群聊语音消息。

        Args:
            group_id: 群组 ID
            voice_path: 本地语音文件路径
            duration: 语音时长（秒）
            at_users: @ 的用户 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        result = await self._uploader.aupload_file(voice_path)
        content = MessageBuilder.voice(result.url, duration)
        await self._asend_group_message(
            group_id, content, MessageType.VOICE, at_users
        )
        return self

    @require_login
    def send_group_video(
        self,
        group_id: int,
        video_path: str,
        at_users: Optional[List[int]] = None,
    ) -> "BoxIM":
        """发送群聊视频消息。

        Args:
            group_id: 群组 ID
            video_path: 本地视频文件路径
            at_users: @ 的用户 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        result = self._uploader.upload_video(video_path)
        content = MessageBuilder.video_from_upload(result)
        self._send_group_message(
            group_id, content, MessageType.VIDEO, at_users
        )
        return self

    @async_require_login
    async def asend_group_video(
        self,
        group_id: int,
        video_path: str,
        at_users: Optional[List[int]] = None,
    ) -> "BoxIM":
        """异步发送群聊视频消息。

        Args:
            group_id: 群组 ID
            video_path: 本地视频文件路径
            at_users: @ 的用户 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        result = await self._uploader.aupload_video(video_path)
        content = MessageBuilder.video_from_upload(result)
        await self._asend_group_message(
            group_id, content, MessageType.VIDEO, at_users
        )
        return self

    @require_login
    def send_group_sticker(
        self,
        group_id: int,
        sticker_id: int,
        at_users: Optional[List[int]] = None,
    ) -> "BoxIM":
        """发送群聊贴纸消息。

        Args:
            group_id: 群组 ID
            sticker_id: 贴纸 ID
            at_users: @ 的用户 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        content = MessageBuilder.sticker(sticker_id)
        self._send_group_message(
            group_id, content, MessageType.STICKER, at_users
        )
        return self

    @async_require_login
    async def asend_group_sticker(
        self,
        group_id: int,
        sticker_id: int,
        at_users: Optional[List[int]] = None,
    ) -> "BoxIM":
        """异步发送群聊贴纸消息。

        Args:
            group_id: 群组 ID
            sticker_id: 贴纸 ID
            at_users: @ 的用户 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        content = MessageBuilder.sticker(sticker_id)
        await self._asend_group_message(
            group_id, content, MessageType.STICKER, at_users
        )
        return self

    @require_login
    def recall_group_message(self, message_id: int) -> "BoxIM":
        """撤回群聊消息。

        Args:
            message_id: 消息 ID

        Returns:
            返回 self 以支持链式调用
        """
        self._http.request(
            "DELETE", f"/api/message/group/recall/{message_id}"
        )
        return self

    @async_require_login
    async def arecall_group_message(self, message_id: int) -> "BoxIM":
        """异步撤回群聊消息。

        Args:
            message_id: 消息 ID

        Returns:
            返回 self 以支持链式调用
        """
        await self._http.arequest(
            "DELETE", f"/api/message/group/recall/{message_id}"
        )
        return self

    @require_login
    def mark_group_read(
        self, group_id: int, message_id: Optional[int] = None
    ) -> "BoxIM":
        """标记群聊消息为已读。

        Args:
            group_id: 群组 ID
            message_id: 消息 ID（可选，标记到该消息为止）

        Returns:
            返回 self 以支持链式调用
        """
        params: Dict[str, Any] = {"groupId": group_id}
        if message_id is not None:
            params["messageId"] = message_id
        self._http.request(
            "PUT",
            "/api/message/group/readed",
            params=params,
        )
        return self

    @async_require_login
    async def amark_group_read(
        self, group_id: int, message_id: Optional[int] = None
    ) -> "BoxIM":
        """异步标记群聊消息为已读。

        Args:
            group_id: 群组 ID
            message_id: 消息 ID（可选）

        Returns:
            返回 self 以支持链式调用
        """
        params: Dict[str, Any] = {"groupId": group_id}
        if message_id is not None:
            params["messageId"] = message_id
        await self._http.arequest(
            "PUT",
            "/api/message/group/readed",
            params=params,
        )
        return self

    @require_login
    def load_group_offline_message(
        self, min_id: int
    ) -> List[Dict[str, Any]]:
        """拉取群聊离线消息。

        Args:
            min_id: 最小消息 ID

        Returns:
            List[Dict[str, Any]]: 离线消息列表
        """
        return (
            self._http.request(
                "GET",
                "/api/message/group/loadOfflineMessage",
                params={"minId": min_id},
            )
            or []
        )

    @async_require_login
    async def aload_group_offline_message(
        self, min_id: int
    ) -> List[Dict[str, Any]]:
        """异步拉取群聊离线消息。

        Args:
            min_id: 最小消息 ID

        Returns:
            List[Dict[str, Any]]: 离线消息列表
        """
        return (
            await self._http.arequest(
                "GET",
                "/api/message/group/loadOfflineMessage",
                params={"minId": min_id},
            )
            or []
        )

    @require_login
    def get_group_message_readers(
        self, group_id: int, message_id: int
    ) -> List[int]:
        """获取群聊消息已读用户 ID 列表。

        Args:
            group_id: 群组 ID
            message_id: 消息 ID

        Returns:
            List[int]: 已读用户 ID 列表
        """
        return (
            self._http.request(
                "GET",
                "/api/message/group/findReadedUsers",
                params={"groupId": group_id, "messageId": message_id},
            )
            or []
        )

    @async_require_login
    async def aget_group_message_readers(
        self, group_id: int, message_id: int
    ) -> List[int]:
        """异步获取群聊消息已读用户 ID 列表。

        Args:
            group_id: 群组 ID
            message_id: 消息 ID

        Returns:
            List[int]: 已读用户 ID 列表
        """
        return (
            await self._http.arequest(
                "GET",
                "/api/message/group/findReadedUsers",
                params={"groupId": group_id, "messageId": message_id},
            )
            or []
        )

    @require_login
    def get_group_message_history(
        self,
        group_id: int,
        local_ids: Optional[List[int]] = None,
        min_seq_no: Optional[int] = None,
        max_seq_no: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """获取群聊消息历史记录。

        支持两种查询模式：
        - 按 localIds 查询
        - 按 seqNo 范围查询

        Args:
            group_id: 群组 ID
            local_ids: 本地消息 ID 列表（模式 1）
            min_seq_no: 最小序列号（模式 2）
            max_seq_no: 最大序列号（模式 2）

        Returns:
            List[Dict[str, Any]]: 消息历史列表
        """
        data: Dict[str, Any] = {"groupId": group_id}
        if local_ids is not None:
            data["localIds"] = local_ids
        if min_seq_no is not None:
            data["minSeqNo"] = min_seq_no
        if max_seq_no is not None:
            data["maxSeqNo"] = max_seq_no
        return (
            self._http.request(
                "POST",
                "/api/message/group/history",
                json_data=data,
            )
            or []
        )

    @async_require_login
    async def aget_group_message_history(
        self,
        group_id: int,
        local_ids: Optional[List[int]] = None,
        min_seq_no: Optional[int] = None,
        max_seq_no: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """异步获取群聊消息历史记录。

        参数同 get_group_message_history()。
        """
        data: Dict[str, Any] = {"groupId": group_id}
        if local_ids is not None:
            data["localIds"] = local_ids
        if min_seq_no is not None:
            data["minSeqNo"] = min_seq_no
        if max_seq_no is not None:
            data["maxSeqNo"] = max_seq_no
        return (
            await self._http.arequest(
                "POST",
                "/api/message/group/history",
                json_data=data,
            )
            or []
        )

    @require_login
    def delete_group_messages(
        self, chat_id: int, message_ids: List[int]
    ) -> "BoxIM":
        """删除群聊消息。

        Args:
            chat_id: 群组 ID
            message_ids: 要删除的消息 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        data = {"chatId": chat_id, "messageIds": message_ids}
        self._http.request(
            "DELETE", "/api/message/group/deleteMessage", json_data=data
        )
        return self

    @async_require_login
    async def adelete_group_messages(
        self, chat_id: int, message_ids: List[int]
    ) -> "BoxIM":
        """异步删除群聊消息。

        Args:
            chat_id: 群组 ID
            message_ids: 要删除的消息 ID 列表

        Returns:
            返回 self 以支持链式调用
        """
        data = {"chatId": chat_id, "messageIds": message_ids}
        await self._http.arequest(
            "DELETE", "/api/message/group/deleteMessage", json_data=data
        )
        return self

    @require_login
    def delete_group_chat(self, chat_id: int) -> "BoxIM":
        """删除群聊会话。

        Args:
            chat_id: 群组 ID

        Returns:
            返回 self 以支持链式调用
        """
        data = {"chatId": chat_id}
        self._http.request(
            "DELETE", "/api/message/group/deleteChat", json_data=data
        )
        return self

    @async_require_login
    async def adelete_group_chat(self, chat_id: int) -> "BoxIM":
        """异步删除群聊会话。

        Args:
            chat_id: 群组 ID

        Returns:
            返回 self 以支持链式调用
        """
        data = {"chatId": chat_id}
        await self._http.arequest(
            "DELETE", "/api/message/group/deleteChat", json_data=data
        )
        return self

    def _send_group_message(
        self,
        group_id: int,
        content: str,
        msg_type: MessageType,
        at_users: Optional[List[int]] = None,
        receipt: bool = False,
        quote_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """发送群聊消息（内部方法）。

        Args:
            group_id: 群组 ID
            content: 消息内容
            msg_type: 消息类型
            at_users: @ 的用户 ID 列表
            receipt: 是否需要已读回执
            quote_message_id: 引用消息 ID

        Returns:
            Dict[str, Any]: 发送结果
        """
        data: Dict[str, Any] = {
            "groupId": group_id,
            "content": content,
            "type": int(msg_type),
            "localId": MessageBuilder.generate_local_id(),
            "atUserIds": at_users or [],
            "receipt": receipt,
        }
        if quote_message_id is not None:
            data["quoteMessageId"] = quote_message_id
        return self._http.request(
            "POST", "/api/message/group/send", json_data=data
        )

    async def _asend_group_message(
        self,
        group_id: int,
        content: str,
        msg_type: MessageType,
        at_users: Optional[List[int]] = None,
        receipt: bool = False,
        quote_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """异步发送群聊消息（内部方法）。

        Args:
            group_id: 群组 ID
            content: 消息内容
            msg_type: 消息类型
            at_users: @ 的用户 ID 列表
            receipt: 是否需要已读回执
            quote_message_id: 引用消息 ID

        Returns:
            Dict[str, Any]: 发送结果
        """
        data: Dict[str, Any] = {
            "groupId": group_id,
            "content": content,
            "type": int(msg_type),
            "localId": MessageBuilder.generate_local_id(),
            "atUserIds": at_users or [],
            "receipt": receipt,
        }
        if quote_message_id is not None:
            data["quoteMessageId"] = quote_message_id
        return await self._http.arequest(
            "POST", "/api/message/group/send", json_data=data
        )

    @require_login
    def send_group_raw(
        self,
        group_id: int,
        content: str,
        msg_type: MessageType,
        at_users: Optional[List[int]] = None,
        receipt: bool = False,
        quote_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """发送原始群聊消息（开发者完全控制消息内容）。

        Args:
            group_id: 群组 ID
            content: 消息内容
            msg_type: 消息类型
            at_users: @ 的用户 ID 列表
            receipt: 是否需要已读回执
            quote_message_id: 引用消息 ID

        Returns:
            Dict[str, Any]: 发送结果
        """
        return self._send_group_message(
            group_id, content, msg_type, at_users, receipt, quote_message_id
        )

    @async_require_login
    async def asend_group_raw(
        self,
        group_id: int,
        content: str,
        msg_type: MessageType,
        at_users: Optional[List[int]] = None,
        receipt: bool = False,
        quote_message_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """异步发送原始群聊消息。

        Args:
            group_id: 群组 ID
            content: 消息内容
            msg_type: 消息类型
            at_users: @ 的用户 ID 列表
            receipt: 是否需要已读回执
            quote_message_id: 引用消息 ID

        Returns:
            Dict[str, Any]: 发送结果
        """
        return await self._asend_group_message(
            group_id, content, msg_type, at_users, receipt, quote_message_id
        )

    # ======================================================================
    # 系统消息相关
    # ======================================================================

    @require_login
    def load_system_offline_message(
        self, min_seq_no: int = 0
    ) -> List[SystemMessage]:
        """拉取系统离线消息。

        Args:
            min_seq_no: 最小序列号

        Returns:
            List[SystemMessage]: 系统消息列表
        """
        data = self._http.request(
            "GET",
            "/api/message/system/loadOfflineMessage",
            params={"minSeqNo": min_seq_no},
        )
        return [SystemMessage.from_dict(m) for m in data] if data else []

    @async_require_login
    async def aload_system_offline_message(
        self, min_seq_no: int = 0
    ) -> List[SystemMessage]:
        """异步拉取系统离线消息。

        Args:
            min_seq_no: 最小序列号

        Returns:
            List[SystemMessage]: 系统消息列表
        """
        data = await self._http.arequest(
            "GET",
            "/api/message/system/loadOfflineMessage",
            params={"minSeqNo": min_seq_no},
        )
        return [SystemMessage.from_dict(m) for m in data] if data else []

    @require_login
    def mark_system_read(self, max_seq_no: int) -> "BoxIM":
        """标记系统消息为已读。

        Args:
            max_seq_no: 最大序列号

        Returns:
            返回 self 以支持链式调用
        """
        self._http.request(
            "PUT",
            "/api/message/system/readed",
            params={"maxSeqNo": max_seq_no},
        )
        return self

    @async_require_login
    async def amark_system_read(self, max_seq_no: int) -> "BoxIM":
        """异步标记系统消息为已读。

        Args:
            max_seq_no: 最大序列号

        Returns:
            返回 self 以支持链式调用
        """
        await self._http.arequest(
            "PUT",
            "/api/message/system/readed",
            params={"maxSeqNo": max_seq_no},
        )
        return self

    @require_login
    def get_system_message_content(self, message_id: int) -> Dict[str, Any]:
        """获取系统消息内容详情。

        Args:
            message_id: 消息 ID

        Returns:
            Dict[str, Any]: 系统消息内容
        """
        return self._http.request(
            "GET",
            "/api/message/system/content",
            params={"id": message_id},
        )

    @async_require_login
    async def aget_system_message_content(
        self, message_id: int
    ) -> Dict[str, Any]:
        """异步获取系统消息内容详情。

        Args:
            message_id: 消息 ID

        Returns:
            Dict[str, Any]: 系统消息内容
        """
        return await self._http.arequest(
            "GET",
            "/api/message/system/content",
            params={"id": message_id},
        )

    # ======================================================================
    # 贴纸系统
    # ======================================================================

    @require_login
    def get_sticker_albums(self) -> List[StickerAlbum]:
        """获取表情包专辑列表。

        Returns:
            List[StickerAlbum]: 表情包专辑列表
        """
        data = self._http.request("GET", "/api/sticker/albums")
        return [StickerAlbum.from_dict(a) for a in data] if data else []

    @async_require_login
    async def aget_sticker_albums(self) -> List[StickerAlbum]:
        """异步获取表情包专辑列表。

        Returns:
            List[StickerAlbum]: 表情包专辑列表
        """
        data = await self._http.arequest("GET", "/api/sticker/albums")
        return [StickerAlbum.from_dict(a) for a in data] if data else []

    @require_login
    def get_stickers(self, album_id: int) -> List[Sticker]:
        """获取指定表情包专辑中的贴纸列表。

        Args:
            album_id: 表情包专辑 ID

        Returns:
            List[Sticker]: 贴纸列表
        """
        data = self._http.request(
            "GET", f"/api/sticker/stickers/{album_id}"
        )
        return [Sticker.from_dict(s) for s in data] if data else []

    @async_require_login
    async def aget_stickers(self, album_id: int) -> List[Sticker]:
        """异步获取贴纸列表。

        Args:
            album_id: 表情包专辑 ID

        Returns:
            List[Sticker]: 贴纸列表
        """
        data = await self._http.arequest(
            "GET", f"/api/sticker/stickers/{album_id}"
        )
        return [Sticker.from_dict(s) for s in data] if data else []

    @require_login
    def search_stickers(self, name: str) -> List[Sticker]:
        """搜索贴纸。

        Args:
            name: 搜索关键词

        Returns:
            List[Sticker]: 匹配的贴纸列表
        """
        data = self._http.request(
            "GET",
            "/api/sticker/stickers/search",
            params={"name": name},
        )
        return [Sticker.from_dict(s) for s in data] if data else []

    @async_require_login
    async def asearch_stickers(self, name: str) -> List[Sticker]:
        """异步搜索贴纸。

        Args:
            name: 搜索关键词

        Returns:
            List[Sticker]: 匹配的贴纸列表
        """
        data = await self._http.arequest(
            "GET",
            "/api/sticker/stickers/search",
            params={"name": name},
        )
        return [Sticker.from_dict(s) for s in data] if data else []

    @require_login
    def get_custom_stickers(self) -> List[Sticker]:
        """获取用户自定义贴纸列表。

        Returns:
            List[Sticker]: 自定义贴纸列表
        """
        data = self._http.request("GET", "/api/sticker/custom/list")
        return [Sticker.from_dict(s) for s in data] if data else []

    @async_require_login
    async def aget_custom_stickers(self) -> List[Sticker]:
        """异步获取用户自定义贴纸列表。

        Returns:
            List[Sticker]: 自定义贴纸列表
        """
        data = await self._http.arequest("GET", "/api/sticker/custom/list")
        return [Sticker.from_dict(s) for s in data] if data else []

    @require_login
    def add_custom_sticker(
        self,
        name: str,
        image_url: str,
        thumb_url: str,
        width: int = 100,
        height: int = 100,
    ) -> "BoxIM":
        """添加自定义贴纸。

        Args:
            name: 贴纸名称
            image_url: 图片 URL
            thumb_url: 缩略图 URL
            width: 宽度（像素）
            height: 高度（像素）

        Returns:
            返回 self 以支持链式调用
        """
        data = {
            "name": name,
            "imageUrl": image_url,
            "thumbUrl": thumb_url,
            "width": width,
            "height": height,
        }
        self._http.request("POST", "/api/sticker/custom/add", json_data=data)
        return self

    @async_require_login
    async def aadd_custom_sticker(
        self,
        name: str,
        image_url: str,
        thumb_url: str,
        width: int = 100,
        height: int = 100,
    ) -> "BoxIM":
        """异步添加自定义贴纸。

        Args:
            name: 贴纸名称
            image_url: 图片 URL
            thumb_url: 缩略图 URL
            width: 宽度（像素）
            height: 高度（像素）

        Returns:
            返回 self 以支持链式调用
        """
        data = {
            "name": name,
            "imageUrl": image_url,
            "thumbUrl": thumb_url,
            "width": width,
            "height": height,
        }
        await self._http.arequest(
            "POST", "/api/sticker/custom/add", json_data=data
        )
        return self

    @require_login
    def top_custom_sticker(self, sticker_id: int) -> "BoxIM":
        """置顶自定义贴纸。

        Args:
            sticker_id: 贴纸 ID

        Returns:
            返回 self 以支持链式调用
        """
        self._http.request(
            "PUT", f"/api/sticker/custom/top/{sticker_id}"
        )
        return self

    @async_require_login
    async def atop_custom_sticker(self, sticker_id: int) -> "BoxIM":
        """异步置顶自定义贴纸。

        Args:
            sticker_id: 贴纸 ID

        Returns:
            返回 self 以支持链式调用
        """
        await self._http.arequest(
            "PUT", f"/api/sticker/custom/top/{sticker_id}"
        )
        return self

    @require_login
    def delete_custom_sticker(self, sticker_id: int) -> "BoxIM":
        """删除自定义贴纸。

        Args:
            sticker_id: 贴纸 ID

        Returns:
            返回 self 以支持链式调用
        """
        self._http.request(
            "DELETE", f"/api/sticker/custom/delete/{sticker_id}"
        )
        return self

    @async_require_login
    async def adelete_custom_sticker(self, sticker_id: int) -> "BoxIM":
        """异步删除自定义贴纸。

        Args:
            sticker_id: 贴纸 ID

        Returns:
            返回 self 以支持链式调用
        """
        await self._http.arequest(
            "DELETE", f"/api/sticker/custom/delete/{sticker_id}"
        )
        return self

    # ======================================================================
    # 投诉举报
    # ======================================================================

    @require_login
    def submit_complaint(
        self,
        target_type: str,
        target_id: int,
        complaint_type: int = 1,
        content: str = "",
        images: Optional[List[str]] = None,
        target_name: str = "",
    ) -> Dict[str, Any]:
        """发起投诉（API #79）。

        Args:
            target_type: 投诉目标类型 "USER" 或 "GROUP"
            target_id: 目标 ID
            complaint_type: 投诉类型 1=骚扰 2=诈骗 3=不良内容 99=其他
            content: 投诉内容（最大 512 字符）
            images: 截图 URL 列表（最多 9 张）
            target_name: 目标名称

        Returns:
            Dict[str, Any]: 投诉结果
        """
        data: Dict[str, Any] = {
            "type": complaint_type,
            "content": content,
            "targetType": target_type,
            "targetId": target_id,
            "targetName": target_name,
            "images": images or [],
        }
        return self._http.request(
            "POST", "/api/complaint/initiate", json_data=data
        )

    @async_require_login
    async def asubmit_complaint(
        self,
        target_type: str,
        target_id: int,
        complaint_type: int = 1,
        content: str = "",
        images: Optional[List[str]] = None,
        target_name: str = "",
    ) -> Dict[str, Any]:
        """异步发起投诉。

        参数同 submit_complaint()。
        """
        data: Dict[str, Any] = {
            "type": complaint_type,
            "content": content,
            "targetType": target_type,
            "targetId": target_id,
            "targetName": target_name,
            "images": images or [],
        }
        return await self._http.arequest(
            "POST", "/api/complaint/initiate", json_data=data
        )

    # ======================================================================
    # WebRTC 私聊通话（底层 API）
    # ======================================================================

    @require_login
    def webrtc_setup(
        self, user_id: int, mode: str = "video"
    ) -> Dict[str, Any]:
        """发起 WebRTC 私聊通话建立请求。

        Args:
            user_id: 目标用户 ID
            mode: 通话模式（voice/audio/video）

        Returns:
            Dict[str, Any]: 通话建立响应
        """
        return self._http.request(
            "POST",
            "/api/webrtc/private/setup",
            params={"uid": user_id, "mode": mode},
        )

    @async_require_login
    async def awebrtc_setup(
        self, user_id: int, mode: str = "video"
    ) -> Dict[str, Any]:
        """异步发起 WebRTC 私聊通话建立请求。

        Args:
            user_id: 目标用户 ID
            mode: 通话模式

        Returns:
            Dict[str, Any]: 通话建立响应
        """
        return await self._http.arequest(
            "POST",
            "/api/webrtc/private/setup",
            params={"uid": user_id, "mode": mode},
        )

    @require_login
    def webrtc_accept(
        self, user_id: int, answer: str = ""
    ) -> Dict[str, Any]:
        """接受 WebRTC 私聊通话。

        Args:
            user_id: 对方用户 ID
            answer: SDP Answer（可选）

        Returns:
            Dict[str, Any]: 操作结果
        """
        json_data = self._parse_sdp_to_dict(answer)
        return self._http.request(
            "POST",
            "/api/webrtc/private/accept",
            params={"uid": user_id},
            json_data=json_data,
        )

    @async_require_login
    async def awebrtc_accept(
        self, user_id: int, answer: str = ""
    ) -> Dict[str, Any]:
        """异步接受 WebRTC 私聊通话。

        Args:
            user_id: 对方用户 ID
            answer: SDP Answer（可选）

        Returns:
            Dict[str, Any]: 操作结果
        """
        json_data = self._parse_sdp_to_dict(answer)
        return await self._http.arequest(
            "POST",
            "/api/webrtc/private/accept",
            params={"uid": user_id},
            json_data=json_data,
        )

    @staticmethod
    def _parse_sdp_to_dict(sdp: str) -> Dict[str, Any]:
        """将 SDP 字符串解析为字典（优先作为 JSON 解析）。

        Args:
            sdp: SDP 字符串或 JSON 字符串

        Returns:
            Dict[str, Any]: 解析后的字典
        """
        if not sdp:
            return {}
        try:
            return json.loads(sdp)
        except json.JSONDecodeError:
            return {"sdp": sdp}

    @require_login
    def webrtc_reject(self, user_id: int) -> Dict[str, Any]:
        """拒绝 WebRTC 私聊通话。

        Args:
            user_id: 对方用户 ID

        Returns:
            Dict[str, Any]: 操作结果
        """
        return self._http.request(
            "POST",
            "/api/webrtc/private/reject",
            params={"uid": user_id},
        )

    @async_require_login
    async def awebrtc_reject(self, user_id: int) -> Dict[str, Any]:
        """异步拒绝 WebRTC 私聊通话。

        Args:
            user_id: 对方用户 ID

        Returns:
            Dict[str, Any]: 操作结果
        """
        return await self._http.arequest(
            "POST",
            "/api/webrtc/private/reject",
            params={"uid": user_id},
        )

    @require_login
    def webrtc_cancel(self, user_id: int) -> Dict[str, Any]:
        """取消 WebRTC 私聊通话（主叫方）。

        Args:
            user_id: 对方用户 ID

        Returns:
            Dict[str, Any]: 操作结果
        """
        return self._http.request(
            "POST",
            "/api/webrtc/private/cancel",
            params={"uid": user_id},
        )

    @async_require_login
    async def awebrtc_cancel(self, user_id: int) -> Dict[str, Any]:
        """异步取消 WebRTC 私聊通话。

        Args:
            user_id: 对方用户 ID

        Returns:
            Dict[str, Any]: 操作结果
        """
        return await self._http.arequest(
            "POST",
            "/api/webrtc/private/cancel",
            params={"uid": user_id},
        )

    @require_login
    def webrtc_failed(
        self, user_id: int, reason: str = ""
    ) -> Dict[str, Any]:
        """上报 WebRTC 私聊通话失败。

        Args:
            user_id: 对方用户 ID
            reason: 失败原因

        Returns:
            Dict[str, Any]: 操作结果
        """
        return self._http.request(
            "POST",
            "/api/webrtc/private/failed",
            params={"uid": user_id, "reason": reason},
        )

    @async_require_login
    async def awebrtc_failed(
        self, user_id: int, reason: str = ""
    ) -> Dict[str, Any]:
        """异步上报 WebRTC 私聊通话失败。

        Args:
            user_id: 对方用户 ID
            reason: 失败原因

        Returns:
            Dict[str, Any]: 操作结果
        """
        return await self._http.arequest(
            "POST",
            "/api/webrtc/private/failed",
            params={"uid": user_id, "reason": reason},
        )

    @require_login
    def webrtc_handup(self, user_id: int) -> Dict[str, Any]:
        """挂断 WebRTC 私聊通话。

        Args:
            user_id: 对方用户 ID

        Returns:
            Dict[str, Any]: 操作结果
        """
        return self._http.request(
            "POST",
            "/api/webrtc/private/handup",
            params={"uid": user_id},
        )

    @async_require_login
    async def awebrtc_handup(self, user_id: int) -> Dict[str, Any]:
        """异步挂断 WebRTC 私聊通话。

        Args:
            user_id: 对方用户 ID

        Returns:
            Dict[str, Any]: 操作结果
        """
        return await self._http.arequest(
            "POST",
            "/api/webrtc/private/handup",
            params={"uid": user_id},
        )

    @require_login
    def webrtc_offer(self, user_id: int, sdp: str) -> Dict[str, Any]:
        """发送 WebRTC SDP Offer（私聊）。

        Args:
            user_id: 对方用户 ID
            sdp: SDP 内容

        Returns:
            Dict[str, Any]: 操作结果
        """
        return self._http.request(
            "POST",
            "/api/webrtc/private/offer",
            params={"uid": user_id},
            json_data={"sdp": sdp},
        )

    @async_require_login
    async def awebrtc_offer(self, user_id: int, sdp: str) -> Dict[str, Any]:
        """异步发送 WebRTC SDP Offer（私聊）。

        Args:
            user_id: 对方用户 ID
            sdp: SDP 内容

        Returns:
            Dict[str, Any]: 操作结果
        """
        return await self._http.arequest(
            "POST",
            "/api/webrtc/private/offer",
            params={"uid": user_id},
            json_data={"sdp": sdp},
        )

    @require_login
    def webrtc_answer(self, user_id: int, sdp: str) -> Dict[str, Any]:
        """发送 WebRTC SDP Answer（私聊）。

        Args:
            user_id: 对方用户 ID
            sdp: SDP 内容

        Returns:
            Dict[str, Any]: 操作结果
        """
        return self._http.request(
            "POST",
            "/api/webrtc/private/answer",
            params={"uid": user_id},
            json_data={"sdp": sdp},
        )

    @async_require_login
    async def awebrtc_answer(self, user_id: int, sdp: str) -> Dict[str, Any]:
        """异步发送 WebRTC SDP Answer（私聊）。

        Args:
            user_id: 对方用户 ID
            sdp: SDP 内容

        Returns:
            Dict[str, Any]: 操作结果
        """
        return await self._http.arequest(
            "POST",
            "/api/webrtc/private/answer",
            params={"uid": user_id},
            json_data={"sdp": sdp},
        )

    @require_login
    def webrtc_send_candidate(
        self, user_id: int, candidate: str
    ) -> Dict[str, Any]:
        """发送 WebRTC ICE Candidate（私聊）。

        Args:
            user_id: 对方用户 ID
            candidate: ICE Candidate 字符串

        Returns:
            Dict[str, Any]: 操作结果
        """
        return self._http.request(
            "POST",
            "/api/webrtc/private/candidate",
            params={"uid": user_id},
            json_data={"candidate": candidate},
        )

    @async_require_login
    async def awebrtc_send_candidate(
        self, user_id: int, candidate: str
    ) -> Dict[str, Any]:
        """异步发送 WebRTC ICE Candidate（私聊）。

        Args:
            user_id: 对方用户 ID
            candidate: ICE Candidate 字符串

        Returns:
            Dict[str, Any]: 操作结果
        """
        return await self._http.arequest(
            "POST",
            "/api/webrtc/private/candidate",
            params={"uid": user_id},
            json_data={"candidate": candidate},
        )

    @require_login
    def webrtc_heartbeat(self, user_id: int) -> Dict[str, Any]:
        """发送 WebRTC 私聊通话心跳。

        Args:
            user_id: 对方用户 ID

        Returns:
            Dict[str, Any]: 操作结果
        """
        return self._http.request(
            "POST",
            "/api/webrtc/private/heartbeat",
            params={"uid": user_id},
        )

    @async_require_login
    async def awebrtc_heartbeat(self, user_id: int) -> Dict[str, Any]:
        """异步发送 WebRTC 私聊通话心跳。

        Args:
            user_id: 对方用户 ID

        Returns:
            Dict[str, Any]: 操作结果
        """
        return await self._http.arequest(
            "POST",
            "/api/webrtc/private/heartbeat",
            params={"uid": user_id},
        )

    # ======================================================================
    # WebRTC 群组通话（底层 API）
    # ======================================================================

    @require_login
    def webrtc_group_setup(
        self,
        group_id: int,
        user_infos: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """发起群组 WebRTC 通话。

        Args:
            group_id: 群组 ID
            user_infos: 被邀请用户信息列表（可选）

        Returns:
            Dict[str, Any]: 通话建立响应
        """
        data: Dict[str, Any] = {"groupId": group_id}
        if user_infos:
            data["userInfos"] = user_infos
        return self._http.request(
            "POST", "/api/webrtc/group/setup", json_data=data
        )

    @async_require_login
    async def awebrtc_group_setup(
        self,
        group_id: int,
        user_infos: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """异步发起群组 WebRTC 通话。

        Args:
            group_id: 群组 ID
            user_infos: 被邀请用户信息列表（可选）

        Returns:
            Dict[str, Any]: 通话建立响应
        """
        data: Dict[str, Any] = {"groupId": group_id}
        if user_infos:
            data["userInfos"] = user_infos
        return await self._http.arequest(
            "POST", "/api/webrtc/group/setup", json_data=data
        )

    @require_login
    def webrtc_group_accept(self, group_id: int) -> Dict[str, Any]:
        """接受群组 WebRTC 通话。

        Args:
            group_id: 群组 ID

        Returns:
            Dict[str, Any]: 操作结果
        """
        return self._http.request(
            "POST",
            "/api/webrtc/group/accept",
            params={"groupId": group_id},
        )

    @async_require_login
    async def awebrtc_group_accept(self, group_id: int) -> Dict[str, Any]:
        """异步接受群组 WebRTC 通话。

        Args:
            group_id: 群组 ID

        Returns:
            Dict[str, Any]: 操作结果
        """
        return await self._http.arequest(
            "POST",
            "/api/webrtc/group/accept",
            params={"groupId": group_id},
        )

    @require_login
    def webrtc_group_reject(self, group_id: int) -> Dict[str, Any]:
        """拒绝群组 WebRTC 通话。

        Args:
            group_id: 群组 ID

        Returns:
            Dict[str, Any]: 操作结果
        """
        return self._http.request(
            "POST",
            "/api/webrtc/group/reject",
            params={"groupId": group_id},
        )

    @async_require_login
    async def awebrtc_group_reject(self, group_id: int) -> Dict[str, Any]:
        """异步拒绝群组 WebRTC 通话。

        Args:
            group_id: 群组 ID

        Returns:
            Dict[str, Any]: 操作结果
        """
        return await self._http.arequest(
            "POST",
            "/api/webrtc/group/reject",
            params={"groupId": group_id},
        )

    @require_login
    def webrtc_group_failed(
        self, group_id: int, reason: str = ""
    ) -> Dict[str, Any]:
        """上报群组 WebRTC 通话失败。

        Args:
            group_id: 群组 ID
            reason: 失败原因

        Returns:
            Dict[str, Any]: 操作结果
        """
        data = {"groupId": group_id, "reason": reason}
        return self._http.request(
            "POST", "/api/webrtc/group/failed", json_data=data
        )

    @async_require_login
    async def awebrtc_group_failed(
        self, group_id: int, reason: str = ""
    ) -> Dict[str, Any]:
        """异步上报群组 WebRTC 通话失败。

        Args:
            group_id: 群组 ID
            reason: 失败原因

        Returns:
            Dict[str, Any]: 操作结果
        """
        data = {"groupId": group_id, "reason": reason}
        return await self._http.arequest(
            "POST", "/api/webrtc/group/failed", json_data=data
        )

    @require_login
    def webrtc_group_join(self, group_id: int) -> Dict[str, Any]:
        """加入群组 WebRTC 通话。

        Args:
            group_id: 群组 ID

        Returns:
            Dict[str, Any]: 操作结果
        """
        return self._http.request(
            "POST",
            "/api/webrtc/group/join",
            params={"groupId": group_id},
        )

    @async_require_login
    async def awebrtc_group_join(self, group_id: int) -> Dict[str, Any]:
        """异步加入群组 WebRTC 通话。

        Args:
            group_id: 群组 ID

        Returns:
            Dict[str, Any]: 操作结果
        """
        return await self._http.arequest(
            "POST",
            "/api/webrtc/group/join",
            params={"groupId": group_id},
        )

    @require_login
    def webrtc_group_invite(
        self, group_id: int, user_infos: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """邀请成员加入群组 WebRTC 通话。

        Args:
            group_id: 群组 ID
            user_infos: 被邀请用户信息列表

        Returns:
            Dict[str, Any]: 操作结果
        """
        data = {"groupId": group_id, "userInfos": user_infos}
        return self._http.request(
            "POST", "/api/webrtc/group/invite", json_data=data
        )

    @async_require_login
    async def awebrtc_group_invite(
        self, group_id: int, user_infos: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """异步邀请成员加入群组 WebRTC 通话。

        Args:
            group_id: 群组 ID
            user_infos: 被邀请用户信息列表

        Returns:
            Dict[str, Any]: 操作结果
        """
        data = {"groupId": group_id, "userInfos": user_infos}
        return await self._http.arequest(
            "POST", "/api/webrtc/group/invite", json_data=data
        )

    @require_login
    def webrtc_group_offer(
        self, group_id: int, user_id: int, offer: str
    ) -> Dict[str, Any]:
        """发送群组 WebRTC SDP Offer。

        Args:
            group_id: 群组 ID
            user_id: 目标用户 ID
            offer: SDP Offer 内容

        Returns:
            Dict[str, Any]: 操作结果
        """
        data = {"groupId": group_id, "userId": user_id, "offer": offer}
        return self._http.request(
            "POST", "/api/webrtc/group/offer", json_data=data
        )

    @async_require_login
    async def awebrtc_group_offer(
        self, group_id: int, user_id: int, offer: str
    ) -> Dict[str, Any]:
        """异步发送群组 WebRTC SDP Offer。

        Args:
            group_id: 群组 ID
            user_id: 目标用户 ID
            offer: SDP Offer 内容

        Returns:
            Dict[str, Any]: 操作结果
        """
        data = {"groupId": group_id, "userId": user_id, "offer": offer}
        return await self._http.arequest(
            "POST", "/api/webrtc/group/offer", json_data=data
        )

    @require_login
    def webrtc_group_answer(
        self, group_id: int, user_id: int, answer: str
    ) -> Dict[str, Any]:
        """发送群组 WebRTC SDP Answer。

        Args:
            group_id: 群组 ID
            user_id: 目标用户 ID
            answer: SDP Answer 内容

        Returns:
            Dict[str, Any]: 操作结果
        """
        data = {"groupId": group_id, "userId": user_id, "answer": answer}
        return self._http.request(
            "POST", "/api/webrtc/group/answer", json_data=data
        )

    @async_require_login
    async def awebrtc_group_answer(
        self, group_id: int, user_id: int, answer: str
    ) -> Dict[str, Any]:
        """异步发送群组 WebRTC SDP Answer。

        Args:
            group_id: 群组 ID
            user_id: 目标用户 ID
            answer: SDP Answer 内容

        Returns:
            Dict[str, Any]: 操作结果
        """
        data = {"groupId": group_id, "userId": user_id, "answer": answer}
        return await self._http.arequest(
            "POST", "/api/webrtc/group/answer", json_data=data
        )

    @require_login
    def webrtc_group_quit(self, group_id: int) -> Dict[str, Any]:
        """退出群组 WebRTC 通话。

        Args:
            group_id: 群组 ID

        Returns:
            Dict[str, Any]: 操作结果
        """
        return self._http.request(
            "POST",
            "/api/webrtc/group/quit",
            params={"groupId": group_id},
        )

    @async_require_login
    async def awebrtc_group_quit(self, group_id: int) -> Dict[str, Any]:
        """异步退出群组 WebRTC 通话。

        Args:
            group_id: 群组 ID

        Returns:
            Dict[str, Any]: 操作结果
        """
        return await self._http.arequest(
            "POST",
            "/api/webrtc/group/quit",
            params={"groupId": group_id},
        )

    @require_login
    def webrtc_group_cancel(self, group_id: int) -> Dict[str, Any]:
        """取消群组 WebRTC 通话。

        Args:
            group_id: 群组 ID

        Returns:
            Dict[str, Any]: 操作结果
        """
        return self._http.request(
            "POST",
            "/api/webrtc/group/cancel",
            params={"groupId": group_id},
        )

    @async_require_login
    async def awebrtc_group_cancel(self, group_id: int) -> Dict[str, Any]:
        """异步取消群组 WebRTC 通话。

        Args:
            group_id: 群组 ID

        Returns:
            Dict[str, Any]: 操作结果
        """
        return await self._http.arequest(
            "POST",
            "/api/webrtc/group/cancel",
            params={"groupId": group_id},
        )

    @require_login
    def webrtc_group_send_candidate(
        self, group_id: int, user_id: int, candidate: str
    ) -> Dict[str, Any]:
        """发送群组 WebRTC ICE Candidate。

        Args:
            group_id: 群组 ID
            user_id: 目标用户 ID
            candidate: ICE Candidate 字符串

        Returns:
            Dict[str, Any]: 操作结果
        """
        data = {
            "groupId": group_id,
            "userId": user_id,
            "candidate": candidate,
        }
        return self._http.request(
            "POST", "/api/webrtc/group/candidate", json_data=data
        )

    @async_require_login
    async def awebrtc_group_send_candidate(
        self, group_id: int, user_id: int, candidate: str
    ) -> Dict[str, Any]:
        """异步发送群组 WebRTC ICE Candidate。

        Args:
            group_id: 群组 ID
            user_id: 目标用户 ID
            candidate: ICE Candidate 字符串

        Returns:
            Dict[str, Any]: 操作结果
        """
        data = {
            "groupId": group_id,
            "userId": user_id,
            "candidate": candidate,
        }
        return await self._http.arequest(
            "POST", "/api/webrtc/group/candidate", json_data=data
        )

    @require_login
    def webrtc_group_device(
        self,
        group_id: int,
        is_camera: bool = True,
        is_microphone: bool = True,
        is_share_screen: bool = False,
    ) -> Dict[str, Any]:
        """更新群组通话设备状态。

        Args:
            group_id: 群组 ID
            is_camera: 摄像头是否开启
            is_microphone: 麦克风是否开启
            is_share_screen: 是否屏幕共享

        Returns:
            Dict[str, Any]: 操作结果
        """
        data = {
            "groupId": group_id,
            "isCamera": is_camera,
            "isMicroPhone": is_microphone,
            "isShareScreen": is_share_screen,
        }
        return self._http.request(
            "POST", "/api/webrtc/group/device", json_data=data
        )

    @async_require_login
    async def awebrtc_group_device(
        self,
        group_id: int,
        is_camera: bool = True,
        is_microphone: bool = True,
        is_share_screen: bool = False,
    ) -> Dict[str, Any]:
        """异步更新群组通话设备状态。

        Args:
            group_id: 群组 ID
            is_camera: 摄像头是否开启
            is_microphone: 麦克风是否开启
            is_share_screen: 是否屏幕共享

        Returns:
            Dict[str, Any]: 操作结果
        """
        data = {
            "groupId": group_id,
            "isCamera": is_camera,
            "isMicroPhone": is_microphone,
            "isShareScreen": is_share_screen,
        }
        return await self._http.arequest(
            "POST", "/api/webrtc/group/device", json_data=data
        )

    @require_login
    def webrtc_group_heartbeat(self, group_id: int) -> Dict[str, Any]:
        """发送群组 WebRTC 通话心跳。

        Args:
            group_id: 群组 ID

        Returns:
            Dict[str, Any]: 操作结果
        """
        return self._http.request(
            "POST",
            "/api/webrtc/group/heartbeat",
            params={"groupId": group_id},
        )

    @async_require_login
    async def awebrtc_group_heartbeat(self, group_id: int) -> Dict[str, Any]:
        """异步发送群组 WebRTC 通话心跳。

        Args:
            group_id: 群组 ID

        Returns:
            Dict[str, Any]: 操作结果
        """
        return await self._http.arequest(
            "POST",
            "/api/webrtc/group/heartbeat",
            params={"groupId": group_id},
        )

    @require_login
    def webrtc_group_info(self, group_id: int) -> Dict[str, Any]:
        """获取群组通话信息。

        Args:
            group_id: 群组 ID

        Returns:
            Dict[str, Any]: 通话信息
        """
        return self._http.request(
            "GET",
            "/api/webrtc/group/info",
            params={"groupId": group_id},
        )

    @async_require_login
    async def awebrtc_group_info(self, group_id: int) -> Dict[str, Any]:
        """异步获取群组通话信息。

        Args:
            group_id: 群组 ID

        Returns:
            Dict[str, Any]: 通话信息
        """
        return await self._http.arequest(
            "GET",
            "/api/webrtc/group/info",
            params={"groupId": group_id},
        )

    # ======================================================================
    # 高级通话接口
    # ======================================================================

    def create_call(
        self,
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
        mode: Union[str, RTCMode] = RTCMode.VIDEO,
        is_caller: bool = True,
    ) -> RTCCallSession:
        """创建通话会话（高级接口）。

        Args:
            user_id: 私聊对方用户 ID（与 group_id 二选一）
            group_id: 群聊群组 ID（与 user_id 二选一）
            mode: 通话模式（"voice"/"audio"/"video" 或 RTCMode）
            is_caller: 是否为主叫方

        Returns:
            RTCCallSession: 通话会话对象

        Raises:
            ValidationError: 参数错误（未指定或同时指定 user_id 和 group_id）

        示例（私聊语音通话）：
            >>> call = im.create_call(user_id=123, mode="voice")
            >>> await call.start()
            >>> await asyncio.sleep(60)
            >>> await call.hangup()

        示例（AI 实时流通话）：
            >>> async def ai_process(audio: bytes) -> bytes:
            ...     return await my_model.infer(audio)
            >>> call = im.create_call(user_id=123, mode="voice")
            >>> call.set_audio_processor(ai_process)
            >>> await call.start()
        """
        if user_id is None and group_id is None:
            raise ValidationError("必须指定 user_id 或 group_id")
        if user_id is not None and group_id is not None:
            raise ValidationError("user_id 和 group_id 不能同时指定")

        rtc_mode = self._resolve_rtc_mode(mode)
        session = RTCCallSession(
            sdk=self,
            user_id=user_id,
            group_id=group_id,
            mode=rtc_mode,
            is_caller=is_caller,
        )
        self._active_calls[session.session_info.session_id or ""] = session
        return session

    def create_incoming_call(
        self,
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
        mode: Union[str, RTCMode] = RTCMode.VIDEO,
    ) -> RTCCallSession:
        """创建来电会话（被叫方使用）。

        Args:
            user_id: 主叫方用户 ID
            group_id: 群组 ID
            mode: 通话模式

        Returns:
            RTCCallSession: 通话会话对象
        """
        return self.create_call(
            user_id=user_id,
            group_id=group_id,
            mode=mode,
            is_caller=False,
        )

    @staticmethod
    def _resolve_rtc_mode(mode: Union[str, RTCMode]) -> RTCMode:
        """将字符串或枚举值解析为 RTCMode 枚举。

        Args:
            mode: 字符串或 RTCMode 枚举值

        Returns:
            RTCMode: 解析后的通话模式
        """
        if isinstance(mode, RTCMode):
            return mode
        try:
            return RTCMode(mode)
        except ValueError:
            return RTCMode.VIDEO

    # ======================================================================
    # 验证码相关
    # ======================================================================

    def get_captcha_img(self) -> CaptchaCode:
        """获取图片验证码。

        Returns:
            CaptchaCode: 验证码对象
        """
        data = self._http.request("POST", "/api/captcha/img/code")
        return CaptchaCode.from_dict(data)

    async def aget_captcha_img(self) -> CaptchaCode:
        """异步获取图片验证码。

        Returns:
            CaptchaCode: 验证码对象
        """
        data = await self._http.arequest("POST", "/api/captcha/img/code")
        return CaptchaCode.from_dict(data)

    def verify_captcha_img(self, captcha_id: str, code: str) -> bool:
        """验证图片验证码。

        Args:
            captcha_id: 验证码 ID
            code: 用户输入的验证码

        Returns:
            bool: 是否验证成功
        """
        result = self._http.request(
            "GET",
            "/api/captcha/img/vertify",
            params={"id": captcha_id, "code": code},
        )
        return bool(result)

    async def averify_captcha_img(self, captcha_id: str, code: str) -> bool:
        """异步验证图片验证码。

        Args:
            captcha_id: 验证码 ID
            code: 用户输入的验证码

        Returns:
            bool: 是否验证成功
        """
        result = await self._http.arequest(
            "GET",
            "/api/captcha/img/vertify",
            params={"id": captcha_id, "code": code},
        )
        return bool(result)

    def send_sms_captcha(
        self,
        phone: str,
        captcha_id: Optional[str] = None,
        captcha_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """发送短信验证码。

        Args:
            phone: 手机号码
            captcha_id: 图片验证码 ID（需要图片验证时提供）
            captcha_code: 图片验证码（需要图片验证时提供）

        Returns:
            Dict[str, Any]: 发送结果
        """
        data: Dict[str, Any] = {"phone": phone}
        if captcha_id and captcha_code:
            data["id"] = captcha_id
            data["code"] = captcha_code
        return self._http.request(
            "POST", "/api/captcha/sms/code", json_data=data
        )

    async def asend_sms_captcha(
        self,
        phone: str,
        captcha_id: Optional[str] = None,
        captcha_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """异步发送短信验证码。

        Args:
            phone: 手机号码
            captcha_id: 图片验证码 ID（可选）
            captcha_code: 图片验证码（可选）

        Returns:
            Dict[str, Any]: 发送结果
        """
        data: Dict[str, Any] = {"phone": phone}
        if captcha_id and captcha_code:
            data["id"] = captcha_id
            data["code"] = captcha_code
        return await self._http.arequest(
            "POST", "/api/captcha/sms/code", json_data=data
        )

    def verify_sms_captcha(self, phone: str, code: str) -> bool:
        """验证短信验证码。

        Args:
            phone: 手机号
            code: 验证码

        Returns:
            bool: 是否验证成功
        """
        result = self._http.request(
            "GET",
            "/api/captcha/sms/vertify",
            params={"id": phone, "code": code},
        )
        return bool(result)

    async def averify_sms_captcha(self, phone: str, code: str) -> bool:
        """异步验证短信验证码。

        Args:
            phone: 手机号
            code: 验证码

        Returns:
            bool: 是否验证成功
        """
        result = await self._http.arequest(
            "GET",
            "/api/captcha/sms/vertify",
            params={"id": phone, "code": code},
        )
        return bool(result)

    def send_email_captcha(self, email: str) -> Dict[str, Any]:
        """发送邮件验证码。

        Args:
            email: 邮箱地址

        Returns:
            Dict[str, Any]: 发送结果
        """
        data = {"email": email}
        return self._http.request(
            "POST", "/api/captcha/mail/code", json_data=data
        )

    async def asend_email_captcha(self, email: str) -> Dict[str, Any]:
        """异步发送邮件验证码。

        Args:
            email: 邮箱地址

        Returns:
            Dict[str, Any]: 发送结果
        """
        data = {"email": email}
        return await self._http.arequest(
            "POST", "/api/captcha/mail/code", json_data=data
        )

    def verify_email_captcha(self, email: str, code: str) -> bool:
        """验证邮件验证码。

        Args:
            email: 邮箱地址
            code: 验证码

        Returns:
            bool: 是否验证成功
        """
        result = self._http.request(
            "GET",
            "/api/captcha/mail/vertify",
            params={"id": email, "code": code},
        )
        return bool(result)

    async def averify_email_captcha(self, email: str, code: str) -> bool:
        """异步验证邮件验证码。

        Args:
            email: 邮箱地址
            code: 验证码

        Returns:
            bool: 是否验证成功
        """
        result = await self._http.arequest(
            "GET",
            "/api/captcha/mail/vertify",
            params={"id": email, "code": code},
        )
        return bool(result)

    # ======================================================================
    # 投诉举报
    # ======================================================================

    @require_login
    def initiate_complaint(
        self,
        complaint_type: int,
        target_id: int,
        target_type: str,
        description: str,
        evidence: Optional[List[str]] = None,
        target_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """发起投诉举报。

        Args:
            complaint_type: 投诉类型（1-用户，2-群组，3-消息）
            target_id: 被举报目标 ID
            target_type: 目标类型（user/group/message）
            description: 投诉描述
            evidence: 证据图片 URL 列表（可选）
            target_name: 被举报目标名称（可选）

        Returns:
            Dict[str, Any]: 投诉结果
        """
        data: Dict[str, Any] = {
            "type": complaint_type,
            "targetId": target_id,
            "targetType": target_type,
            "content": description,
        }
        if evidence:
            data["images"] = evidence
        if target_name:
            data["targetName"] = target_name
        return self._http.request(
            "POST", "/api/complaint/initiate", json_data=data
        )

    @async_require_login
    async def ainitiate_complaint(
        self,
        complaint_type: int,
        target_id: int,
        target_type: str,
        description: str,
        evidence: Optional[List[str]] = None,
        target_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """异步发起投诉举报。

        Args:
            complaint_type: 投诉类型
            target_id: 被举报目标 ID
            target_type: 目标类型
            description: 投诉描述
            evidence: 证据图片 URL 列表（可选）
            target_name: 被举报目标名称（可选）

        Returns:
            Dict[str, Any]: 投诉结果
        """
        data: Dict[str, Any] = {
            "type": complaint_type,
            "targetId": target_id,
            "targetType": target_type,
            "content": description,
        }
        if evidence:
            data["images"] = evidence
        if target_name:
            data["targetName"] = target_name
        return await self._http.arequest(
            "POST", "/api/complaint/initiate", json_data=data
        )

    # ======================================================================
    # 系统配置
    # ======================================================================

    def get_system_config(self) -> SystemConfig:
        """获取系统配置（注册方式、WebRTC 配置等）。

        Returns:
            SystemConfig: 系统配置对象
        """
        data = self._http.request("GET", "/api/system/config")
        return SystemConfig.from_dict(data)

    async def aget_system_config(self) -> SystemConfig:
        """异步获取系统配置。

        Returns:
            SystemConfig: 系统配置对象
        """
        data = await self._http.arequest("GET", "/api/system/config")
        return SystemConfig.from_dict(data)

    # ======================================================================
    # 消息监听
    # ======================================================================

    @require_login
    def on_message(
        self, handler: Union[MessageHandler, AsyncMessageHandler]
    ) -> "BoxIM":
        """注册消息处理器。

        Args:
            handler: 消息处理函数，签名为 (msg_data, is_group)

        Returns:
            返回 self 以支持链式调用

        示例：
            >>> def my_handler(msg, is_group):
            ...     print(f"收到消息: {msg}")
            >>> im.on_message(my_handler).listen_sync()
        """
        self._ws.add_handler(handler)
        return self

    @require_login
    def off_message(
        self, handler: Union[MessageHandler, AsyncMessageHandler]
    ) -> "BoxIM":
        """移除消息处理器。

        Args:
            handler: 要移除的消息处理函数

        Returns:
            返回 self 以支持链式调用
        """
        self._ws.remove_handler(handler)
        return self

    def on_event(self, event: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """事件装饰器，用于注册 WebSocket 事件监听器。

        Args:
            event: 事件名称（如 "message"/"connected"/"disconnected" 等）

        Returns:
            装饰器函数

        示例：
            >>> @im.on_event("message")
            ... async def handler(msg, is_group):
            ...     print(msg)
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._ws.on(event, func)
            return func

        return decorator

    @require_login
    async def listen(self) -> None:
        """开始监听 WebSocket 消息（阻塞，直到中断）。

        示例：
            >>> im = BoxIM().login("user", "pass")
            >>> im.on_message(handler)
            >>> await im.listen()
        """
        await self._ws.start()
        try:
            while True:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            await self._ws.stop()

    @require_login
    def listen_sync(self) -> None:
        """同步方式监听消息（阻塞，直到 Ctrl+C 中断）。

        示例：
            >>> im = BoxIM().login("user", "pass")
            >>> im.on_message(handler).listen_sync()
        """
        try:
            asyncio.run(self.listen())
        except KeyboardInterrupt:
            pass

    @require_login
    async def start_listening(self) -> "BoxIM":
        """非阻塞方式启动 WebSocket 监听。

        Returns:
            返回 self 以支持链式调用

        示例：
            >>> await im.start_listening()
            >>> # 继续执行其他逻辑
            >>> await im.stop_listening()
        """
        await self._ws.start()
        return self

    async def stop_listening(self) -> "BoxIM":
        """停止 WebSocket 监听。

        Returns:
            返回 self 以支持链式调用
        """
        await self._ws.stop()
        return self

    # ======================================================================
    # 内部工具方法
    # ======================================================================

    def _get_user_id(self) -> int:
        """获取当前登录用户 ID。

        优先从令牌存储读取，读取失败时调用 API 获取。

        Returns:
            int: 当前用户 ID
        """
        if hasattr(self._token_store, "get_int"):
            user_id = self._token_store.get_int("USER_ID")  # type: ignore[attr-defined]
            if user_id:
                return user_id
        if hasattr(self._token_store, "get"):
            raw = self._token_store.get("USER_ID")  # type: ignore[attr-defined]
            if raw:
                try:
                    return int(raw)
                except (ValueError, TypeError):
                    pass

        user_info = self.get_me()
        user_id = user_info.get("id", 0)
        self._save_user_id(user_id)
        return user_id


# ============================================================================
# 便捷函数
# ============================================================================


def quick_login(
    username: str,
    password: str,
    base_url: Optional[str] = None,
    debug: bool = False,
) -> BoxIM:
    """快速登录便捷函数。

    Args:
        username: 用户名/邮箱/手机号
        password: 密码
        base_url: API 基础 URL（可选）
        debug: 是否开启调试模式

    Returns:
        BoxIM: 已登录的 BoxIM 实例

    示例：
        >>> im = quick_login("user", "pass")
        >>> im.send_text(123, "Hi")
    """
    kwargs: Dict[str, Any] = {"debug": debug}
    if base_url:
        kwargs["base_url"] = base_url
    return BoxIM(**kwargs).login(username, password)


async def aquick_login(
    username: str,
    password: str,
    base_url: Optional[str] = None,
    debug: bool = False,
) -> BoxIM:
    """异步快速登录便捷函数。

    Args:
        username: 用户名/邮箱/手机号
        password: 密码
        base_url: API 基础 URL（可选）
        debug: 是否开启调试模式

    Returns:
        BoxIM: 已登录的 BoxIM 实例

    示例：
        >>> im = await aquick_login("user", "pass")
        >>> await im.asend_text(123, "Hi")
    """
    kwargs: Dict[str, Any] = {"debug": debug}
    if base_url:
        kwargs["base_url"] = base_url
    return await BoxIM(**kwargs).alogin(username, password)


__all__ = [
    "BoxIM",
    "quick_login",
    "aquick_login",
]
