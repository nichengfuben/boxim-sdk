from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import List

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(*args: object, **kwargs: object) -> None:  # type: ignore[misc]
        """dotenv 不可用时的空实现。"""


@dataclass
class SDKConfig:
    """SDK 全局配置类。

    所有配置项均可通过构造参数或环境变量覆盖。

    Attributes:
        base_url: API 服务器基础 URL
        ws_url: WebSocket 服务器 URL
        timeout: HTTP 请求超时（秒）
        max_retries: HTTP 最大重试次数
        retry_backoff_factor: 重试退避系数
        retry_status_forcelist: 触发重试的 HTTP 状态码列表
        max_image_size: 图片最大字节数
        max_file_size: 文件最大字节数
        max_video_size: 视频最大字节数
        ws_reconnect_delay: WebSocket 初始重连延迟（秒）
        ws_max_reconnect_delay: WebSocket 最大重连延迟（秒）
        ws_heartbeat_interval: WebSocket 心跳间隔（秒）
        ws_ping_interval: WebSocket ping 间隔（秒）
        ws_ping_timeout: WebSocket ping 超时（秒）
        ws_auth_timeout: WebSocket 认证超时（秒）
        ws_auto_reconnect: 是否自动重连
        auto_refresh_token: 是否自动刷新令牌
        token_refresh_margin: 令牌刷新提前量（秒）
        max_large_group_member: 大群最大人数
        max_normal_group_member: 普通群最大人数
        log_level: 日志级别
        log_format: 日志格式字符串
        debug: 是否开启调试模式
        ssl_verify: 是否验证 SSL 证书
        stream_chunk_size: 流读取块大小（字节）
        stream_sample_rate: 音频采样率
        stream_channels: 音频声道数
        stream_sample_width: 音频采样位宽（字节）
        stream_buffer_size: 流缓冲区大小（字节）
        rtc_heartbeat_interval: RTC 心跳间隔（秒）
        rtc_call_timeout: RTC 通话超时（秒）
        user_agent: HTTP User-Agent 字符串
    """

    base_url: str = "https://www.boximchat.com/api"
    ws_url: str = "wss://www.boximchat.com/im"

    timeout: int = 30
    max_retries: int = 3
    retry_backoff_factor: float = 0.3
    retry_status_forcelist: List[int] = field(
        default_factory=lambda: [429, 500, 502, 503, 504]
    )

    max_image_size: int = 10 * 1024 * 1024
    max_file_size: int = 10 * 1024 * 1024
    max_video_size: int = 50 * 1024 * 1024

    ws_reconnect_delay: int = 1
    ws_max_reconnect_delay: int = 300
    ws_heartbeat_interval: int = 20
    ws_ping_interval: int = 20
    ws_ping_timeout: int = 10
    ws_auth_timeout: float = 10.0
    ws_auto_reconnect: bool = True

    auto_refresh_token: bool = True
    token_refresh_margin: int = 60

    max_large_group_member: int = 3000
    max_normal_group_member: int = 500

    log_level: int = logging.INFO
    log_format: str = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
    debug: bool = False

    ssl_verify: bool = False

    stream_chunk_size: int = 4096
    stream_sample_rate: int = 16000
    stream_channels: int = 1
    stream_sample_width: int = 2
    stream_buffer_size: int = 32768

    rtc_heartbeat_interval: int = 10
    rtc_call_timeout: int = 60

    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36 BoxIMSDK/3.0.0"
    )

    def __post_init__(self) -> None:
        """初始化后处理：调试模式下自动设置 DEBUG 日志级别。"""
        if self.debug:
            self.log_level = logging.DEBUG

    @classmethod
    def from_env(cls, env_file: str = ".env") -> "SDKConfig":
        """从环境变量（及可选的 .env 文件）构造配置对象。

        Args:
            env_file: 环境变量文件路径，文件不存在时跳过加载

        Returns:
            SDKConfig: 从环境变量读取的配置实例
        """
        if os.path.exists(env_file):
            load_dotenv(env_file, override=True)
        return cls(
            base_url=os.getenv("BOXIM_BASE_URL", cls.base_url),
            ws_url=os.getenv("BOXIM_WS_URL", cls.ws_url),
            timeout=int(os.getenv("BOXIM_TIMEOUT", str(cls.timeout))),
            max_retries=int(
                os.getenv("BOXIM_MAX_RETRIES", str(cls.max_retries))
            ),
            debug=os.getenv("BOXIM_DEBUG", "false").lower()
            in ("true", "1", "yes"),
            ssl_verify=os.getenv("BOXIM_SSL_VERIFY", "false").lower()
            in ("true", "1", "yes"),
            auto_refresh_token=os.getenv(
                "BOXIM_AUTO_REFRESH_TOKEN", "true"
            ).lower()
            in ("true", "1", "yes"),
        )


__all__ = ["SDKConfig"]
