from __future__ import annotations

import logging
from typing import Optional


def setup_logging(
    level: int = logging.INFO,
    fmt: str = "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handler: Optional[logging.Handler] = None,
) -> logging.Logger:
    """配置 BoxIM SDK 日志系统。

    若 boxim logger 已有处理器则跳过配置，避免重复添加。

    Args:
        level: 日志级别，默认为 INFO
        fmt: 日志格式字符串
        handler: 自定义日志处理器；为 None 时使用 StreamHandler

    Returns:
        logging.Logger: 配置好的 boxim Logger 实例

    示例：
        >>> logger = setup_logging(level=logging.DEBUG)
        >>> logger.name
        'boxim'
    """
    logger = logging.getLogger("boxim")
    logger.setLevel(level)
    if not logger.handlers:
        h = handler or logging.StreamHandler()
        h.setFormatter(logging.Formatter(fmt))
        logger.addHandler(h)
    return logger


__all__ = ["setup_logging"]
