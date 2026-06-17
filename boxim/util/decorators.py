from __future__ import annotations

import asyncio
import functools
import logging
import time
from typing import Any, Callable, Optional, Tuple, Type

from boxim.util.exceptions import AuthError, BoxIMError

_logger = logging.getLogger("boxim")


def require_login(func: Callable[..., Any]) -> Callable[..., Any]:
    """同步登录状态检查装饰器。

    在执行被装饰方法前验证当前实例是否已登录（持有有效访问令牌）。

    Args:
        func: 被装饰的同步方法

    Returns:
        包装后的方法

    Raises:
        AuthError: 未登录或令牌无效时抛出

    示例：
        >>> class MyClient:
        ...     @require_login
        ...     def get_data(self):
        ...         pass
    """

    @functools.wraps(func)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        _check_login(self)
        return func(self, *args, **kwargs)

    return wrapper


def async_require_login(func: Callable[..., Any]) -> Callable[..., Any]:
    """异步登录状态检查装饰器。

    在执行被装饰异步方法前验证当前实例是否已登录。

    Args:
        func: 被装饰的异步方法

    Returns:
        包装后的异步方法

    Raises:
        AuthError: 未登录或令牌无效时抛出

    示例：
        >>> class MyClient:
        ...     @async_require_login
        ...     async def get_data(self):
        ...         pass
    """

    @functools.wraps(func)
    async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        _check_login(self)
        return await func(self, *args, **kwargs)

    return wrapper


def _check_login(instance: Any) -> None:
    """检查实例是否已登录，未登录时抛出 AuthError。

    Args:
        instance: BoxIM 实例对象

    Raises:
        AuthError: 未登录或令牌无效
    """
    token_store = getattr(instance, "_token_store", None) or getattr(
        instance, "token_store", None
    )
    if token_store is None:
        env = getattr(instance, "_env", None)
        if env is None or not env.get("ACCESS_TOKEN"):
            raise AuthError("请先登录")
        return

    token = token_store.get_token()
    if not token or not token.access_token:
        raise AuthError("请先登录")


def auto_retry(
    max_retries: int = 3,
    delay: float = 1.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """自动重试装饰器，支持指数退避。

    Args:
        max_retries: 最大重试次数
        delay: 初始重试延迟（秒），每次翻倍
        exceptions: 需要重试的异常类型元组

    Returns:
        装饰器函数

    示例：
        >>> @auto_retry(max_retries=3, delay=1.0, exceptions=(NetworkError,))
        ... def call_api():
        ...     pass
    """

    def decorator(
        func: Callable[..., Any],
    ) -> Callable[..., Any]:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                last_error: Optional[Exception] = None
                for attempt in range(max_retries):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as exc:
                        last_error = exc
                        if attempt < max_retries - 1:
                            wait = delay * (2**attempt)
                            _logger.warning(
                                "重试 %s/%s，等待 %ss: %s",
                                attempt + 1,
                                max_retries,
                                wait,
                                exc,
                            )
                            await asyncio.sleep(wait)
                if last_error is not None:
                    raise last_error
                raise BoxIMError("重试失败")

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error: Optional[Exception] = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_error = exc
                    if attempt < max_retries - 1:
                        wait = delay * (2**attempt)
                        _logger.warning(
                            "重试 %s/%s，等待 %ss: %s",
                            attempt + 1,
                            max_retries,
                            wait,
                            exc,
                        )
                        time.sleep(wait)
            if last_error is not None:
                raise last_error
            raise BoxIMError("重试失败")

        return sync_wrapper

    return decorator


def validate_params(
    **validators: Callable[[Any], bool],
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """参数验证装饰器。

    在函数调用前对指定参数执行自定义验证，验证失败时抛出 ValidationError。

    Args:
        **validators: 参数名到验证函数的映射，验证函数返回 True 表示通过

    Returns:
        装饰器函数

    示例：
        >>> from boxim.util.exceptions import ValidationError
        >>> @validate_params(user_id=lambda x: x > 0)
        ... def get_user(self, user_id: int):
        ...     pass
    """
    from boxim.util.exceptions import ValidationError

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            import inspect

            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            for param_name, validator in validators.items():
                if param_name in bound.arguments:
                    value = bound.arguments[param_name]
                    if not validator(value):
                        raise ValidationError(
                            f"参数 '{param_name}' 验证失败: {value!r}"
                        )

            return func(*args, **kwargs)

        return wrapper

    return decorator


__all__ = [
    "require_login",
    "async_require_login",
    "auto_retry",
    "validate_params",
]
