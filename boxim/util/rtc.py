from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, List, Optional, Union

from boxim.util.enums import MessageType, RTCMode, RTCState
from boxim.util.events import EventEmitter
from boxim.util.exceptions import RTCError
from boxim.util.models import RTCSessionInfo
from boxim.util.protocols import (
    AsyncAudioStream,
    AsyncVideoStream,
    AudioStream,
    MediaProcessor,
    MediaProcessorWithVideo,
    VideoStream,
)

if TYPE_CHECKING:
    from boxim.boxim import BoxIM

_logger = logging.getLogger("boxim")


class RTCCallSession:
    """RTC 通话会话。

    封装单次通话的完整生命周期，支持：
    - 私聊 / 群聊通话
    - 音频 / 视频流注入
    - AI 实时流处理
    - 自动心跳维持
    - 事件回调

    示例（私聊语音通话）：
        >>> call = im.create_call(user_id=123, mode="voice")
        >>> call.on_connected(lambda: print("已接通"))
        >>> await call.start()
        >>> await call.hangup()

    示例（AI 实时流通话）：
        >>> async def ai_process(audio: bytes) -> bytes:
        ...     return await my_ai.inference(audio)
        >>> call = im.create_call(user_id=123, mode="voice")
        >>> call.set_audio_processor(ai_process)
        >>> await call.start()
    """

    def __init__(
        self,
        sdk: "BoxIM",
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
        mode: RTCMode = RTCMode.VIDEO,
        is_caller: bool = True,
    ) -> None:
        """初始化通话会话。

        Args:
            sdk: BoxIM 实例引用
            user_id: 私聊对方用户 ID
            group_id: 群聊群组 ID
            mode: 通话模式
            is_caller: 是否为主叫方
        """
        self._sdk = sdk
        self._session = RTCSessionInfo(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            group_id=group_id,
            mode=mode,
            state=RTCState.IDLE,
            is_caller=is_caller,
        )
        self._events = EventEmitter()
        self._heartbeat_task: Optional[asyncio.Task[None]] = None
        self._stream_task: Optional[asyncio.Task[None]] = None
        self._input_stream: Optional[Union[AudioStream, AsyncAudioStream]] = None
        self._output_stream: Optional[Union[AudioStream, AsyncAudioStream]] = None
        self._video_input: Optional[Union[VideoStream, AsyncVideoStream]] = None
        self._video_output: Optional[Union[VideoStream, AsyncVideoStream]] = None
        self._audio_processor: Optional[
            Callable[[bytes], Awaitable[bytes]]
        ] = None
        self._video_processor: Optional[
            Callable[[bytes], Awaitable[bytes]]
        ] = None
        self._running = False
        self._config = sdk._config

    # ------------------------------------------------------------------
    # 属性访问
    # ------------------------------------------------------------------

    @property
    def session_info(self) -> RTCSessionInfo:
        """获取会话信息对象。"""
        return self._session

    @property
    def state(self) -> RTCState:
        """获取当前通话状态。"""
        return self._session.state

    @property
    def is_active(self) -> bool:
        """通话是否处于活跃状态（呼叫中/振铃/已接通）。"""
        return self._session.is_active

    @property
    def is_group_call(self) -> bool:
        """是否为群组通话。"""
        return self._session.is_group_call

    @property
    def duration(self) -> float:
        """通话时长（秒），未接通时为 0。"""
        return self._session.duration

    @property
    def events(self) -> EventEmitter:
        """事件发射器，可手动注册自定义事件。"""
        return self._events

    # ------------------------------------------------------------------
    # 流配置
    # ------------------------------------------------------------------

    def set_input_stream(
        self,
        stream: Union[AudioStream, AsyncAudioStream],
    ) -> "RTCCallSession":
        """设置音频输入流（本地发送给对方的音频来源）。

        Args:
            stream: 实现 AudioStream 或 AsyncAudioStream 协议的对象

        Returns:
            返回 self 以支持链式调用
        """
        self._input_stream = stream
        return self

    def set_output_stream(
        self,
        stream: Union[AudioStream, AsyncAudioStream],
    ) -> "RTCCallSession":
        """设置音频输出流（接收到的音频写入此流）。

        Args:
            stream: 实现 AudioStream 或 AsyncAudioStream 协议的对象

        Returns:
            返回 self 以支持链式调用
        """
        self._output_stream = stream
        return self

    def set_video_input(
        self,
        stream: Union[VideoStream, AsyncVideoStream],
    ) -> "RTCCallSession":
        """设置视频输入流（本地发送给对方的视频来源）。

        Args:
            stream: 实现 VideoStream 或 AsyncVideoStream 协议的对象

        Returns:
            返回 self 以支持链式调用
        """
        self._video_input = stream
        return self

    def set_video_output(
        self,
        stream: Union[VideoStream, AsyncVideoStream],
    ) -> "RTCCallSession":
        """设置视频输出流（接收到的视频帧写入此流）。

        Args:
            stream: 实现 VideoStream 或 AsyncVideoStream 协议的对象

        Returns:
            返回 self 以支持链式调用
        """
        self._video_output = stream
        return self

    def set_audio_processor(
        self,
        processor: Callable[[bytes], Awaitable[bytes]],
    ) -> "RTCCallSession":
        """设置 AI 音频处理器（实时流处理）。

        处理器接收原始音频字节，返回处理后的音频字节。
        可用于语音识别、降噪、语音合成等场景。

        Args:
            processor: 异步音频处理函数 (audio_data: bytes) -> bytes

        Returns:
            返回 self 以支持链式调用

        示例：
            >>> async def ai_process(audio: bytes) -> bytes:
            ...     text = await speech_to_text(audio)
            ...     reply = await ai_chat(text)
            ...     return await text_to_speech(reply)
            >>> call.set_audio_processor(ai_process)
        """
        self._audio_processor = processor
        return self

    def set_video_processor(
        self,
        processor: Callable[[bytes], Awaitable[bytes]],
    ) -> "RTCCallSession":
        """设置视频帧处理器。

        Args:
            processor: 异步视频帧处理函数 (frame: bytes) -> bytes

        Returns:
            返回 self 以支持链式调用
        """
        self._video_processor = processor
        return self

    def set_media_processor(
        self,
        processor: Union[MediaProcessor, MediaProcessorWithVideo],
    ) -> "RTCCallSession":
        """通过统一媒体处理器接口设置音视频处理器。

        Args:
            processor: 实现 MediaProcessor 或 MediaProcessorWithVideo 协议的对象

        Returns:
            返回 self 以支持链式调用

        示例：
            >>> class MyAI:
            ...     async def process_audio(self, data: bytes) -> bytes:
            ...         return await model.infer(data)
            >>> call.set_media_processor(MyAI())
        """
        self._audio_processor = processor.process_audio
        if hasattr(processor, "process_video"):
            self._video_processor = processor.process_video  # type: ignore[union-attr]
        return self

    # ------------------------------------------------------------------
    # 事件注册快捷方法
    # ------------------------------------------------------------------

    def on_state_change(
        self,
        callback: Callable[[RTCState, RTCState], Any],
    ) -> "RTCCallSession":
        """注册通话状态变更回调。

        Args:
            callback: 回调函数 (old_state, new_state)

        Returns:
            返回 self 以支持链式调用
        """
        self._events.on("state_change", callback)
        return self

    def on_connected(
        self, callback: Callable[[], Any]
    ) -> "RTCCallSession":
        """注册通话接通回调。

        Args:
            callback: 无参回调函数

        Returns:
            返回 self 以支持链式调用
        """
        self._events.on("connected", callback)
        return self

    def on_ended(self, callback: Callable[[], Any]) -> "RTCCallSession":
        """注册通话结束回调。

        Args:
            callback: 无参回调函数

        Returns:
            返回 self 以支持链式调用
        """
        self._events.on("ended", callback)
        return self

    def on_failed(
        self, callback: Callable[[str], Any]
    ) -> "RTCCallSession":
        """注册通话失败回调。

        Args:
            callback: 回调函数 (reason: str)

        Returns:
            返回 self 以支持链式调用
        """
        self._events.on("failed", callback)
        return self

    def on_audio_receive(
        self, callback: Callable[[bytes], Any]
    ) -> "RTCCallSession":
        """注册音频数据接收回调。

        Args:
            callback: 回调函数 (audio_data: bytes)

        Returns:
            返回 self 以支持链式调用
        """
        self._events.on("audio_receive", callback)
        return self

    def on_video_receive(
        self, callback: Callable[[bytes], Any]
    ) -> "RTCCallSession":
        """注册视频帧接收回调。

        Args:
            callback: 回调函数 (frame_data: bytes)

        Returns:
            返回 self 以支持链式调用
        """
        self._events.on("video_receive", callback)
        return self

    def on_remote_sdp(
        self, callback: Callable[[str], Any]
    ) -> "RTCCallSession":
        """注册远端 SDP 接收回调。

        Args:
            callback: 回调函数 (sdp: str)

        Returns:
            返回 self 以支持链式调用
        """
        self._events.on("remote_sdp", callback)
        return self

    def on_remote_candidate(
        self, callback: Callable[[str], Any]
    ) -> "RTCCallSession":
        """注册远端 ICE Candidate 接收回调。

        Args:
            callback: 回调函数 (candidate: str)

        Returns:
            返回 self 以支持链式调用
        """
        self._events.on("remote_candidate", callback)
        return self

    # ------------------------------------------------------------------
    # 状态管理
    # ------------------------------------------------------------------

    async def _set_state(self, new_state: RTCState) -> None:
        """原子性更新通话状态并触发对应事件。

        Args:
            new_state: 目标状态
        """
        old_state = self._session.state
        if old_state == new_state:
            return

        self._session.state = new_state
        _logger.info(
            "通话状态变更: %s -> %s",
            old_state.value,
            new_state.value,
        )
        await self._events.emit("state_change", old_state, new_state)

        if new_state == RTCState.CONNECTED:
            self._session.connected_time = time.time()
            await self._events.emit("connected")
        elif new_state == RTCState.ENDED:
            self._session.end_time = time.time()
            await self._events.emit("ended")
        elif new_state == RTCState.FAILED:
            self._session.end_time = time.time()
            await self._events.emit("failed", "通话失败")

    # ------------------------------------------------------------------
    # 通话控制
    # ------------------------------------------------------------------

    async def start(self) -> "RTCCallSession":
        """发起通话（主叫方调用）。

        Returns:
            返回 self 以支持链式调用

        Raises:
            RTCError: 当前状态不允许发起通话
        """
        if self._session.state != RTCState.IDLE:
            raise RTCError(
                f"无法在 {self._session.state.value} 状态下发起通话"
            )

        self._running = True
        self._session.start_time = time.time()

        if self._session.is_group_call:
            await self._start_group_call()
        else:
            await self._start_private_call()

        return self

    async def _start_private_call(self) -> None:
        """发起私聊通话，设置心跳和 WebSocket 消息处理器。

        Raises:
            RTCError: user_id 未设置或 API 调用失败
        """
        user_id = self._session.user_id
        if user_id is None:
            raise RTCError("私聊通话需要指定 user_id")

        mode_str = self._session.mode.value
        if mode_str == "audio":
            mode_str = "voice"

        await self._set_state(RTCState.CALLING)
        try:
            await self._sdk.awebrtc_setup(user_id, mode=mode_str)
            _logger.info(
                "私聊通话已发起: user_id=%s, mode=%s", user_id, mode_str
            )
            self._heartbeat_task = asyncio.create_task(
                self._private_heartbeat_loop(user_id)
            )
            self._register_rtc_ws_handler()
        except Exception as exc:
            await self._set_state(RTCState.FAILED)
            raise RTCError(f"发起通话失败: {exc}") from exc

    async def _start_group_call(self) -> None:
        """发起群聊通话，设置心跳和 WebSocket 消息处理器。

        Raises:
            RTCError: group_id 未设置或 API 调用失败
        """
        group_id = self._session.group_id
        if group_id is None:
            raise RTCError("群聊通话需要指定 group_id")

        await self._set_state(RTCState.CALLING)
        try:
            await self._sdk.awebrtc_group_setup(group_id)
            _logger.info("群聊通话已发起: group_id=%s", group_id)
            self._heartbeat_task = asyncio.create_task(
                self._group_heartbeat_loop(group_id)
            )
            self._register_rtc_ws_handler()
        except Exception as exc:
            await self._set_state(RTCState.FAILED)
            raise RTCError(f"发起群聊通话失败: {exc}") from exc

    async def accept(self, answer_sdp: str = "") -> "RTCCallSession":
        """接受通话（被叫方调用）。

        Args:
            answer_sdp: SDP Answer 字符串（可选）

        Returns:
            返回 self 以支持链式调用
        """
        self._running = True

        if self._session.is_group_call:
            group_id = self._session.group_id
            if group_id is not None:
                await self._sdk.awebrtc_group_accept(group_id)
        else:
            user_id = self._session.user_id
            if user_id is not None:
                await self._sdk.awebrtc_accept(user_id, answer=answer_sdp)

        await self._set_state(RTCState.CONNECTED)
        await self._start_heartbeat_after_accept()
        self._register_rtc_ws_handler()
        self._start_stream_processing()
        return self

    async def _start_heartbeat_after_accept(self) -> None:
        """接受通话后启动心跳循环。"""
        if self._session.is_group_call:
            group_id = self._session.group_id
            if group_id is not None:
                self._heartbeat_task = asyncio.create_task(
                    self._group_heartbeat_loop(group_id)
                )
        else:
            user_id = self._session.user_id
            if user_id is not None:
                self._heartbeat_task = asyncio.create_task(
                    self._private_heartbeat_loop(user_id)
                )

    async def reject(self) -> "RTCCallSession":
        """拒绝来电。

        Returns:
            返回 self 以支持链式调用
        """
        if self._session.is_group_call:
            group_id = self._session.group_id
            if group_id is not None:
                await self._sdk.awebrtc_group_reject(group_id)
        else:
            user_id = self._session.user_id
            if user_id is not None:
                await self._sdk.awebrtc_reject(user_id)

        await self._set_state(RTCState.ENDED)
        await self._cleanup()
        return self

    async def cancel(self) -> "RTCCallSession":
        """取消呼出（主叫方使用）。

        Returns:
            返回 self 以支持链式调用
        """
        if self._session.is_group_call:
            group_id = self._session.group_id
            if group_id is not None:
                await self._sdk.awebrtc_group_cancel(group_id)
        else:
            user_id = self._session.user_id
            if user_id is not None:
                await self._sdk.awebrtc_cancel(user_id)

        await self._set_state(RTCState.ENDED)
        await self._cleanup()
        return self

    async def hangup(self) -> "RTCCallSession":
        """挂断通话。

        Returns:
            返回 self 以支持链式调用
        """
        if self._session.is_group_call:
            group_id = self._session.group_id
            if group_id is not None:
                await self._sdk.awebrtc_group_quit(group_id)
        else:
            user_id = self._session.user_id
            if user_id is not None:
                await self._sdk.awebrtc_handup(user_id)

        await self._set_state(RTCState.ENDED)
        await self._cleanup()
        return self

    async def send_offer(self, sdp: str) -> "RTCCallSession":
        """发送 SDP Offer。

        Args:
            sdp: SDP 内容字符串

        Returns:
            返回 self 以支持链式调用
        """
        self._session.local_sdp = sdp

        if self._session.is_group_call:
            group_id = self._session.group_id
            user_id = self._session.user_id
            if group_id is not None and user_id is not None:
                await self._sdk.awebrtc_group_offer(group_id, user_id, sdp)
        else:
            user_id = self._session.user_id
            if user_id is not None:
                await self._sdk.awebrtc_offer(user_id, sdp)

        return self

    async def send_answer(self, sdp: str) -> "RTCCallSession":
        """发送 SDP Answer。

        Args:
            sdp: SDP 内容字符串

        Returns:
            返回 self 以支持链式调用
        """
        self._session.local_sdp = sdp

        if self._session.is_group_call:
            group_id = self._session.group_id
            user_id = self._session.user_id
            if group_id is not None and user_id is not None:
                await self._sdk.awebrtc_group_answer(group_id, user_id, sdp)
        else:
            user_id = self._session.user_id
            if user_id is not None:
                await self._sdk.awebrtc_answer(user_id, sdp)

        return self

    async def send_candidate(self, candidate: str) -> "RTCCallSession":
        """发送 ICE Candidate。

        Args:
            candidate: ICE Candidate 字符串

        Returns:
            返回 self 以支持链式调用
        """
        self._session.candidates.append(candidate)

        if self._session.is_group_call:
            group_id = self._session.group_id
            user_id = self._session.user_id
            if group_id is not None and user_id is not None:
                await self._sdk.awebrtc_group_send_candidate(
                    group_id, user_id, candidate
                )
        else:
            user_id = self._session.user_id
            if user_id is not None:
                await self._sdk.awebrtc_send_candidate(user_id, candidate)

        return self

    async def update_device(
        self,
        camera: Optional[bool] = None,
        microphone: Optional[bool] = None,
        screen_share: Optional[bool] = None,
    ) -> "RTCCallSession":
        """更新设备状态（仅群聊通话有效）。

        Args:
            camera: 摄像头开关状态
            microphone: 麦克风开关状态
            screen_share: 屏幕共享开关状态

        Returns:
            返回 self 以支持链式调用
        """
        if not self._session.is_group_call:
            _logger.warning("设备状态更新仅适用于群聊通话")
            return self

        if camera is not None:
            self._session.is_camera_on = camera
        if microphone is not None:
            self._session.is_microphone_on = microphone
        if screen_share is not None:
            self._session.is_screen_sharing = screen_share

        group_id = self._session.group_id
        if group_id is not None:
            await self._sdk.awebrtc_group_device(
                group_id,
                is_camera=self._session.is_camera_on,
                is_microphone=self._session.is_microphone_on,
                is_share_screen=self._session.is_screen_sharing,
            )

        return self

    async def invite_members(
        self, user_infos: List[Dict[str, Any]]
    ) -> "RTCCallSession":
        """邀请成员加入群组通话。

        Args:
            user_infos: 用户信息列表，每项包含 id/nickName/headImage

        Returns:
            返回 self 以支持链式调用

        Raises:
            RTCError: 非群聊通话时抛出
        """
        if not self._session.is_group_call:
            raise RTCError("邀请成员仅适用于群聊通话")

        group_id = self._session.group_id
        if group_id is not None:
            await self._sdk.awebrtc_group_invite(group_id, user_infos)

        return self

    async def report_failed(self, reason: str = "unknown") -> "RTCCallSession":
        """向服务端报告通话失败并清理资源。

        Args:
            reason: 失败原因描述

        Returns:
            返回 self 以支持链式调用
        """
        if self._session.is_group_call:
            group_id = self._session.group_id
            if group_id is not None:
                await self._sdk.awebrtc_group_failed(group_id, reason)
        else:
            user_id = self._session.user_id
            if user_id is not None:
                await self._sdk.awebrtc_failed(user_id, reason)

        await self._set_state(RTCState.FAILED)
        await self._cleanup()
        return self

    # ------------------------------------------------------------------
    # 流处理
    # ------------------------------------------------------------------

    def _start_stream_processing(self) -> None:
        """启动音视频流处理任务（有流或处理器时才启动）。"""
        if (
            self._input_stream
            or self._audio_processor
            or self._video_input
        ):
            self._stream_task = asyncio.create_task(self._stream_loop())

    async def _stream_loop(self) -> None:
        """音视频流处理主循环。"""
        chunk_size = self._config.stream_chunk_size

        while self._running and self._session.state == RTCState.CONNECTED:
            try:
                if self._input_stream:
                    await self._process_audio_input(chunk_size)
                if self._video_input:
                    await self._process_video_input()
                await asyncio.sleep(0.02)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                _logger.error("流处理异常: %s", exc)
                await asyncio.sleep(0.1)

    async def _process_audio_input(self, chunk_size: int) -> None:
        """读取音频输入流并通过处理器处理后发送。

        Args:
            chunk_size: 每次读取的字节数
        """
        if self._input_stream is None:
            return

        audio_data = await self._read_audio(self._input_stream, chunk_size)
        if not audio_data:
            return

        if self._audio_processor:
            try:
                audio_data = await self._audio_processor(audio_data)
            except Exception as exc:
                _logger.error("音频处理器异常: %s", exc)

        await self._events.emit("audio_send", audio_data)

    async def _process_video_input(self) -> None:
        """读取视频输入流并通过处理器处理后发送。"""
        if self._video_input is None:
            return

        frame_data = await self._read_video_frame(self._video_input)
        if not frame_data:
            return

        if self._video_processor:
            try:
                frame_data = await self._video_processor(frame_data)
            except Exception as exc:
                _logger.error("视频处理器异常: %s", exc)

        await self._events.emit("video_send", frame_data)

    @staticmethod
    async def _read_audio(
        stream: Union[AudioStream, AsyncAudioStream],
        size: int,
    ) -> bytes:
        """从音频流读取数据（自动兼容同步/异步流）。

        Args:
            stream: 音频流对象
            size: 要读取的字节数

        Returns:
            读取到的音频字节数据
        """
        if asyncio.iscoroutinefunction(getattr(stream, "read", None)):
            return await stream.read(size)  # type: ignore[union-attr]
        return stream.read(size)  # type: ignore[union-attr]

    @staticmethod
    async def _write_audio(
        stream: Union[AudioStream, AsyncAudioStream],
        data: bytes,
    ) -> None:
        """向音频流写入数据（自动兼容同步/异步流）。

        Args:
            stream: 音频流对象
            data: 要写入的音频字节数据
        """
        if asyncio.iscoroutinefunction(getattr(stream, "write", None)):
            await stream.write(data)  # type: ignore[union-attr]
        else:
            stream.write(data)  # type: ignore[union-attr]

    @staticmethod
    async def _read_video_frame(
        stream: Union[VideoStream, AsyncVideoStream],
    ) -> Optional[bytes]:
        """从视频流读取一帧（自动兼容同步/异步流）。

        Args:
            stream: 视频流对象

        Returns:
            视频帧字节数据，无数据时返回 None
        """
        if asyncio.iscoroutinefunction(getattr(stream, "read_frame", None)):
            return await stream.read_frame()  # type: ignore[union-attr]
        return stream.read_frame()  # type: ignore[union-attr]

    @staticmethod
    async def _write_video_frame(
        stream: Union[VideoStream, AsyncVideoStream],
        data: bytes,
    ) -> None:
        """向视频流写入一帧（自动兼容同步/异步流）。

        Args:
            stream: 视频流对象
            data: 视频帧字节数据
        """
        if asyncio.iscoroutinefunction(getattr(stream, "write_frame", None)):
            await stream.write_frame(data)  # type: ignore[union-attr]
        else:
            stream.write_frame(data)  # type: ignore[union-attr]

    async def handle_received_audio(self, data: bytes) -> None:
        """处理接收到的音频数据（由 SDK 内部调用，也可手动注入）。

        若设置了音频处理器，则先经过处理器处理再写入输出流。

        Args:
            data: 接收到的音频字节数据
        """
        processed = data
        if self._audio_processor:
            try:
                processed = await self._audio_processor(data)
            except Exception as exc:
                _logger.error("音频处理器异常: %s", exc)
                processed = data

        if self._output_stream:
            await self._write_audio(self._output_stream, processed)

        await self._events.emit("audio_receive", processed)

    async def handle_received_video(self, data: bytes) -> None:
        """处理接收到的视频帧（由 SDK 内部调用，也可手动注入）。

        Args:
            data: 接收到的视频帧字节数据
        """
        processed = data
        if self._video_processor:
            try:
                processed = await self._video_processor(data)
            except Exception as exc:
                _logger.error("视频处理器异常: %s", exc)
                processed = data

        if self._video_output:
            await self._write_video_frame(self._video_output, processed)

        await self._events.emit("video_receive", processed)

    async def handle_remote_sdp(self, sdp: str) -> None:
        """处理接收到的远端 SDP。

        Args:
            sdp: SDP 字符串
        """
        self._session.remote_sdp = sdp
        await self._events.emit("remote_sdp", sdp)

    async def handle_remote_candidate(self, candidate: str) -> None:
        """处理接收到的远端 ICE Candidate。

        Args:
            candidate: ICE Candidate 字符串
        """
        self._session.remote_candidates.append(candidate)
        await self._events.emit("remote_candidate", candidate)

    # ------------------------------------------------------------------
    # WebSocket 消息处理
    # ------------------------------------------------------------------

    def _register_rtc_ws_handler(self) -> None:
        """注册 RTC WebSocket 消息处理器到 SDK 的 WebSocket 传输层。"""
        self._sdk.ws.on("rtc_message", self._handle_rtc_message)

    async def _handle_rtc_message(
        self,
        msg_data: Dict[str, Any],
        is_group: bool = False,
    ) -> None:
        """路由并处理 RTC WebSocket 信令消息。

        Args:
            msg_data: 消息数据字典
            is_group: 是否来自群聊频道
        """
        msg_type_val = msg_data.get("type", 0)
        try:
            rtc_type = MessageType(msg_type_val)
        except ValueError:
            return

        await self._dispatch_rtc_message(rtc_type, msg_data)

    async def _dispatch_rtc_message(
        self,
        rtc_type: MessageType,
        msg_data: Dict[str, Any],
    ) -> None:
        """根据 RTC 消息类型分发处理逻辑。

        Args:
            rtc_type: 消息类型枚举值
            msg_data: 消息数据字典
        """
        # 私聊 RTC 信令
        if rtc_type == MessageType.RTC_PRIVATE_SETUP:
            if not self._session.is_caller:
                await self._set_state(RTCState.RINGING)
        elif rtc_type == MessageType.RTC_PRIVATE_ACCEPT:
            await self._set_state(RTCState.CONNECTED)
            self._start_stream_processing()
        elif rtc_type in (
            MessageType.RTC_PRIVATE_REJECT,
            MessageType.RTC_PRIVATE_CANCEL,
            MessageType.RTC_PRIVATE_HANDUP,
        ):
            await self._set_state(RTCState.ENDED)
            await self._cleanup()
        elif rtc_type == MessageType.RTC_PRIVATE_FAILED:
            reason = msg_data.get("content", "unknown")
            await self._events.emit("failed", reason)
            await self._set_state(RTCState.FAILED)
            await self._cleanup()
        elif rtc_type == MessageType.RTC_PRIVATE_OFFER:
            await self.handle_remote_sdp(
                self._extract_sdp(msg_data, ("sdp",))
            )
        elif rtc_type == MessageType.RTC_PRIVATE_ANSWER:
            await self.handle_remote_sdp(
                self._extract_sdp(msg_data, ("sdp",))
            )
        elif rtc_type == MessageType.RTC_PRIVATE_CANDIDATE:
            await self.handle_remote_candidate(
                self._extract_candidate(msg_data)
            )
        # 群聊 RTC 信令
        elif rtc_type == MessageType.RTC_GROUP_ACCEPT:
            await self._set_state(RTCState.CONNECTED)
            self._start_stream_processing()
        elif rtc_type == MessageType.RTC_GROUP_REJECT:
            _logger.info("群聊通话有成员拒绝")
        elif rtc_type == MessageType.RTC_GROUP_FAILED:
            reason = msg_data.get("content", "unknown")
            await self._events.emit("failed", reason)
        elif rtc_type in (
            MessageType.RTC_GROUP_CANCEL,
        ):
            await self._set_state(RTCState.ENDED)
            await self._cleanup()
        elif rtc_type == MessageType.RTC_GROUP_QUIT:
            _logger.info("群聊通话有成员退出")
        elif rtc_type == MessageType.RTC_GROUP_INVITE:
            await self._events.emit("group_invite", msg_data)
        elif rtc_type == MessageType.RTC_GROUP_JOIN:
            await self._events.emit("group_join", msg_data)
        elif rtc_type == MessageType.RTC_GROUP_OFFER:
            await self.handle_remote_sdp(
                self._extract_sdp(msg_data, ("offer", "sdp"))
            )
        elif rtc_type == MessageType.RTC_GROUP_ANSWER:
            await self.handle_remote_sdp(
                self._extract_sdp(msg_data, ("answer", "sdp"))
            )
        elif rtc_type == MessageType.RTC_GROUP_CANDIDATE:
            await self.handle_remote_candidate(
                self._extract_candidate(msg_data)
            )
        elif rtc_type == MessageType.RTC_GROUP_DEVICE:
            await self._events.emit("device_change", msg_data)

    @staticmethod
    def _extract_sdp(
        msg_data: Dict[str, Any],
        keys: tuple[str, ...],
    ) -> str:
        """从消息数据中提取 SDP 字符串。

        依次尝试 keys 中的键名，均不存在时返回原始 content。

        Args:
            msg_data: 消息数据字典
            keys: 候选键名元组

        Returns:
            SDP 字符串
        """
        content = msg_data.get("content", "")
        try:
            parsed = json.loads(content) if content else {}
            for key in keys:
                if key in parsed:
                    return parsed[key]
        except (json.JSONDecodeError, TypeError):
            pass
        return content

    @staticmethod
    def _extract_candidate(msg_data: Dict[str, Any]) -> str:
        """从消息数据中提取 ICE Candidate 字符串。

        Args:
            msg_data: 消息数据字典

        Returns:
            ICE Candidate 字符串
        """
        content = msg_data.get("content", "")
        try:
            parsed = json.loads(content) if content else {}
            return parsed.get("candidate", content)
        except (json.JSONDecodeError, TypeError):
            return content

    # ------------------------------------------------------------------
    # 心跳
    # ------------------------------------------------------------------

    async def _private_heartbeat_loop(self, user_id: int) -> None:
        """私聊通话心跳循环，定时发送心跳维持连接。

        Args:
            user_id: 对方用户 ID
        """
        interval = self._config.rtc_heartbeat_interval
        while self._running and self._session.is_active:
            try:
                await asyncio.sleep(interval)
                if self._running and self._session.is_active:
                    await self._sdk.awebrtc_heartbeat(user_id)
                    _logger.debug(
                        "私聊通话心跳已发送: user_id=%s", user_id
                    )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                _logger.warning("私聊通话心跳失败: %s", exc)

    async def _group_heartbeat_loop(self, group_id: int) -> None:
        """群聊通话心跳循环，定时发送心跳维持连接。

        Args:
            group_id: 群组 ID
        """
        interval = self._config.rtc_heartbeat_interval
        while self._running and self._session.is_active:
            try:
                await asyncio.sleep(interval)
                if self._running and self._session.is_active:
                    await self._sdk.awebrtc_group_heartbeat(group_id)
                    _logger.debug(
                        "群聊通话心跳已发送: group_id=%s", group_id
                    )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                _logger.warning("群聊通话心跳失败: %s", exc)

    # ------------------------------------------------------------------
    # 清理
    # ------------------------------------------------------------------

    async def _cleanup(self) -> None:
        """清理通话资源：取消任务、关闭流、注销 WebSocket 处理器。"""
        self._running = False

        await self._cancel_task(self._heartbeat_task)
        self._heartbeat_task = None

        await self._cancel_task(self._stream_task)
        self._stream_task = None

        await self._close_streams()
        self._deregister_rtc_ws_handler()

        _logger.info(
            "通话已清理: session_id=%s, duration=%.1fs",
            self._session.session_id,
            self._session.duration,
        )

    @staticmethod
    async def _cancel_task(
        task: Optional[asyncio.Task[Any]],
    ) -> None:
        """安全取消并等待 asyncio 任务完成。

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

    async def _close_streams(self) -> None:
        """关闭所有已注册的音视频流。"""
        streams = [
            self._input_stream,
            self._output_stream,
            self._video_input,
            self._video_output,
        ]
        for stream in streams:
            if stream is None:
                continue
            try:
                if asyncio.iscoroutinefunction(getattr(stream, "close", None)):
                    await stream.close()  # type: ignore[union-attr]
                elif hasattr(stream, "close"):
                    stream.close()  # type: ignore[union-attr]
            except Exception as exc:
                _logger.warning("关闭流异常: %s", exc)

    def _deregister_rtc_ws_handler(self) -> None:
        """从 WebSocket 传输层注销 RTC 消息处理器。"""
        try:
            self._sdk.ws.off("rtc_message", self._handle_rtc_message)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 上下文管理器
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "RTCCallSession":
        """进入异步上下文管理器。

        Returns:
            返回 self
        """
        return self

    async def __aexit__(
        self,
        exc_type: Any,
        exc_val: Any,
        exc_tb: Any,
    ) -> None:
        """退出异步上下文管理器，自动挂断或清理通话。

        Args:
            exc_type: 异常类型
            exc_val: 异常值
            exc_tb: 异常 traceback
        """
        if self._session.is_active:
            await self.hangup()
        else:
            await self._cleanup()


__all__ = ["RTCCallSession"]
