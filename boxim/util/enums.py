from __future__ import annotations

from enum import Enum, IntEnum


class MessageType(IntEnum):
    """消息类型枚举（47 种，对齐官方 API 文档）。"""

    TEXT = 0
    IMAGE = 1
    FILE = 2
    AUDIO = 3
    VIDEO = 4
    USER_CARD = 5
    GROUP_CARD = 6
    STICKER = 7
    MERGE_FORWARD = 8
    RECALL = 10
    READED = 11
    RECEIPT = 12
    TIP_TIME = 20
    TIP_TEXT = 21
    LOADING = 30
    ACT_RT_VOICE = 40
    ACT_RT_VIDEO = 41
    USER_BANNED = 50
    SYSTEM_MESSAGE = 53
    USER_UNREG = 54
    FRIEND_REQ_APPLY = 70
    FRIEND_REQ_APPROVE = 71
    FRIEND_REQ_REJECT = 72
    FRIEND_REQ_RECALL = 73
    FRIEND_NEW = 80
    FRIEND_DEL = 81
    FRIEND_ONLINE = 82
    FRIEND_DND = 83
    FRIEND_TOP = 84
    GROUP_NEW = 90
    GROUP_DEL = 91
    GROUP_TOP_MESSAGE = 92
    GROUP_DND = 93
    GROUP_TOP = 94
    GROUP_ALL_MUTED = 95
    GROUP_MEMBER_MUTED = 96
    RTC_SETUP_VOICE = 100
    RTC_SETUP_VIDEO = 101
    RTC_ACCEPT = 102
    RTC_REJECT = 103
    RTC_CANCEL = 104
    RTC_FAILED = 105
    RTC_HANDUP = 106
    RTC_OFFER = 107
    RTC_ANSWER = 108
    RTC_CANDIDATE = 109
    RTC_PRIVATE_DEVICE = 110
    RTC_GROUP_SETUP = 200
    RTC_GROUP_ACCEPT = 201
    RTC_GROUP_REJECT = 202
    RTC_GROUP_FAILED = 203
    RTC_GROUP_CANCEL = 204
    RTC_GROUP_QUIT = 205
    RTC_GROUP_INVITE = 206
    RTC_GROUP_JOIN = 207
    RTC_GROUP_OFFER = 208
    RTC_GROUP_ANSWER = 209
    RTC_GROUP_CANDIDATE = 210
    RTC_GROUP_DEVICE = 211
    RTC_GROUP_INFO = 212

    # ---- 向后兼容别名 ----
    VOICE = 3
    SYSTEM_NOTIFICATION = 53
    USER_LOGOUT = 54
    ONLINE_STATUS = 82
    FRIEND_REQUEST = 70
    FRIEND_REQUEST_ACCEPT = 71
    FRIEND_REQUEST_REJECT = 72
    FRIEND_REQUEST_RECALL = 73
    GROUP_CREATE = 90
    GROUP_DISMISS = 91
    RTC_CALL_VOICE = 40
    RTC_CALL_VIDEO = 41
    RTC_PRIVATE_SETUP = 100
    RTC_PRIVATE_ACCEPT = 102
    RTC_PRIVATE_REJECT = 103
    RTC_PRIVATE_CANCEL = 104
    RTC_PRIVATE_FAILED = 105
    RTC_PRIVATE_HANDUP = 106
    RTC_PRIVATE_OFFER = 107
    RTC_PRIVATE_ANSWER = 108
    RTC_PRIVATE_CANDIDATE = 109


class TerminalType(IntEnum):
    """终端类型枚举。"""

    WEB = 0
    APP = 1


class FriendRequestStatus(IntEnum):
    """好友请求状态枚举。"""

    PENDING = 1
    APPROVED = 2
    REJECTED = 3
    EXPIRED = 4

    ACCEPTED = 2


class ComplaintType(IntEnum):
    """投诉类型枚举。"""

    HARASSMENT = 1
    FRAUD = 2
    BAD_CONTENT = 3
    OTHER = 99


class UserSex(IntEnum):
    """用户性别枚举。"""

    FEMALE = 0
    MALE = 1
    UNKNOWN = 2


class RegistrationMode(str, Enum):
    """注册方式枚举。"""

    USERNAME = "username"
    PHONE = "phone"
    EMAIL = "email"


class ChatType(str, Enum):
    """聊天类型枚举。"""

    PRIVATE = "private"
    GROUP = "group"


class RTCMode(str, Enum):
    """通话模式枚举。"""

    VOICE = "voice"
    AUDIO = "audio"
    VIDEO = "video"


class RTCState(str, Enum):
    """通话状态枚举。"""

    FREE = "free"
    WAIT_CALL = "wait_call"
    WAIT_ACCEPT = "wait_accept"
    ACCEPTED = "accepted"
    CHATING = "chating"
    FAILED = "failed"
    ENDED = "ended"

    IDLE = "free"
    CALLING = "wait_call"
    RINGING = "wait_accept"
    CONNECTED = "chating"


class QRLoginStatus(str, Enum):
    """二维码登录状态枚举。"""

    WAITING = "WAITING"
    SCANNED = "SCANNED"
    CONFIRMED = "CONFIRMED"
    EXPIRED = "EXPIRED"

    PENDING = "WAITING"


class WebSocketCommand(IntEnum):
    """WebSocket 命令类型枚举。"""

    AUTH = 0
    HEARTBEAT = 1
    FORCE_OFFLINE = 2
    PRIVATE_MESSAGE = 3
    GROUP_MESSAGE = 4
    SYSTEM_MESSAGE = 5


__all__ = [
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
]
