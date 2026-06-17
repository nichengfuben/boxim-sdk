from __future__ import annotations

import json
import random
import threading
import time

from boxim.util.models import UploadResult


class SnowflakeIdGenerator:
    """Snowflake ID 生成器（对齐 BoxIM 前端算法）。

    参数:
        epoch: 1288834974657 (2010-11-04)
        machine_id: 5 bits (0-31)
        datacenter_id: 5 bits (0-31)
        sequence: 12 bits (0-4095)
    """

    EPOCH = 1288834974657
    MACHINE_ID = random.randint(0, 31)
    DATACENTER_ID = random.randint(0, 31)
    SEQ_MASK = (1 << 12) - 1
    TIMESTAMP_SHIFT = 22
    MACHINE_SHIFT = 17
    DATACENTER_SHIFT = 12

    def __init__(self) -> None:
        self._last_ts = -1
        self._seq = 0
        self._lock = threading.Lock()

    def generate(self) -> str:
        with self._lock:
            ts = int(time.time() * 1000)
            if ts < self._last_ts:
                diff = self._last_ts - ts
                if diff > 5:
                    raise RuntimeError(f"Clock moved backwards {diff}ms")
                while ts < self._last_ts:
                    time.sleep(0.001)
                    ts = int(time.time() * 1000)
            if ts == self._last_ts:
                self._seq = (self._seq + 1) & self.SEQ_MASK
                if self._seq == 0:
                    while ts <= self._last_ts:
                        time.sleep(0.001)
                        ts = int(time.time() * 1000)
            else:
                self._seq = random.randint(1, 2)
            self._last_ts = ts
            sid = (
                ((ts - self.EPOCH) << self.TIMESTAMP_SHIFT)
                | (self.MACHINE_ID << self.MACHINE_SHIFT)
                | (self.DATACENTER_ID << self.DATACENTER_SHIFT)
                | self._seq
            )
            return str(sid)


_snowflake = SnowflakeIdGenerator()


class MessageBuilder:
    """消息内容构建器。

    辅助构建各种消息类型的 content 字段 JSON 字符串。
    所有方法均为静态方法，无需实例化。

    示例：
        >>> MessageBuilder.text("你好")
        '你好'
        >>> MessageBuilder.sticker(42)
        '{"stickerId": 42}'
    """

    @staticmethod
    def text(content: str) -> str:
        """构建文本消息内容。

        Args:
            content: 文本内容字符串

        Returns:
            原始文本字符串
        """
        return content

    @staticmethod
    def image(
        origin_url: str,
        thumb_url: str,
        width: int = 0,
        height: int = 0,
    ) -> str:
        """构建图片消息内容。

        Args:
            origin_url: 原图 URL
            thumb_url: 缩略图 URL
            width: 图片宽度（像素）
            height: 图片高度（像素）

        Returns:
            图片消息 content JSON 字符串
        """
        return json.dumps(
            {
                "originUrl": origin_url,
                "thumbUrl": thumb_url,
                "width": width,
                "height": height,
            }
        )

    @staticmethod
    def image_from_upload(result: UploadResult) -> str:
        """从上传结果构建图片消息内容。

        Args:
            result: 图片上传结果对象

        Returns:
            图片消息 content JSON 字符串
        """
        return json.dumps(
            {
                "originUrl": result.origin_url,
                "thumbUrl": result.thumb_url,
                "width": result.width,
                "height": result.height,
            }
        )

    @staticmethod
    def file(name: str, size: int, url: str) -> str:
        """构建文件消息内容。

        Args:
            name: 文件名
            size: 文件大小（字节）
            url: 文件访问 URL

        Returns:
            文件消息 content JSON 字符串
        """
        return json.dumps({"name": name, "size": size, "url": url})

    @staticmethod
    def file_from_upload(result: UploadResult) -> str:
        """从上传结果构建文件消息内容。

        Args:
            result: 文件上传结果对象

        Returns:
            文件消息 content JSON 字符串
        """
        return json.dumps(
            {
                "name": result.file_name,
                "size": result.file_size,
                "url": result.url,
            }
        )

    @staticmethod
    def voice(url: str, duration: int = 3) -> str:
        """构建语音消息内容。

        Args:
            url: 语音文件访问 URL
            duration: 语音时长（秒）

        Returns:
            语音消息 content JSON 字符串
        """
        return json.dumps({"duration": duration, "url": url})

    @staticmethod
    def video(
        video_url: str,
        cover_url: str = "",
        width: int = 0,
        height: int = 0,
    ) -> str:
        """构建视频消息内容。

        Args:
            video_url: 视频文件访问 URL
            cover_url: 视频封面图 URL
            width: 视频宽度（像素）
            height: 视频高度（像素）

        Returns:
            视频消息 content JSON 字符串
        """
        return json.dumps(
            {
                "videoUrl": video_url,
                "coverUrl": cover_url,
                "width": width,
                "height": height,
            }
        )

    @staticmethod
    def video_from_upload(result: UploadResult) -> str:
        """从上传结果构建视频消息内容。

        Args:
            result: 视频上传结果对象

        Returns:
            视频消息 content JSON 字符串
        """
        return json.dumps(
            {
                "videoUrl": result.video_url,
                "coverUrl": result.cover_url,
                "width": result.width,
                "height": result.height,
            }
        )

    @staticmethod
    def sticker(sticker_id: int) -> str:
        """构建贴纸消息内容。

        Args:
            sticker_id: 贴纸 ID

        Returns:
            贴纸消息 content JSON 字符串
        """
        return json.dumps({"stickerId": sticker_id})

    @staticmethod
    def user_card(
        user_id: int,
        nick_name: str,
        head_image: str,
    ) -> str:
        """构建个人名片消息内容。

        Args:
            user_id: 用户 ID
            nick_name: 用户昵称
            head_image: 用户头像 URL

        Returns:
            个人名片消息 content JSON 字符串
        """
        return json.dumps(
            {
                "userId": user_id,
                "nickName": nick_name,
                "headImage": head_image,
            }
        )

    @staticmethod
    def group_card(
        group_id: int,
        group_name: str,
        head_image: str,
    ) -> str:
        """构建群聊名片消息内容。

        Args:
            group_id: 群组 ID
            group_name: 群组名称
            head_image: 群组头像 URL

        Returns:
            群聊名片消息 content JSON 字符串
        """
        return json.dumps(
            {
                "groupId": group_id,
                "groupName": group_name,
                "headImage": head_image,
            }
        )

    @staticmethod
    def generate_local_id() -> str:
        """生成消息本地 ID（Snowflake 算法，对齐官方 API 文档的 localId 字段）。

        Returns:
            Snowflake ID 字符串
        """
        return _snowflake.generate()

    @staticmethod
    def generate_tmp_id() -> str:
        """生成消息临时 ID（generate_local_id 的向后兼容别名）。

        Returns:
            Snowflake ID 字符串
        """
        return _snowflake.generate()


__all__ = ["MessageBuilder"]
