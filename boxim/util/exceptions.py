from __future__ import annotations

from typing import Optional


class BoxIMError(Exception):
    """SDK 基础异常类。

    所有 BoxIM SDK 异常的公共基类，携带可选业务错误码。

    Attributes:
        message: 异常描述信息
        code: 可选的业务错误码
    """

    def __init__(self, message: str, code: Optional[int] = None) -> None:
        self.message = message
        self.code = code
        super().__init__(self.message)

    def __repr__(self) -> str:
        if self.code is not None:
            return (
                f"{self.__class__.__name__}"
                f"(code={self.code}, message={self.message!r})"
            )
        return f"{self.__class__.__name__}(message={self.message!r})"


class AuthError(BoxIMError):
    """认证异常：未登录或令牌失效。"""


class NetworkError(BoxIMError):
    """网络异常：请求失败或连接中断。"""


class ValidationError(BoxIMError):
    """参数验证异常：入参不满足要求。"""


class RTCError(BoxIMError):
    """WebRTC 通话异常。"""


class StreamError(BoxIMError):
    """流处理异常。"""


class ConfigError(BoxIMError):
    """配置异常：依赖未注册或配置错误。"""


class TimeoutError(BoxIMError):
    """超时异常。"""


__all__ = [
    "BoxIMError",
    "AuthError",
    "NetworkError",
    "ValidationError",
    "RTCError",
    "StreamError",
    "ConfigError",
    "TimeoutError",
]
