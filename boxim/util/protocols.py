from __future__ import annotations

from typing import Optional

try:
    from typing import Protocol, runtime_checkable
except ImportError:  # pragma: no cover
    from typing_extensions import Protocol, runtime_checkable  # type: ignore[assignment]

from boxim.util.models import TokenInfo


@runtime_checkable
class TokenStore(Protocol):
    """令牌存储协议。

    实现此协议可自定义令牌的持久化方式（数据库、Redis、内存等）。
    """

    def save_token(self, token_info: TokenInfo) -> None:
        """保存令牌信息。

        Args:
            token_info: 令牌信息对象
        """
        ...

    def get_token(self) -> Optional[TokenInfo]:
        """获取令牌信息。

        Returns:
            TokenInfo 实例，不存在时返回 None
        """
        ...

    def clear_token(self) -> None:
        """清除令牌信息。"""
        ...


@runtime_checkable
class AudioStream(Protocol):
    """同步音频流协议。

    用于自定义音频数据的读写，适配通话输入/输出流。
    """

    def read(self, size: int) -> bytes:
        """读取音频数据。

        Args:
            size: 要读取的字节数

        Returns:
            读取到的音频字节数据
        """
        ...

    def write(self, data: bytes) -> None:
        """写入音频数据。

        Args:
            data: 要写入的音频字节数据
        """
        ...

    def close(self) -> None:
        """关闭流，释放资源。"""
        ...


@runtime_checkable
class AsyncAudioStream(Protocol):
    """异步音频流协议。

    异步版本的音频流，适用于 asyncio 环境。
    """

    async def read(self, size: int) -> bytes:
        """异步读取音频数据。

        Args:
            size: 要读取的字节数

        Returns:
            读取到的音频字节数据
        """
        ...

    async def write(self, data: bytes) -> None:
        """异步写入音频数据。

        Args:
            data: 要写入的音频字节数据
        """
        ...

    async def close(self) -> None:
        """异步关闭流，释放资源。"""
        ...


@runtime_checkable
class VideoStream(Protocol):
    """同步视频流协议。

    用于自定义视频帧的读写。
    """

    def read_frame(self) -> Optional[bytes]:
        """读取一帧视频数据。

        Returns:
            视频帧字节数据，无数据时返回 None
        """
        ...

    def write_frame(self, data: bytes) -> None:
        """写入一帧视频数据。

        Args:
            data: 视频帧字节数据
        """
        ...

    def close(self) -> None:
        """关闭流，释放资源。"""
        ...


@runtime_checkable
class AsyncVideoStream(Protocol):
    """异步视频流协议。"""

    async def read_frame(self) -> Optional[bytes]:
        """异步读取一帧视频数据。

        Returns:
            视频帧字节数据，无数据时返回 None
        """
        ...

    async def write_frame(self, data: bytes) -> None:
        """异步写入一帧视频数据。

        Args:
            data: 视频帧字节数据
        """
        ...

    async def close(self) -> None:
        """异步关闭流，释放资源。"""
        ...


@runtime_checkable
class MediaProcessor(Protocol):
    """媒体处理器协议（仅音频）。

    用于 AI 实时音频处理，如语音识别、降噪、语音合成等。
    """

    async def process_audio(self, audio_data: bytes) -> bytes:
        """处理音频数据。

        Args:
            audio_data: 原始音频字节数据

        Returns:
            处理后的音频字节数据
        """
        ...


@runtime_checkable
class MediaProcessorWithVideo(Protocol):
    """媒体处理器协议（音频 + 视频）。

    同时支持音频和视频处理。
    """

    async def process_audio(self, audio_data: bytes) -> bytes:
        """处理音频数据。

        Args:
            audio_data: 原始音频字节数据

        Returns:
            处理后的音频字节数据
        """
        ...

    async def process_video(self, video_frame: bytes) -> bytes:
        """处理视频帧数据。

        Args:
            video_frame: 原始视频帧字节数据

        Returns:
            处理后的视频帧字节数据
        """
        ...


__all__ = [
    "TokenStore",
    "AudioStream",
    "AsyncAudioStream",
    "VideoStream",
    "AsyncVideoStream",
    "MediaProcessor",
    "MediaProcessorWithVideo",
]
