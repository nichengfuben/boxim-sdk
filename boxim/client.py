#client.py
from __future__ import annotations

from typing import Optional

from boxim.boxim import BoxIM

_im_client: Optional[BoxIM] = None


def get_im_client() -> BoxIM:
    """获取全局 IM 客户端单例实例。

    Returns:
        BoxIM: 全局客户端实例

    Raises:
        RuntimeError: 客户端尚未初始化时抛出
    """
    global _im_client
    if _im_client is None:
        raise RuntimeError(
            "IM 客户端未初始化，请先调用 initialize_im_client()"
        )
    return _im_client


def initialize_im_client(username: str, password: str) -> BoxIM:
    """初始化全局 IM 客户端（幂等，已初始化则直接返回）。

    Args:
        username: 用户名/邮箱/手机号
        password: 密码

    Returns:
        BoxIM: 已登录的全局客户端实例
    """
    global _im_client
    if _im_client is None:
        _im_client = BoxIM().login(username, password)
    return _im_client
