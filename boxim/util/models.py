from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from boxim.util.enums import FriendRequestStatus, MessageType, RTCMode, RTCState


@dataclass
class User:
    """用户信息数据模型。"""

    id: Optional[int] = None
    user_name: Optional[str] = None
    nick_name: Optional[str] = None
    sex: Optional[int] = None
    signature: Optional[str] = None
    head_image: Optional[str] = None
    head_image_thumb: Optional[str] = None
    online: bool = False
    type: Optional[int] = None
    is_banned: Optional[bool] = None
    reason: Optional[str] = None
    company_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: Optional[int] = None
    is_audio_tip: Optional[bool] = None
    deleted: Optional[bool] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        """从 API 响应字典构造用户对象。

        Args:
            data: API 响应字典

        Returns:
            User: 用户实例
        """
        if not data:
            return cls()
        return cls(
            id=data.get("id"),
            user_name=data.get("userName"),
            nick_name=data.get("nickName"),
            sex=data.get("sex"),
            signature=data.get("signature"),
            head_image=data.get("headImage"),
            head_image_thumb=data.get("headImageThumb"),
            online=data.get("online", False),
            type=data.get("type"),
            is_banned=data.get("isBanned"),
            reason=data.get("reason"),
            company_name=data.get("companyName"),
            phone=data.get("phone"),
            email=data.get("email"),
            status=data.get("status"),
            is_audio_tip=data.get("isAudioTip"),
            deleted=data.get("deleted"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为 API 请求格式字典。

        Returns:
            Dict[str, Any]: 仅包含非 None 字段的字典
        """
        result: Dict[str, Any] = {}
        if self.id is not None:
            result["id"] = self.id
        if self.user_name is not None:
            result["userName"] = self.user_name
        if self.nick_name is not None:
            result["nickName"] = self.nick_name
        if self.sex is not None:
            result["sex"] = self.sex
        if self.signature is not None:
            result["signature"] = self.signature
        if self.head_image is not None:
            result["headImage"] = self.head_image
        if self.head_image_thumb is not None:
            result["headImageThumb"] = self.head_image_thumb
        if self.company_name is not None:
            result["companyName"] = self.company_name
        if self.phone is not None:
            result["phone"] = self.phone
        if self.email is not None:
            result["email"] = self.email
        return result


@dataclass
class Friend:
    """好友信息数据模型。"""

    id: int = 0
    nick_name: str = ""
    show_nick_name: str = ""
    remark_nick_name: str = ""
    head_image: str = ""
    company_name: Optional[str] = None
    is_dnd: Optional[bool] = None
    is_top: bool = False
    deleted: bool = False
    online: bool = False
    online_web: bool = False
    online_app: bool = False
    version: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Friend":
        """从 API 响应字典构造好友对象。

        Args:
            data: API 响应字典

        Returns:
            Friend: 好友实例
        """
        if not data:
            return cls(id=0)
        return cls(
            id=data.get("id", 0),
            nick_name=data.get("nickName", ""),
            show_nick_name=data.get("showNickName", ""),
            remark_nick_name=data.get("remarkNickName", ""),
            head_image=data.get("headImage", ""),
            company_name=data.get("companyName"),
            is_dnd=data.get("isDnd"),
            is_top=data.get("isTop", False),
            deleted=data.get("deleted", False),
            online=data.get("online", False),
            online_web=data.get("onlineWeb", False),
            online_app=data.get("onlineApp", False),
            version=data.get("version"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。

        Returns:
            Dict[str, Any]: 好友数据字典
        """
        return {
            "id": self.id,
            "nickName": self.nick_name,
            "showNickName": self.show_nick_name,
            "remarkNickName": self.remark_nick_name,
            "headImage": self.head_image,
            "companyName": self.company_name,
            "isDnd": self.is_dnd,
            "isTop": self.is_top,
            "deleted": self.deleted,
            "online": self.online,
            "onlineWeb": self.online_web,
            "onlineApp": self.online_app,
        }


@dataclass
class FriendRequest:
    """好友请求数据模型。"""

    id: Optional[int] = None
    req_user_id: Optional[int] = None
    req_user_name: Optional[str] = None
    req_user_nick_name: Optional[str] = None
    req_user_head_image: Optional[str] = None
    resp_user_id: Optional[int] = None
    message: Optional[str] = None
    status: FriendRequestStatus = FriendRequestStatus.PENDING
    create_time: Optional[int] = None
    update_time: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FriendRequest":
        """从 API 响应字典构造好友请求对象。

        Args:
            data: API 响应字典

        Returns:
            FriendRequest: 好友请求实例
        """
        if not data:
            return cls()
        return cls(
            id=data.get("id"),
            req_user_id=data.get("reqUserId"),
            req_user_name=data.get("reqUserName"),
            req_user_nick_name=data.get("reqUserNickName"),
            req_user_head_image=data.get("reqUserHeadImage"),
            resp_user_id=data.get("respUserId"),
            message=data.get("message"),
            status=FriendRequestStatus(data.get("status", 0)),
            create_time=data.get("createTime"),
            update_time=data.get("updateTime"),
        )


@dataclass
class Group:
    """群组信息数据模型。"""

    id: Optional[int] = None
    name: Optional[str] = None
    owner_id: Optional[int] = None
    head_image: Optional[str] = None
    head_image_thumb: Optional[str] = None
    notice: Optional[str] = None
    remark_nick_name: Optional[str] = None
    show_nick_name: Optional[str] = None
    show_group_name: Optional[str] = None
    remark_group_name: Optional[str] = None
    member_count: int = 0
    is_dnd: bool = False
    dissolve: Optional[bool] = None
    quit: Optional[bool] = None
    is_banned: Optional[bool] = None
    reason: Optional[str] = None
    is_muted: Optional[bool] = None
    is_all_muted: Optional[bool] = None
    is_allow_invite: Optional[bool] = None
    is_allow_share_card: Optional[bool] = None
    is_top: bool = False
    version: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Group":
        """从 API 响应字典构造群组对象。

        Args:
            data: API 响应字典

        Returns:
            Group: 群组实例
        """
        if not data:
            return cls()
        return cls(
            id=data.get("id"),
            name=data.get("name"),
            owner_id=data.get("ownerId"),
            head_image=data.get("headImage"),
            head_image_thumb=data.get("headImageThumb"),
            notice=data.get("notice"),
            remark_nick_name=data.get("remarkNickName"),
            show_nick_name=data.get("showNickName"),
            show_group_name=data.get("showGroupName"),
            remark_group_name=data.get("remarkGroupName"),
            member_count=data.get("memberCount", 0),
            is_dnd=data.get("isDnd", False),
            dissolve=data.get("dissolve"),
            quit=data.get("quit"),
            is_banned=data.get("isBanned"),
            reason=data.get("reason"),
            is_muted=data.get("isMuted"),
            is_all_muted=data.get("isAllMuted"),
            is_allow_invite=data.get("isAllowInvite"),
            is_allow_share_card=data.get("isAllowShareCard"),
            is_top=data.get("isTop", False),
            version=data.get("version"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为 API 请求格式字典。

        Returns:
            Dict[str, Any]: 仅包含非 None 字段的字典
        """
        result: Dict[str, Any] = {}
        if self.id is not None:
            result["id"] = self.id
        if self.name is not None:
            result["name"] = self.name
        if self.notice is not None:
            result["notice"] = self.notice
        if self.head_image is not None:
            result["headImage"] = self.head_image
        if self.head_image_thumb is not None:
            result["headImageThumb"] = self.head_image_thumb
        if self.remark_group_name is not None:
            result["remarkGroupName"] = self.remark_group_name
        return result


@dataclass
class Message:
    """消息数据模型。"""

    id: Optional[int] = None
    type: MessageType = MessageType.TEXT
    content: str = ""
    sender_id: Optional[int] = None
    receiver_id: Optional[int] = None
    group_id: Optional[int] = None
    send_time: Optional[int] = None
    local_id: Optional[str] = None
    seq_no: Optional[int] = None
    send_nick_name: Optional[str] = None
    send_head_image: Optional[str] = None
    at_user_ids: Optional[List[int]] = None
    receipt: bool = False
    quote_message_id: Optional[int] = None

    @property
    def tmp_id(self) -> Optional[str]:
        """向后兼容别名，等同于 local_id。"""
        return self.local_id

    @property
    def is_private(self) -> bool:
        """是否私聊消息。"""
        return self.receiver_id is not None

    @property
    def is_group(self) -> bool:
        """是否群聊消息。"""
        return self.group_id is not None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """从 API 响应字典构造消息对象。

        Args:
            data: API 响应字典

        Returns:
            Message: 消息实例
        """
        if not data:
            return cls()
        msg_type_val = data.get("type", 0)
        try:
            msg_type = MessageType(msg_type_val)
        except ValueError:
            msg_type = MessageType.TEXT
        return cls(
            id=data.get("id"),
            type=msg_type,
            content=data.get("content", ""),
            sender_id=data.get("sendId"),
            receiver_id=data.get("recvId"),
            group_id=data.get("groupId"),
            send_time=data.get("sendTime"),
            local_id=data.get("localId") or data.get("tmpId"),
            seq_no=data.get("seqNo"),
            send_nick_name=data.get("sendNickName"),
            send_head_image=data.get("sendHeadImage"),
            at_user_ids=data.get("atUserIds"),
            receipt=data.get("receipt", False),
            quote_message_id=data.get("quoteMessageId"),
        )


@dataclass
class SystemMessage:
    """系统消息数据模型。"""

    seq_no: Optional[int] = None
    type: Optional[str] = None
    content: Optional[str] = None
    create_time: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SystemMessage":
        """从 API 响应字典构造系统消息对象。

        Args:
            data: API 响应字典

        Returns:
            SystemMessage: 系统消息实例
        """
        if not data:
            return cls()
        return cls(
            seq_no=data.get("seqNo"),
            type=data.get("type"),
            content=data.get("content"),
            create_time=data.get("createTime"),
        )


@dataclass
class CaptchaCode:
    """验证码数据模型。"""

    id: str = ""
    image_url: str = ""
    expire_time: Optional[int] = None
    image: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CaptchaCode":
        """从 API 响应字典构造验证码对象。

        Args:
            data: API 响应字典

        Returns:
            CaptchaCode: 验证码实例
        """
        if not data:
            return cls()
        return cls(
            id=data.get("id", ""),
            image_url=data.get("imageUrl", ""),
            expire_time=data.get("expireTime"),
            image=data.get("image"),
        )


@dataclass
class StickerAlbum:
    """表情包专辑数据模型。"""

    id: int = 0
    name: str = ""
    cover_url: str = ""
    sticker_count: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StickerAlbum":
        """从 API 响应字典构造表情包专辑对象。

        Args:
            data: API 响应字典

        Returns:
            StickerAlbum: 表情包专辑实例
        """
        if not data:
            return cls()
        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            cover_url=data.get("coverUrl", ""),
            sticker_count=data.get("stickerCount", 0),
        )


@dataclass
class Sticker:
    """贴纸数据模型。"""

    id: int = 0
    name: str = ""
    image_url: str = ""
    thumb_url: str = ""
    width: int = 0
    height: int = 0
    album_id: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Sticker":
        """从 API 响应字典构造贴纸对象。

        Args:
            data: API 响应字典

        Returns:
            Sticker: 贴纸实例
        """
        if not data:
            return cls()
        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            image_url=data.get("imageUrl", ""),
            thumb_url=data.get("thumbUrl", ""),
            width=data.get("width", 0),
            height=data.get("height", 0),
            album_id=data.get("albumId"),
        )


@dataclass
class QRLoginInfo:
    """二维码登录信息数据模型。"""

    qr_code: str = ""
    qr_image: str = ""
    expires_in: int = 300

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QRLoginInfo":
        """从 API 响应字典构造二维码登录信息对象。

        Args:
            data: API 响应字典

        Returns:
            QRLoginInfo: 二维码登录信息实例
        """
        if not data:
            return cls()
        return cls(
            qr_code=data.get("qrCode", ""),
            qr_image=data.get("qrImage", ""),
            expires_in=data.get("expiresIn", 300),
        )


@dataclass
class SystemConfig:
    """系统配置数据模型。"""

    registration: Dict[str, Any] = field(default_factory=dict)
    webrtc: Dict[str, Any] = field(default_factory=dict)
    max_channel: int = 9

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SystemConfig":
        """从 API 响应字典构造系统配置对象。

        Args:
            data: API 响应字典

        Returns:
            SystemConfig: 系统配置实例
        """
        if not data:
            return cls()
        webrtc_data = data.get("webrtc", {})
        return cls(
            registration=data.get("registration", {}),
            webrtc=webrtc_data,
            max_channel=webrtc_data.get("maxChannel", 9) if webrtc_data else 9,
        )


@dataclass
class TokenInfo:
    """令牌信息数据模型。"""

    access_token: str = ""
    refresh_token: str = ""
    access_token_expires_in: int = 0
    refresh_token_expires_in: int = 0
    access_token_expires_at: int = 0
    refresh_token_expires_at: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenInfo":
        """从登录响应字典构造令牌信息对象。

        Args:
            data: 登录 API 响应字典

        Returns:
            TokenInfo: 令牌信息实例
        """
        if not data:
            return cls()
        now = int(time.time())
        access_expires = data.get("accessTokenExpiresIn", 0)
        refresh_expires = data.get("refreshTokenExpiresIn", 0)
        return cls(
            access_token=data.get("accessToken", ""),
            refresh_token=data.get("refreshToken", ""),
            access_token_expires_in=access_expires,
            refresh_token_expires_in=refresh_expires,
            access_token_expires_at=now + access_expires,
            refresh_token_expires_at=now + refresh_expires,
        )

    @property
    def is_access_expired(self) -> bool:
        """访问令牌是否已过期（提前 60 秒判定）。"""
        return int(time.time()) >= self.access_token_expires_at - 60

    @property
    def is_refresh_expired(self) -> bool:
        """刷新令牌是否已过期（提前 60 秒判定）。"""
        return int(time.time()) >= self.refresh_token_expires_at - 60


@dataclass
class RTCSessionInfo:
    """RTC 通话会话信息数据模型。"""

    session_id: Optional[str] = None
    user_id: Optional[int] = None
    group_id: Optional[int] = None
    mode: RTCMode = RTCMode.VIDEO
    state: RTCState = RTCState.IDLE
    is_caller: bool = False
    start_time: Optional[float] = None
    connected_time: Optional[float] = None
    end_time: Optional[float] = None
    local_sdp: Optional[str] = None
    remote_sdp: Optional[str] = None
    candidates: List[str] = field(default_factory=list)
    remote_candidates: List[str] = field(default_factory=list)
    is_camera_on: bool = True
    is_microphone_on: bool = True
    is_screen_sharing: bool = False

    @property
    def duration(self) -> float:
        """通话时长（秒），未接通时返回 0。"""
        if self.connected_time is None:
            return 0.0
        end = self.end_time or time.time()
        return end - self.connected_time

    @property
    def is_active(self) -> bool:
        """通话是否处于活跃状态。"""
        return self.state in (
            RTCState.CALLING,
            RTCState.RINGING,
            RTCState.CONNECTED,
        )

    @property
    def is_group_call(self) -> bool:
        """是否为群组通话。"""
        return self.group_id is not None


@dataclass
class UploadResult:
    """文件上传结果数据模型。"""

    url: str = ""
    origin_url: str = ""
    thumb_url: str = ""
    width: int = 0
    height: int = 0
    video_url: str = ""
    cover_url: str = ""
    file_name: str = ""
    file_size: int = 0

    @classmethod
    def from_image_dict(cls, data: Dict[str, Any]) -> "UploadResult":
        """从图片上传响应字典构造结果对象。

        Args:
            data: 图片上传 API 响应字典

        Returns:
            UploadResult: 上传结果实例
        """
        if not data:
            return cls()
        return cls(
            origin_url=data.get("originUrl", ""),
            thumb_url=data.get("thumbUrl", ""),
            width=data.get("width", 0),
            height=data.get("height", 0),
        )

    @classmethod
    def from_video_dict(cls, data: Dict[str, Any]) -> "UploadResult":
        """从视频上传响应字典构造结果对象。

        Args:
            data: 视频上传 API 响应字典

        Returns:
            UploadResult: 上传结果实例
        """
        if not data:
            return cls()
        return cls(
            video_url=data.get("videoUrl", ""),
            cover_url=data.get("coverUrl", ""),
            width=data.get("width", 0),
            height=data.get("height", 0),
        )

    @classmethod
    def from_file_url(cls, url: str, file_path: str = "") -> "UploadResult":
        """从文件上传 URL 构造结果对象。

        Args:
            url: 文件访问 URL
            file_path: 本地文件路径，用于获取文件名和大小

        Returns:
            UploadResult: 上传结果实例
        """
        file_size = 0
        if file_path and os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
        return cls(
            url=url,
            file_name=os.path.basename(file_path) if file_path else "",
            file_size=file_size,
        )


__all__ = [
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
]

