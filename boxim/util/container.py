from __future__ import annotations

from typing import Any, Callable, Dict

from boxim.util.exceptions import ConfigError


class Container:
    """简单依赖注入容器。

    支持单例注册和工厂注册两种模式。

    示例：
        >>> container = Container()
        >>> container.register_singleton("key", 42)
        <...>
        >>> container.resolve("key")
        42
    """

    def __init__(self) -> None:
        self._singletons: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[["Container"], Any]] = {}
        self._instances: Dict[str, Any] = {}

    def register_singleton(self, name: str, instance: Any) -> "Container":
        """注册单例对象。

        Args:
            name: 注册名称
            instance: 单例实例

        Returns:
            返回 self 以支持链式调用
        """
        self._singletons[name] = instance
        return self

    def register_factory(
        self,
        name: str,
        factory: Callable[["Container"], Any],
    ) -> "Container":
        """注册工厂函数（首次解析时创建并缓存实例）。

        Args:
            name: 注册名称
            factory: 工厂函数，接收容器实例作为唯一参数

        Returns:
            返回 self 以支持链式调用
        """
        self._factories[name] = factory
        return self

    def resolve(self, name: str) -> Any:
        """解析已注册的依赖。

        Args:
            name: 注册名称

        Returns:
            解析到的实例

        Raises:
            ConfigError: 名称未注册时抛出
        """
        if name in self._singletons:
            return self._singletons[name]
        if name in self._instances:
            return self._instances[name]
        if name in self._factories:
            instance = self._factories[name](self)
            self._instances[name] = instance
            return instance
        raise ConfigError(f"未注册的依赖: {name}")

    def has(self, name: str) -> bool:
        """检查指定名称是否已注册。

        Args:
            name: 注册名称

        Returns:
            是否已注册
        """
        return (
            name in self._singletons
            or name in self._factories
            or name in self._instances
        )

    def reset(self) -> None:
        """重置所有由工厂创建的实例缓存（单例不受影响）。"""
        self._instances.clear()


__all__ = ["Container"]
