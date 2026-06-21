from __future__ import annotations

import logging
from typing import Optional

from loguru import logger as _loguru_logger


class _LoguruInterceptHandler(logging.Handler):
    """将标准库 logging 桥接到 loguru，使 boxim SDK 日志统一使用 loguru 格式。"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = record.levelname
        except Exception:
            level = "INFO"
        _loguru_logger.opt(exception=record.exc_info).log(level, record.getMessage())


def setup_logging(
    level: int = logging.INFO,
    fmt: str = "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handler: Optional[logging.Handler] = None,
) -> logging.Logger:
    """配置 BoxIM SDK 日志系统。

    将 boxim logger 的 handler 替换为 loguru 桥接 handler，
    使 SDK 内部日志统一走 loguru 输出，支持 success/trace 等 loguru 特有方法。

    Args:
        level: 日志级别，默认为 INFO
        fmt: 日志格式字符串（已弃用，保留仅为兼容）
        handler: 自定义日志处理器（已弃用，保留仅为兼容）

    Returns:
        logging.Logger: 配置好的 boxim Logger 实例

    示例：
        >>> logger = setup_logging(level=logging.DEBUG)
        >>> logger.name
        'boxim'
        >>> logger.success("连接成功")  # loguru 特有方法
    """
    logger = logging.getLogger("boxim")
    logger.setLevel(level)
    # 清除已有 handler，替换为 loguru 桥接 handler
    logger.handlers.clear()
    logger.addHandler(_LoguruInterceptHandler())
    logger.propagate = False  # 不向上传播，避免重复输出
    return logger


__all__ = ["setup_logging"]
