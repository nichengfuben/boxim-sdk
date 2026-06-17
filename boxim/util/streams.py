from __future__ import annotations

import asyncio
import logging
import math
import struct
import wave
from io import BytesIO
from typing import Any, Awaitable, Callable, Optional

_logger = logging.getLogger("boxim")


class BytesStreamAdapter:
    """字节流适配器（同步）。

    将 bytes 数据包装为 AudioStream 协议兼容对象。

    示例：
        >>> stream = BytesStreamAdapter(b"hello")
        >>> stream.read(3)
        b'hel'
    """

    def __init__(self, data: bytes = b"") -> None:
        self._buffer = BytesIO(data)

    def read(self, size: int) -> bytes:
        """读取指定字节数的数据。

        Args:
            size: 要读取的字节数

        Returns:
            读取到的字节数据
        """
        return self._buffer.read(size)

    def write(self, data: bytes) -> None:
        """向缓冲区写入字节数据。

        Args:
            data: 要写入的字节数据
        """
        self._buffer.write(data)

    def close(self) -> None:
        """关闭缓冲区。"""
        self._buffer.close()

    def getvalue(self) -> bytes:
        """获取缓冲区全部数据。

        Returns:
            缓冲区中所有字节数据
        """
        return self._buffer.getvalue()

    def seek(self, pos: int) -> None:
        """移动读写指针。

        Args:
            pos: 目标位置
        """
        self._buffer.seek(pos)


class AsyncBytesStreamAdapter:
    """字节流适配器（异步）。

    将 bytes 数据包装为 AsyncAudioStream 协议兼容对象，
    所有操作通过异步锁保证线程安全。
    """

    def __init__(self, data: bytes = b"") -> None:
        self._buffer = BytesIO(data)
        self._lock = asyncio.Lock()

    async def read(self, size: int) -> bytes:
        """异步读取指定字节数的数据。

        Args:
            size: 要读取的字节数

        Returns:
            读取到的字节数据
        """
        async with self._lock:
            return self._buffer.read(size)

    async def write(self, data: bytes) -> None:
        """异步向缓冲区写入字节数据。

        Args:
            data: 要写入的字节数据
        """
        async with self._lock:
            self._buffer.write(data)

    async def close(self) -> None:
        """异步关闭缓冲区。"""
        self._buffer.close()

    def getvalue(self) -> bytes:
        """获取缓冲区全部数据。

        Returns:
            缓冲区中所有字节数据
        """
        return self._buffer.getvalue()


class CallbackAudioStream:
    """回调式音频流（同步）。

    开发者通过回调函数控制音频读写，SDK 在通话过程中自动调用。

    示例：
        >>> def provide_audio(size: int) -> bytes:
        ...     return b"\\x00" * size
        >>> stream = CallbackAudioStream(read_callback=provide_audio)
        >>> stream.read(4)
        b'\\x00\\x00\\x00\\x00'
    """

    def __init__(
        self,
        read_callback: Optional[Callable[[int], bytes]] = None,
        write_callback: Optional[Callable[[bytes], None]] = None,
    ) -> None:
        self._read_callback = read_callback
        self._write_callback = write_callback
        self._closed = False

    def read(self, size: int) -> bytes:
        """通过读取回调获取音频数据。

        Args:
            size: 要读取的字节数

        Returns:
            回调返回的音频字节数据；流已关闭或无回调时返回静音数据
        """
        if self._closed or self._read_callback is None:
            return b""
        try:
            return self._read_callback(size)
        except Exception as exc:
            _logger.error("音频读取回调异常: %s", exc)
            return b"\x00" * size

    def write(self, data: bytes) -> None:
        """通过写入回调输出音频数据。

        Args:
            data: 要写入的音频字节数据
        """
        if self._closed or self._write_callback is None:
            return
        try:
            self._write_callback(data)
        except Exception as exc:
            _logger.error("音频写入回调异常: %s", exc)

    def close(self) -> None:
        """关闭流，后续读写操作将被忽略。"""
        self._closed = True


class AsyncCallbackAudioStream:
    """回调式音频流（异步）。

    异步版本的回调式音频流，适用于 asyncio 环境。

    示例：
        >>> async def provide_audio(size: int) -> bytes:
        ...     return b"\\x00" * size
        >>> stream = AsyncCallbackAudioStream(read_callback=provide_audio)
    """

    def __init__(
        self,
        read_callback: Optional[Callable[[int], Awaitable[bytes]]] = None,
        write_callback: Optional[Callable[[bytes], Awaitable[None]]] = None,
    ) -> None:
        self._read_callback = read_callback
        self._write_callback = write_callback
        self._closed = False

    async def read(self, size: int) -> bytes:
        """异步通过读取回调获取音频数据。

        Args:
            size: 要读取的字节数

        Returns:
            回调返回的音频字节数据；流已关闭或无回调时返回空字节
        """
        if self._closed or self._read_callback is None:
            return b""
        try:
            return await self._read_callback(size)
        except Exception as exc:
            _logger.error("异步音频读取回调异常: %s", exc)
            return b"\x00" * size

    async def write(self, data: bytes) -> None:
        """异步通过写入回调输出音频数据。

        Args:
            data: 要写入的音频字节数据
        """
        if self._closed or self._write_callback is None:
            return
        try:
            await self._write_callback(data)
        except Exception as exc:
            _logger.error("异步音频写入回调异常: %s", exc)

    async def close(self) -> None:
        """异步关闭流。"""
        self._closed = True


class QueueAudioStream:
    """基于队列的异步音频流。

    适用于生产者-消费者模式的音频数据处理。

    示例：
        >>> stream = QueueAudioStream()
        >>> import asyncio
        >>> async def demo():
        ...     await stream.write(b"data")
        ...     return await stream.read(4)
        >>> asyncio.run(demo())
        b'data'
    """

    def __init__(self, max_size: int = 0) -> None:
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=max_size)
        self._buffer = bytearray()
        self._closed = False

    async def read(self, size: int) -> bytes:
        """从队列读取指定大小的数据，不足时等待。

        Args:
            size: 要读取的字节数

        Returns:
            读取到的字节数据；流已关闭且队列为空时返回空字节
        """
        if self._closed and len(self._buffer) == 0 and self._queue.empty():
            return b""

        while len(self._buffer) < size:
            try:
                chunk = await asyncio.wait_for(
                    self._queue.get(), timeout=0.1
                )
                self._buffer.extend(chunk)
            except asyncio.TimeoutError:
                if self._closed:
                    break
            except Exception:
                break

        if not self._buffer:
            return b""

        result = bytes(self._buffer[:size])
        self._buffer = self._buffer[size:]
        return result

    async def write(self, data: bytes) -> None:
        """向队列写入音频数据。

        Args:
            data: 要写入的音频字节数据
        """
        if self._closed:
            return
        await self._queue.put(data)

    async def close(self) -> None:
        """关闭流。"""
        self._closed = True

    @property
    def is_closed(self) -> bool:
        """是否已关闭。"""
        return self._closed


class FileAudioStream:
    """文件音频流。

    从文件读取或向文件写入音频数据，支持 WAV 和原始 PCM 格式。

    示例：
        >>> stream = FileAudioStream("output.pcm", mode="w")
        >>> stream.write(b"\\x00" * 1024)
        >>> stream.close()
    """

    def __init__(
        self,
        file_path: str,
        mode: str = "r",
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2,
    ) -> None:
        self._file_path = file_path
        self._mode = mode
        self._sample_rate = sample_rate
        self._channels = channels
        self._sample_width = sample_width
        self._file: Optional[Any] = None
        self._closed = False
        self._open()

    def _open(self) -> None:
        """打开文件（根据扩展名自动选择 WAV 或原始 PCM）。"""
        if self._mode == "r":
            if self._file_path.endswith(".wav"):
                self._file = wave.open(self._file_path, "rb")
            else:
                self._file = open(self._file_path, "rb")
        else:
            if self._file_path.endswith(".wav"):
                wav_file = wave.open(self._file_path, "wb")
                wav_file.setnchannels(self._channels)
                wav_file.setsampwidth(self._sample_width)
                wav_file.setframerate(self._sample_rate)
                self._file = wav_file
            else:
                self._file = open(self._file_path, "wb")

    def read(self, size: int) -> bytes:
        """读取音频数据。

        Args:
            size: 要读取的字节数

        Returns:
            读取到的音频字节数据
        """
        if self._closed or self._file is None:
            return b""
        try:
            if isinstance(self._file, wave.Wave_read):
                frames = size // (self._channels * self._sample_width)
                return self._file.readframes(frames)
            return self._file.read(size)
        except Exception as exc:
            _logger.error("文件读取异常: %s", exc)
            return b""

    def write(self, data: bytes) -> None:
        """写入音频数据。

        Args:
            data: 要写入的音频字节数据
        """
        if self._closed or self._file is None:
            return
        try:
            if isinstance(self._file, wave.Wave_write):
                self._file.writeframes(data)
            else:
                self._file.write(data)
        except Exception as exc:
            _logger.error("文件写入异常: %s", exc)

    def close(self) -> None:
        """关闭文件，释放资源。"""
        if not self._closed and self._file is not None:
            try:
                self._file.close()
            except Exception:
                pass
        self._closed = True


class SilenceAudioStream:
    """静音音频流。

    生成全零静音数据，用于占位或测试。

    示例：
        >>> stream = SilenceAudioStream()
        >>> stream.read(4)
        b'\\x00\\x00\\x00\\x00'
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2,
    ) -> None:
        self._closed = False

    def read(self, size: int) -> bytes:
        """读取静音数据（全零字节）。

        Args:
            size: 要读取的字节数

        Returns:
            全零字节数据
        """
        if self._closed:
            return b""
        return b"\x00" * size

    def write(self, data: bytes) -> None:
        """丢弃写入数据（无操作）。

        Args:
            data: 忽略的字节数据
        """

    def close(self) -> None:
        """关闭流。"""
        self._closed = True


class ToneAudioStream:
    """音调生成流。

    生成指定频率的正弦波音调，用于通话测试。

    示例：
        >>> stream = ToneAudioStream(frequency=440.0)
        >>> data = stream.read(32)
        >>> len(data)
        32
    """

    def __init__(
        self,
        frequency: float = 440.0,
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2,
        amplitude: float = 0.5,
    ) -> None:
        self._frequency = frequency
        self._sample_rate = sample_rate
        self._channels = channels
        self._sample_width = sample_width
        self._amplitude = amplitude
        self._phase = 0.0
        self._closed = False

    def read(self, size: int) -> bytes:
        """生成并返回指定大小的音调数据。

        Args:
            size: 要读取的字节数

        Returns:
            包含正弦波音调的字节数据
        """
        if self._closed:
            return b""

        num_samples = size // (self._channels * self._sample_width)
        samples = bytearray()
        max_val = (2 ** (self._sample_width * 8 - 1)) - 1

        for _ in range(num_samples):
            value = int(
                self._amplitude
                * max_val
                * math.sin(2 * math.pi * self._phase)
            )
            self._phase += self._frequency / self._sample_rate
            if self._phase >= 1.0:
                self._phase -= 1.0

            sample_bytes = self._encode_sample(value)
            for _ in range(self._channels):
                samples.extend(sample_bytes)

        return bytes(samples[:size])

    def _encode_sample(self, value: int) -> bytes:
        """将采样值编码为字节。

        Args:
            value: 原始采样整数值

        Returns:
            编码后的字节数据
        """
        if self._sample_width == 2:
            clamped = max(-32768, min(32767, value))
            return struct.pack("<h", clamped)
        clamped_u = max(0, min(255, value + 128))
        return struct.pack("B", clamped_u)

    def write(self, data: bytes) -> None:
        """丢弃写入数据（无操作）。

        Args:
            data: 忽略的字节数据
        """

    def close(self) -> None:
        """关闭流。"""
        self._closed = True


__all__ = [
    "BytesStreamAdapter",
    "AsyncBytesStreamAdapter",
    "CallbackAudioStream",
    "AsyncCallbackAudioStream",
    "QueueAudioStream",
    "FileAudioStream",
    "SilenceAudioStream",
    "ToneAudioStream",
]
