from __future__ import annotations

import sys
import threading
import types
from typing import Any, Callable, Dict, List, Optional

from boxim.boxim import (
    BoxIM,
    aquick_login,
    quick_login,
)
from boxim.util import (
    AsyncAudioStream,
    AsyncBytesStreamAdapter,
    AsyncCallbackAudioStream,
    AsyncMessageHandler,
    AsyncStreamCallback,
    AsyncVideoStream,
    AudioStream,
    AuthError,
    BoxIMError,
    BytesStreamAdapter,
    CallbackAudioStream,
    ChatType,
    ComplaintType,
    ConfigError,
    Container,
    EnvManager,
    EventEmitter,
    FileAudioStream,
    FileUploader,
    Friend,
    FriendRequest,
    FriendRequestStatus,
    Group,
    HTTPTransport,
    MediaProcessor,
    MediaProcessorWithVideo,
    Message,
    MessageBuilder,
    MessageHandler,
    MessageType,
    NetworkError,
    QRLoginInfo,
    QRLoginStatus,
    QueueAudioStream,
    RTCError,
    RTCMode,
    RTCSessionInfo,
    RTCState,
    RegistrationMode,
    SDKConfig,
    SilenceAudioStream,
    Sticker,
    StickerAlbum,
    StreamCallback,
    StreamError,
    SystemConfig,
    SystemMessage,
    TerminalType,
    TimeoutError,
    TokenInfo,
    TokenStore,
    ToneAudioStream,
    UploadResult,
    User,
    UserSex,
    ValidationError,
    VideoStream,
    WebSocketCommand,
    WebSocketTransport,
    async_require_login,
    auto_retry,
    emoji_util,
    require_login,
    setup_logging,
    validate_params,
    RTCCallSession,
)

__version__ = "3.0.0"
__author__ = "nichengfuben"
__license__ = "MIT"


# ============================================================================
# 全局实例管理器
# ============================================================================


class _InstanceManager:
    """线程安全的全局 BoxIM 实例管理器。

    支持多命名实例管理和当前活跃实例切换。
    """

    _DEFAULT = "__default__"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._instances: Dict[str, BoxIM] = {}
        self._current: Optional[str] = None

    def init(
        self,
        username: str,
        password: str,
        name: Optional[str] = None,
        config: Optional[SDKConfig] = None,
        terminal: TerminalType = TerminalType.WEB,
        **kw: Any,
    ) -> BoxIM:
        """初始化全局默认实例并同步登录。

        Args:
            username: 用户名
            password: 密码
            name: 实例名称（默认为 "__default__"）
            config: SDK 配置
            terminal: 终端类型
            **kw: 透传给 BoxIM 构造函数的额外参数

        Returns:
            BoxIM: 已登录的实例
        """
        return self._register(
            BoxIM(config=config, **kw).login(
                username, password, terminal=terminal
            ),
            name,
        )

    async def ainit(
        self,
        username: str,
        password: str,
        name: Optional[str] = None,
        config: Optional[SDKConfig] = None,
        terminal: TerminalType = TerminalType.WEB,
        **kw: Any,
    ) -> BoxIM:
        """异步初始化全局默认实例并登录。

        Args:
            username: 用户名
            password: 密码
            name: 实例名称
            config: SDK 配置
            terminal: 终端类型
            **kw: 透传给 BoxIM 构造函数的额外参数

        Returns:
            BoxIM: 已登录的实例
        """
        im = BoxIM(config=config, **kw)
        await im.alogin(username, password, terminal=terminal)
        return self._register(im, name)

    def create(
        self,
        username: str,
        password: str,
        name: str = _DEFAULT,
        config: Optional[SDKConfig] = None,
        terminal: TerminalType = TerminalType.WEB,
        set_current: bool = True,
        **kw: Any,
    ) -> BoxIM:
        """创建并注册命名实例（同步登录）。

        Args:
            username: 用户名
            password: 密码
            name: 实例名称
            config: SDK 配置
            terminal: 终端类型
            set_current: 是否设为当前活跃实例
            **kw: 透传给 BoxIM 构造函数的额外参数

        Returns:
            BoxIM: 已登录的实例
        """
        im = BoxIM(config=config, **kw).login(
            username, password, terminal=terminal
        )
        return self._register(im, name, set_current)

    async def acreate(
        self,
        username: str,
        password: str,
        name: str = _DEFAULT,
        config: Optional[SDKConfig] = None,
        terminal: TerminalType = TerminalType.WEB,
        set_current: bool = True,
        **kw: Any,
    ) -> BoxIM:
        """异步创建并注册命名实例。

        Args:
            username: 用户名
            password: 密码
            name: 实例名称
            config: SDK 配置
            terminal: 终端类型
            set_current: 是否设为当前活跃实例
            **kw: 透传给 BoxIM 构造函数的额外参数

        Returns:
            BoxIM: 已登录的实例
        """
        im = BoxIM(config=config, **kw)
        await im.alogin(username, password, terminal=terminal)
        return self._register(im, name, set_current)

    def register(
        self,
        im: BoxIM,
        name: Optional[str] = None,
        set_current: bool = True,
    ) -> BoxIM:
        """注册已有 BoxIM 实例。

        Args:
            im: 已初始化的 BoxIM 实例
            name: 实例名称
            set_current: 是否设为当前活跃实例

        Returns:
            BoxIM: 传入的实例
        """
        return self._register(im, name, set_current)

    def _register(
        self,
        im: BoxIM,
        name: Optional[str] = None,
        set_current: bool = True,
    ) -> BoxIM:
        """内部注册逻辑（线程安全）。

        Args:
            im: BoxIM 实例
            name: 实例名称
            set_current: 是否设为当前活跃实例

        Returns:
            BoxIM: 传入的实例
        """
        key = name or self._DEFAULT
        with self._lock:
            self._instances[key] = im
            if set_current or self._current is None:
                self._current = key
        return im

    def get_instance(self, name: Optional[str] = None) -> BoxIM:
        """获取指定名称的实例，未初始化时抛出异常。

        Args:
            name: 实例名称；为 None 时获取当前活跃实例

        Returns:
            BoxIM: 实例对象

        Raises:
            BoxIMError: 实例不存在或未初始化
        """
        with self._lock:
            key = name or self._current
            if key is None or key not in self._instances:
                raise BoxIMError(
                    "BoxIM 未初始化，请先调用 boxim.init() 或 BoxIM().login()"
                )
            return self._instances[key]

    # get 是 get_instance 的别名
    get = get_instance

    def use(self, name: str) -> BoxIM:
        """切换当前活跃实例。

        Args:
            name: 要切换到的实例名称

        Returns:
            BoxIM: 切换后的活跃实例

        Raises:
            BoxIMError: 实例名称不存在
        """
        with self._lock:
            if name not in self._instances:
                raise BoxIMError(
                    f"实例 '{name}' 不存在，"
                    f"已注册: {list(self._instances.keys())}"
                )
            self._current = name
            return self._instances[name]

    def list_instances(self) -> List[str]:
        """列出所有已注册的实例名称。

        Returns:
            List[str]: 实例名称列表
        """
        with self._lock:
            return list(self._instances.keys())

    def has(self, name: str) -> bool:
        """检查指定名称的实例是否已注册。

        Args:
            name: 实例名称

        Returns:
            bool: 是否已注册
        """
        with self._lock:
            return name in self._instances

    @property
    def is_initialized(self) -> bool:
        """是否已有任何实例完成初始化。"""
        with self._lock:
            return bool(self._instances)

    @property
    def current_name(self) -> Optional[str]:
        """当前活跃实例名称。"""
        with self._lock:
            return self._current

    def remove(self, name: str) -> None:
        """移除并关闭指定实例（同步）。

        Args:
            name: 要移除的实例名称
        """
        with self._lock:
            im = self._instances.pop(name, None)
            if self._current == name:
                keys = list(self._instances.keys())
                self._current = keys[0] if keys else None
        if im is not None:
            try:
                im.close()
            except Exception:
                pass

    async def aremove(self, name: str) -> None:
        """异步移除并关闭指定实例。

        Args:
            name: 要移除的实例名称
        """
        with self._lock:
            im = self._instances.pop(name, None)
            if self._current == name:
                keys = list(self._instances.keys())
                self._current = keys[0] if keys else None
        if im is not None:
            try:
                await im.aclose()
            except Exception:
                pass

    def destroy(self) -> None:
        """销毁所有实例并重置管理器（同步）。"""
        with self._lock:
            instances = list(self._instances.values())
            self._instances.clear()
            self._current = None
        for im in instances:
            try:
                im.close()
            except Exception:
                pass

    async def adestroy(self) -> None:
        """异步销毁所有实例并重置管理器。"""
        with self._lock:
            instances = list(self._instances.values())
            self._instances.clear()
            self._current = None
        for im in instances:
            try:
                await im.aclose()
            except Exception:
                pass

    def reset(self) -> None:
        """重置管理器（等同于 destroy）。"""
        self.destroy()


_mgr = _InstanceManager()


# ============================================================================
# 模块代理：将 boxim.xxx() 转发到当前活跃 BoxIM 实例
# ============================================================================


class _BoxIMModule(types.ModuleType):
    """模块级代理。

    拦截属性访问，将未定义的属性自动代理到当前活跃 BoxIM 实例，
    实现 ``import boxim; boxim.send_text(...)`` 的极简调用模式。
    """

    _MANAGER_METHODS = frozenset({
        "init", "ainit", "create", "acreate", "register",
        "get_instance", "get", "use", "list_instances", "has",
        "is_initialized", "current_name", "remove", "aremove",
        "destroy", "adestroy", "reset",
    })

    def __getattr__(self, name: str) -> Any:
        # 1. 管理器方法直接暴露为模块函数
        if name in self._MANAGER_METHODS:
            attr = getattr(_mgr, name, None)
            if attr is not None:
                return attr

        # 2. on_event 需要转发到当前活跃实例
        if name == "on_event":
            return _mgr.get_instance().on_event

        # 3. listen 系列异步入口
        if name == "listen":
            async def _listen() -> None:
                await _mgr.get_instance().listen()
            return _listen

        if name == "start_listening":
            async def _start() -> BoxIM:
                return await _mgr.get_instance().start_listening()
            return _start

        if name == "stop_listening":
            async def _stop() -> BoxIM:
                return await _mgr.get_instance().stop_listening()
            return _stop

        # 4. 代理到当前活跃实例的方法/属性
        if _mgr.is_initialized:
            try:
                im = _mgr.get_instance()
                return getattr(im, name)
            except (BoxIMError, AttributeError):
                pass

        raise AttributeError(f"module 'boxim' has no attribute '{name}'")

    def __dir__(self) -> List[str]:
        """支持 dir() 自动补全。"""
        base = list(super().__dir__())
        base.extend(self._MANAGER_METHODS)
        if _mgr.is_initialized:
            try:
                im = _mgr.get_instance()
                base.extend(
                    a for a in dir(im)
                    if not a.startswith("_") and a not in base
                )
            except BoxIMError:
                pass
        return base


# ============================================================================
# 替换 sys.modules 中的模块对象为代理实例
# ============================================================================

_this_module = sys.modules[__name__]
_proxy_module = _BoxIMModule(__name__, __doc__)

# 将当前模块的所有已定义属性复制到代理模块
for _attr_name in list(vars(_this_module).keys()):
    if not _attr_name.startswith("__") or _attr_name in (
        "__version__",
        "__author__",
        "__license__",
        "__all__",
        "__file__",
        "__spec__",
        "__path__",
        "__package__",
        "__loader__",
        "__builtins__",
    ):
        try:
            setattr(_proxy_module, _attr_name, getattr(_this_module, _attr_name))
        except (AttributeError, TypeError):
            pass

# 确保关键元属性存在
_proxy_module.__version__ = __version__
_proxy_module.__author__ = __author__
_proxy_module.__license__ = __license__
_proxy_module.__package__ = __package__

if hasattr(_this_module, "__path__"):
    _proxy_module.__path__ = _this_module.__path__  # type: ignore[attr-defined]
if hasattr(_this_module, "__file__"):
    _proxy_module.__file__ = _this_module.__file__
if hasattr(_this_module, "__spec__"):
    _proxy_module.__spec__ = _this_module.__spec__

sys.modules[__name__] = _proxy_module


# ============================================================================
# __all__
# ============================================================================

__all__ = [
    # ---- 核心类 ----
    "BoxIM", "RTCCallSession", "quick_login", "aquick_login",
    # ---- 全局管理 ----
    "init", "ainit", "create", "acreate", "register",
    "get_instance", "get", "use",
    "list_instances", "has", "is_initialized", "current_name",
    "remove", "aremove", "destroy", "adestroy", "reset",
    # ---- 枚举 ----
    "MessageType", "TerminalType", "FriendRequestStatus", "ComplaintType",
    "UserSex", "RegistrationMode", "ChatType", "RTCMode", "RTCState",
    "QRLoginStatus", "WebSocketCommand",
    # ---- 异常 ----
    "BoxIMError", "AuthError", "NetworkError", "ValidationError",
    "RTCError", "StreamError", "ConfigError", "TimeoutError",
    # ---- 数据模型 ----
    "User", "Friend", "FriendRequest", "Group", "Message",
    "SystemMessage", "CaptchaCode", "StickerAlbum", "Sticker",
    "QRLoginInfo", "SystemConfig", "TokenInfo", "RTCSessionInfo",
    "UploadResult",
    # ---- 配置 ----
    "SDKConfig", "EnvManager",
    # ---- 协议 ----
    "TokenStore", "AudioStream", "AsyncAudioStream",
    "VideoStream", "AsyncVideoStream",
    "MediaProcessor", "MediaProcessorWithVideo",
    # ---- 事件 ----
    "EventEmitter",
    # ---- 流适配器 ----
    "BytesStreamAdapter", "AsyncBytesStreamAdapter",
    "CallbackAudioStream", "AsyncCallbackAudioStream",
    "QueueAudioStream", "FileAudioStream",
    "SilenceAudioStream", "ToneAudioStream",
    # ---- 传输层 ----
    "HTTPTransport", "WebSocketTransport",
    # ---- 工具 ----
    "FileUploader", "MessageBuilder", "Container", "emoji_util",
    # ---- 装饰器 ----
    "require_login", "async_require_login", "auto_retry", "validate_params",
    # ---- 日志 ----
    "setup_logging",
    # ---- 类型 ----
    "MessageHandler", "AsyncMessageHandler",
    "StreamCallback", "AsyncStreamCallback",
]
