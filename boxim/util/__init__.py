from __future__ import annotations

from boxim.util.enums import (
    ChatType,
    ComplaintType,
    FriendRequestStatus,
    MessageType,
    QRLoginStatus,
    RegistrationMode,
    RTCMode,
    RTCState,
    TerminalType,
    UserSex,
    WebSocketCommand,
)
from boxim.util.exceptions import (
    AuthError,
    BoxIMError,
    ConfigError,
    NetworkError,
    RTCError,
    StreamError,
    TimeoutError,
    ValidationError,
)
from boxim.util.models import (
    CaptchaCode,
    Friend,
    FriendRequest,
    Group,
    Message,
    QRLoginInfo,
    RTCSessionInfo,
    Sticker,
    StickerAlbum,
    SystemConfig,
    SystemMessage,
    TokenInfo,
    UploadResult,
    User,
)
from boxim.util.config import SDKConfig
from boxim.util.env import EnvManager
from boxim.util.protocols import (
    AsyncAudioStream,
    AsyncVideoStream,
    AudioStream,
    MediaProcessor,
    MediaProcessorWithVideo,
    TokenStore,
    VideoStream,
)
from boxim.util.events import EventEmitter
from boxim.util.streams import (
    AsyncBytesStreamAdapter,
    AsyncCallbackAudioStream,
    BytesStreamAdapter,
    CallbackAudioStream,
    FileAudioStream,
    QueueAudioStream,
    SilenceAudioStream,
    ToneAudioStream,
)
from boxim.util.container import Container
from boxim.util.transport_http import HTTPTransport
from boxim.util.transport_ws import WebSocketTransport
from boxim.util.uploader import FileUploader
from boxim.util.message_builder import MessageBuilder
from boxim.util.decorators import (
    async_require_login,
    auto_retry,
    require_login,
    validate_params,
)
from boxim.util.logging_util import setup_logging
from boxim.util.rtc import RTCCallSession
from boxim.util import emoji as emoji_util
# 类型别名
from typing import Awaitable, Callable, Dict, Any
MessageHandler = Callable[[Dict[str, Any], bool], None]
AsyncMessageHandler = Callable[[Dict[str, Any], bool], Awaitable[None]]
StreamCallback = Callable[[bytes], None]
AsyncStreamCallback = Callable[[bytes], Awaitable[None]]

__all__ = [
    # 枚举
    "MessageType",
    "TerminalType",
    "FriendRequestStatus",
    "ComplaintType",
    "UserSex",
    "RegistrationMode",
    "ChatType",
    "RTCMode",
    "RTCState",
    "QRLoginStatus",
    "WebSocketCommand",
    # 异常
    "BoxIMError",
    "AuthError",
    "NetworkError",
    "ValidationError",
    "RTCError",
    "StreamError",
    "ConfigError",
    "TimeoutError",
    # 数据模型
    "User",
    "Friend",
    "FriendRequest",
    "Group",
    "Message",
    "SystemMessage",
    "CaptchaCode",
    "StickerAlbum",
    "Sticker",
    "QRLoginInfo",
    "SystemConfig",
    "TokenInfo",
    "RTCSessionInfo",
    "UploadResult",
    # 配置
    "SDKConfig",
    "EnvManager",
    # 协议
    "TokenStore",
    "AudioStream",
    "AsyncAudioStream",
    "VideoStream",
    "AsyncVideoStream",
    "MediaProcessor",
    "MediaProcessorWithVideo",
    "RTCCallSession",
    # 事件
    "EventEmitter",
    # 流适配器
    "BytesStreamAdapter",
    "AsyncBytesStreamAdapter",
    "CallbackAudioStream",
    "AsyncCallbackAudioStream",
    "QueueAudioStream",
    "FileAudioStream",
    "SilenceAudioStream",
    "ToneAudioStream",
    # 传输层
    "HTTPTransport",
    "WebSocketTransport",
    # 工具
    "FileUploader",
    "MessageBuilder",
    "Container",
    "emoji_util",
    # 装饰器
    "require_login",
    "async_require_login",
    "auto_retry",
    "validate_params",
    # 日志
    "setup_logging",
    # 类型
    "MessageHandler",
    "AsyncMessageHandler",
    "StreamCallback",
    "AsyncStreamCallback",
]

