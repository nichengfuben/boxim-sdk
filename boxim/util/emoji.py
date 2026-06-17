from __future__ import annotations

import os
import re
from typing import Dict, List, Optional

EMOJI_NAMES: List[str] = [
    "憨笑", "媚眼", "开心", "坏笑", "可怜", "爱心", "笑哭", "拍手",
    "惊喜", "打气", "大哭", "流泪", "饥饿", "难受", "健身", "示爱",
    "色色", "眨眼", "暴怒", "惊恐", "思考", "头晕", "大吐", "酷笑",
    "翻滚", "享受", "鼻涕", "快乐", "雀跃", "微笑", "贪婪", "红心",
    "粉心", "星星", "大火", "眼睛", "音符", "叹号", "问号", "绿叶",
    "燃烧", "喇叭", "警告", "信封", "房子", "礼物", "点赞", "举手",
    "喝彩", "点头", "摇头", "偷瞄", "庆祝", "疾跑", "打滚", "惊吓",
    "起跳",
]

EMOJI_NAME_TO_INDEX: Dict[str, int] = {
    name: idx for idx, name in enumerate(EMOJI_NAMES)
}

EMOJI_PATTERN = re.compile(r"#([\u4E00-\u9FA5]{1,3});")

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "emoji_assets")


def get_emoji_names() -> List[str]:
    """获取所有 emoji 名称列表（按索引顺序）。"""
    return list(EMOJI_NAMES)


def get_emoji_index(name: str) -> int:
    """根据 emoji 名称获取索引，不存在返回 -1。"""
    return EMOJI_NAME_TO_INDEX.get(name, -1)


def get_emoji_filename(index: int) -> str:
    """根据索引获取 emoji GIF 文件名。

    Args:
        index: emoji 索引 (0-57)

    Returns:
        文件名如 "0.gif"，索引无效时返回空字符串
    """
    if 0 <= index < len(EMOJI_NAMES):
        return f"{index}.gif"
    return ""


def get_emoji_local_path(index: int) -> str:
    """根据索引获取本地 emoji GIF 文件完整路径。

    Args:
        index: emoji 索引 (0-57)

    Returns:
        本地文件路径，索引无效或文件不存在时返回空字符串
    """
    filename = get_emoji_filename(index)
    if not filename:
        return ""
    path = os.path.join(ASSETS_DIR, filename)
    if os.path.exists(path):
        return path
    hashed_path = _find_hashed_file(index)
    return hashed_path


def _find_hashed_file(index: int) -> str:
    """在 assets 目录中查找带 hash 后缀的实际文件。

    Args:
        index: emoji 索引

    Returns:
        文件路径，未找到时返回空字符串
    """
    if not os.path.isdir(ASSETS_DIR):
        return ""
    prefix = f"{index}."
    for fname in os.listdir(ASSETS_DIR):
        if fname.startswith(prefix) and fname.endswith(".gif"):
            return os.path.join(ASSETS_DIR, fname)
    return ""


def text_to_emoji_tags(text: str, base_url: str = "", css_class: str = "emoji-normal") -> str:
    """将消息文本中的 emoji 代码（#名称;）转换为 HTML img 标签。

    Args:
        text: 含 emoji 代码的消息文本
        base_url: 图片 URL 前缀（为空时使用本地文件路径）
        css_class: img 标签的 CSS 类名

    Returns:
        替换后的 HTML 字符串
    """
    def _replace(match: re.Match) -> str:
        name = match.group(1)
        idx = EMOJI_NAME_TO_INDEX.get(name, -1)
        if idx == -1:
            return match.group(0)
        if base_url:
            src = f"{base_url}/{idx}.gif"
        else:
            src = get_emoji_local_path(idx) or f"{idx}.gif"
        return f'<img src="{src}" class="{css_class}" />'

    return EMOJI_PATTERN.sub(_replace, text)


def text_to_emoji_codes(text: str) -> List[str]:
    """提取消息文本中所有 emoji 代码。

    Args:
        text: 含 emoji 代码的消息文本

    Returns:
        emoji 代码列表，如 ["#憨笑;", "#爱心;"]
    """
    return [f"#{name};" for name in EMOJI_PATTERN.findall(text)]


def has_emoji(text: str) -> bool:
    """检查文本中是否包含 emoji 代码。

    Args:
        text: 消息文本

    Returns:
        是否包含 emoji
    """
    return bool(EMOJI_PATTERN.search(text))


def emoji_code_to_name(code: str) -> str:
    """将 emoji 代码（#名称;）解析为名称。

    Args:
        code: emoji 代码，如 "#憨笑;"

    Returns:
        emoji 名称，格式不合法时返回空字符串
    """
    match = re.match(r"^#([\u4E00-\u9FA5]{1,3});$", code)
    if match:
        name = match.group(1)
        if name in EMOJI_NAME_TO_INDEX:
            return name
    return ""


def name_to_emoji_code(name: str) -> str:
    """将 emoji 名称转换为代码格式。

    Args:
        name: emoji 名称，如 "憨笑"

    Returns:
        emoji 代码 "#憨笑;"，名称无效时返回空字符串
    """
    if name in EMOJI_NAME_TO_INDEX:
        return f"#{name};"
    return ""


__all__ = [
    "EMOJI_NAMES",
    "EMOJI_NAME_TO_INDEX",
    "EMOJI_PATTERN",
    "ASSETS_DIR",
    "get_emoji_names",
    "get_emoji_index",
    "get_emoji_filename",
    "get_emoji_local_path",
    "text_to_emoji_tags",
    "text_to_emoji_codes",
    "has_emoji",
    "emoji_code_to_name",
    "name_to_emoji_code",
]
