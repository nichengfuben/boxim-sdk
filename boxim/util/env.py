from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from boxim.util.models import TokenInfo

try:
    from dotenv import load_dotenv, set_key as dotenv_set_key
except ImportError:  # pragma: no cover
    def load_dotenv(*args: object, **kwargs: object) -> None:  # type: ignore[misc]
        """dotenv 不可用时的空实现。"""

    def dotenv_set_key(*args: object, **kwargs: object) -> None:  # type: ignore[misc]
        """dotenv 不可用时的空实现。"""

import logging

_logger = logging.getLogger("boxim")


class EnvManager:
    """环境变量管理器。

    负责令牌和用户信息的读写，支持内存缓存与 .env 文件持久化。

    示例：
        >>> env = EnvManager()
        >>> env.set("MY_KEY", "value")
        >>> env.get("MY_KEY")
        'value'
    """

    def __init__(self, env_file: str = ".env") -> None:
        """初始化环境变量管理器。

        Args:
            env_file: 环境变量文件路径，不存在时自动创建
        """
        self._env_file = env_file
        self._cache: dict[str, str] = {}
        self._ensure_env_file()
        load_dotenv(self._env_file, override=True)

    def _ensure_env_file(self) -> None:
        """确保环境变量文件存在，不存在时创建空文件。"""
        if not os.path.exists(self._env_file):
            Path(self._env_file).write_text(
                "# BoxIM SDK Configuration\n", encoding="utf-8"
            )

    def get(self, key: str, default: Any = None) -> Any:
        """获取环境变量值，优先从内存缓存读取。

        Args:
            key: 环境变量键名
            default: 键不存在时的默认值

        Returns:
            环境变量值或默认值
        """
        if key in self._cache:
            return self._cache[key]
        value = os.environ.get(key)
        if value is not None:
            return value
        return default

    def set(self, key: str, value: Any) -> None:
        """设置环境变量并持久化到 .env 文件。

        Args:
            key: 环境变量键名
            value: 要设置的值，None 时写入空字符串
        """
        str_value = str(value) if value is not None else ""
        self._cache[key] = str_value
        os.environ[key] = str_value
        try:
            dotenv_set_key(self._env_file, key, str_value)
        except Exception as exc:
            _logger.warning("写入环境变量文件失败: %s", exc)

    def get_int(self, key: str, default: int = 0) -> int:
        """获取整数类型环境变量。

        Args:
            key: 环境变量键名
            default: 键不存在或转换失败时的默认值

        Returns:
            整数值
        """
        value = self.get(key, str(default))
        try:
            return int(value) if value else default
        except (ValueError, TypeError):
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """获取布尔类型环境变量。

        Args:
            key: 环境变量键名
            default: 键不存在时的默认值

        Returns:
            布尔值
        """
        value = self.get(key, str(default).lower())
        return str(value).lower() in ("true", "1", "yes", "on")

    def delete(self, key: str) -> None:
        """删除环境变量（内存缓存和进程环境变量）。

        Args:
            key: 环境变量键名
        """
        self._cache.pop(key, None)
        os.environ.pop(key, None)

    def save_token(self, token_info: TokenInfo) -> None:
        """持久化令牌信息到环境变量。

        Args:
            token_info: 令牌信息对象
        """
        self.set("ACCESS_TOKEN", token_info.access_token)
        self.set("REFRESH_TOKEN", token_info.refresh_token)
        self.set("ACCESS_TOKEN_EXPIRES", token_info.access_token_expires_at)
        self.set("REFRESH_TOKEN_EXPIRES", token_info.refresh_token_expires_at)

    def get_token(self) -> Optional[TokenInfo]:
        """从环境变量读取令牌信息。

        Returns:
            TokenInfo 实例，访问令牌不存在时返回 None
        """
        access = self.get("ACCESS_TOKEN")
        if not access:
            return None
        return TokenInfo(
            access_token=str(access),
            refresh_token=str(self.get("REFRESH_TOKEN") or ""),
            access_token_expires_at=self.get_int("ACCESS_TOKEN_EXPIRES"),
            refresh_token_expires_at=self.get_int("REFRESH_TOKEN_EXPIRES"),
        )

    def clear_token(self) -> None:
        """清除所有令牌相关环境变量。"""
        for key in (
            "ACCESS_TOKEN",
            "REFRESH_TOKEN",
            "ACCESS_TOKEN_EXPIRES",
            "REFRESH_TOKEN_EXPIRES",
            "USER_ID",
        ):
            self.delete(key)


__all__ = ["EnvManager"]
