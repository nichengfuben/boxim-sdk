from __future__ import annotations

import asyncio
import logging
import mimetypes
import os
import time
from typing import Any, Dict, Optional
from urllib.parse import quote, urljoin

import aiohttp
import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from boxim.util.config import SDKConfig
from boxim.util.exceptions import AuthError, BoxIMError, NetworkError, ValidationError
from boxim.util.models import TokenInfo
from boxim.util.protocols import TokenStore

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_logger = logging.getLogger("boxim")


class HTTPTransport:
    """HTTP 传输层。

    封装同步/异步 HTTP 请求、文件上传、令牌自动刷新等逻辑。
    """

    def __init__(
        self,
        config: SDKConfig,
        token_store: Optional[TokenStore] = None,
    ) -> None:
        self._config = config
        self._token_store = token_store
        self._session: Optional[requests.Session] = None
        self._async_session: Optional[aiohttp.ClientSession] = None
        self._refreshing = False
        self._refresh_lock = asyncio.Lock()
        self._sync_refresh_lock = False

    @property
    def session(self) -> requests.Session:
        """获取同步 HTTP 会话（懒加载）。"""
        if self._session is None:
            self._session = self._create_sync_session()
        return self._session

    def _create_sync_session(self) -> requests.Session:
        """创建配置了重试策略的同步 HTTP 会话。

        Returns:
            requests.Session: 配置好的会话对象
        """
        session = requests.Session()
        retry = Retry(
            total=self._config.max_retries,
            status_forcelist=self._config.retry_status_forcelist,
            backoff_factor=self._config.retry_backoff_factor,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _build_headers(
        self,
        extra: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """构建 HTTP 请求头，自动附加访问令牌。

        Args:
            extra: 额外请求头字典，会覆盖默认值

        Returns:
            Dict[str, str]: 完整请求头字典
        """
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "User-Agent": self._config.user_agent,
            "Origin": self._config.base_url,
            "Referer": f"{self._config.base_url}/",
        }

        token = self._resolve_access_token()
        if token:
            headers["accessToken"] = quote(token, safe="")

        if extra:
            headers.update(extra)
        return headers

    def _resolve_access_token(self) -> Optional[str]:
        """多途径获取访问令牌。

        按以下优先级查找：token_store -> 环境变量。

        Returns:
            访问令牌字符串，不存在时返回 None
        """
        if self._token_store is not None:
            token_info = self._token_store.get_token()
            if token_info is not None and token_info.access_token:
                return token_info.access_token
            if hasattr(self._token_store, "get"):
                raw = self._token_store.get("ACCESS_TOKEN")  # type: ignore[attr-defined]
                if raw:
                    return str(raw)
        return os.environ.get("ACCESS_TOKEN")

    def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        files: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        retry_count: int = 0,
        **kwargs: Any,
    ) -> Any:
        """发送同步 HTTP 请求。

        Args:
            method: HTTP 方法（GET/POST/PUT/DELETE 等）
            endpoint: API 端点路径（如 "/api/login"）
            params: URL 查询参数
            json_data: 请求体 JSON 数据
            data: 原始请求体数据
            files: 文件上传字典
            headers: 自定义请求头（会覆盖默认值）
            retry_count: 当前重试次数（内部使用）
            **kwargs: 透传给 requests.Session.request 的额外参数

        Returns:
            API 响应中 data 字段的值

        Raises:
            AuthError: 认证失败或令牌已过期
            NetworkError: 网络请求失败
            BoxIMError: 业务逻辑错误
        """
        url = urljoin(self._config.base_url, endpoint)
        req_headers = self._build_headers(headers)

        if files:
            req_headers.pop("Content-Type", None)

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                data=data,
                files=files,
                headers=req_headers,
                timeout=self._config.timeout,
                verify=self._config.ssl_verify,
                **kwargs,
            )
            response.raise_for_status()
            return self._parse_response(
                response.json(),
                lambda: self.request(
                    method,
                    endpoint,
                    params,
                    json_data,
                    data,
                    files,
                    headers,
                    retry_count + 1,
                    **kwargs,
                ),
                retry_count,
                is_async=False,
            )
        except requests.RequestException as exc:
            raise NetworkError(f"网络请求失败: {exc}") from exc

    def _parse_response(
        self,
        response_data: Dict[str, Any],
        retry_fn: Any,
        retry_count: int,
        is_async: bool,
    ) -> Any:
        """解析 API 响应并处理错误码。

        Args:
            response_data: 响应 JSON 字典
            retry_fn: 重试函数（同步或异步）
            retry_count: 当前重试次数
            is_async: 是否为异步场景（影响令牌刷新方式）

        Returns:
            data 字段值

        Raises:
            AuthError: code 为 401 且刷新失败时
            BoxIMError: 其他业务错误
        """
        code = response_data.get("code")
        if code == 200:
            return response_data.get("data")
        if code == 401:
            if self._config.auto_refresh_token and retry_count == 0:
                _logger.info("令牌过期，尝试自动刷新...")
                if not is_async and self._sync_refresh():
                    return retry_fn()
            raise AuthError("访问令牌无效或已过期", 401)
        raise BoxIMError(
            response_data.get("message", "请求失败"),
            code,
        )

    async def arequest(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        files: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        retry_count: int = 0,
        **kwargs: Any,
    ) -> Any:
        """发送异步 HTTP 请求。

        Args:
            method: HTTP 方法
            endpoint: API 端点路径
            params: URL 查询参数
            json_data: 请求体 JSON 数据
            data: 原始请求体数据
            files: 文件上传字典
            headers: 自定义请求头
            retry_count: 当前重试次数（内部使用）
            **kwargs: 透传给 aiohttp 的额外参数

        Returns:
            API 响应中 data 字段的值

        Raises:
            AuthError: 认证失败
            NetworkError: 网络请求失败
            BoxIMError: 业务逻辑错误
        """
        session = await self._get_async_session()
        url = urljoin(self._config.base_url, endpoint)
        req_headers = self._build_headers(headers)

        if files:
            req_headers.pop("Content-Type", None)

        req_kwargs: Dict[str, Any] = {
            "headers": req_headers,
            "timeout": aiohttp.ClientTimeout(total=self._config.timeout),
        }
        if params:
            req_kwargs["params"] = params
        if json_data:
            req_kwargs["json"] = json_data
        if data:
            req_kwargs["data"] = data
        if files:
            req_kwargs["data"] = self._build_form_data(files)
        for key, val in kwargs.items():
            if key not in req_kwargs:
                req_kwargs[key] = val

        try:
            async with session.request(method, url, **req_kwargs) as response:
                response.raise_for_status()
                response_data = await response.json()

                code = response_data.get("code")
                if code == 200:
                    return response_data.get("data")
                if code == 401:
                    if self._config.auto_refresh_token and retry_count == 0:
                        _logger.info("令牌过期，尝试自动刷新...")
                        if await self._async_refresh():
                            return await self.arequest(
                                method,
                                endpoint,
                                params,
                                json_data,
                                data,
                                files,
                                headers,
                                retry_count + 1,
                                **kwargs,
                            )
                    raise AuthError("访问令牌无效或已过期", 401)
                raise BoxIMError(
                    response_data.get("message", "请求失败"),
                    code,
                )
        except aiohttp.ClientError as exc:
            raise NetworkError(f"网络请求失败: {exc}") from exc

    async def _get_async_session(self) -> aiohttp.ClientSession:
        """获取异步 HTTP 会话（懒加载）。

        Returns:
            aiohttp.ClientSession: 异步会话对象
        """
        if self._async_session is None:
            ssl_ctx = False if not self._config.ssl_verify else None
            connector = aiohttp.TCPConnector(ssl=ssl_ctx)
            self._async_session = aiohttp.ClientSession(connector=connector)
        return self._async_session

    def _build_form_data(
        self, files: Dict[str, Any]
    ) -> aiohttp.FormData:
        """将文件字典构建为 aiohttp.FormData 对象。

        Args:
            files: 文件字典，值可为 (filename, content, content_type) 或文件对象

        Returns:
            aiohttp.FormData: 表单数据对象
        """
        form_data = aiohttp.FormData()
        for key, file_obj in files.items():
            if isinstance(file_obj, tuple):
                if len(file_obj) == 3:
                    filename, content, content_type = file_obj
                    form_data.add_field(
                        key,
                        content,
                        filename=filename,
                        content_type=content_type,
                    )
                elif len(file_obj) == 2:
                    filename, content = file_obj
                    form_data.add_field(key, content, filename=filename)
                else:
                    form_data.add_field(key, file_obj[0])
            else:
                form_data.add_field(key, file_obj)
        return form_data

    def upload_file_sync(
        self,
        endpoint: str,
        file_path: str,
        field_name: str = "file",
        params: Optional[Dict[str, str]] = None,
    ) -> Any:
        """同步上传文件。

        Args:
            endpoint: 上传 API 端点路径
            file_path: 本地文件路径
            field_name: 表单字段名
            params: 额外查询参数

        Returns:
            API 响应中 data 字段的值

        Raises:
            ValidationError: 文件不存在
            BoxIMError: 上传失败
        """
        if not os.path.exists(file_path):
            raise ValidationError(f"文件不存在: {file_path}")

        mime_type = self._guess_mime(file_path)
        url = urljoin(self._config.base_url, endpoint)
        headers = self._build_headers()
        headers.pop("Content-Type", None)

        with open(file_path, "rb") as file_handle:
            files = {
                field_name: (os.path.basename(file_path), file_handle, mime_type)
            }
            response = self.session.post(
                url,
                files=files,
                headers=headers,
                params=params,
                timeout=self._config.timeout,
                verify=self._config.ssl_verify,
            )

        response.raise_for_status()
        resp_data = response.json()
        if resp_data.get("code") == 200:
            return resp_data.get("data")
        raise BoxIMError(
            resp_data.get("message", "上传失败"), resp_data.get("code")
        )

    async def upload_file_async(
        self,
        endpoint: str,
        file_path: str,
        field_name: str = "file",
        params: Optional[Dict[str, str]] = None,
    ) -> Any:
        """异步上传文件。

        Args:
            endpoint: 上传 API 端点路径
            file_path: 本地文件路径
            field_name: 表单字段名
            params: 额外查询参数

        Returns:
            API 响应中 data 字段的值

        Raises:
            ValidationError: 文件不存在
            BoxIMError: 上传失败
        """
        if not os.path.exists(file_path):
            raise ValidationError(f"文件不存在: {file_path}")

        mime_type = self._guess_mime(file_path)
        session = await self._get_async_session()
        url = urljoin(self._config.base_url, endpoint)
        headers = self._build_headers()
        headers.pop("Content-Type", None)

        with open(file_path, "rb") as file_handle:
            form_data = aiohttp.FormData()
            form_data.add_field(
                field_name,
                file_handle,
                filename=os.path.basename(file_path),
                content_type=mime_type,
            )
            async with session.post(
                url,
                data=form_data,
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=self._config.timeout),
            ) as response:
                response.raise_for_status()
                resp_data = await response.json()

        if resp_data.get("code") == 200:
            return resp_data.get("data")
        raise BoxIMError(
            resp_data.get("message", "上传失败"), resp_data.get("code")
        )

    @staticmethod
    def _guess_mime(file_path: str) -> str:
        """猜测文件的 MIME 类型。

        Args:
            file_path: 文件路径

        Returns:
            MIME 类型字符串，无法识别时返回 application/octet-stream
        """
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or "application/octet-stream"

    def _sync_refresh(self) -> bool:
        """同步刷新访问令牌。

        Returns:
            刷新成功返回 True，否则返回 False
        """
        if self._sync_refresh_lock:
            time.sleep(0.5)
            return True

        self._sync_refresh_lock = True
        try:
            return self._do_sync_refresh()
        finally:
            self._sync_refresh_lock = False

    def _do_sync_refresh(self) -> bool:
        """执行同步令牌刷新请求。

        Returns:
            刷新成功返回 True，否则返回 False
        """
        if not self._token_store:
            return False

        token_info = self._token_store.get_token()
        if not token_info or not token_info.refresh_token:
            _logger.error("没有可用的刷新令牌")
            return False

        url = urljoin(self._config.base_url, "/api/refreshToken")
        try:
            response = self.session.request(
                "PUT",
                url,
                headers={"refreshToken": token_info.refresh_token},
                timeout=self._config.timeout,
                verify=self._config.ssl_verify,
            )
            response.raise_for_status()
            result = response.json()
            if result.get("code") == 200:
                new_token = TokenInfo.from_dict(result.get("data", {}))
                self._token_store.save_token(new_token)
                _logger.info("令牌刷新成功")
                return True
            _logger.error("令牌刷新失败: %s", result.get("message"))
            return False
        except Exception as exc:
            _logger.error("令牌刷新异常: %s", exc)
            return False

    async def _async_refresh(self) -> bool:
        """异步刷新访问令牌，使用锁防止并发重复刷新。

        Returns:
            刷新成功返回 True，否则返回 False
        """
        async with self._refresh_lock:
            if self._refreshing:
                while self._refreshing:
                    await asyncio.sleep(0.1)
                return True

            self._refreshing = True
            try:
                return await self._do_async_refresh()
            finally:
                self._refreshing = False

    async def _do_async_refresh(self) -> bool:
        """执行异步令牌刷新请求。

        Returns:
            刷新成功返回 True，否则返回 False
        """
        if not self._token_store:
            return False

        token_info = self._token_store.get_token()
        if not token_info or not token_info.refresh_token:
            _logger.error("没有可用的刷新令牌")
            return False

        session = await self._get_async_session()
        url = urljoin(self._config.base_url, "/api/refreshToken")
        try:
            async with session.request(
                "PUT",
                url,
                headers={"refreshToken": token_info.refresh_token},
                timeout=aiohttp.ClientTimeout(total=self._config.timeout),
            ) as response:
                response.raise_for_status()
                result = await response.json()

            if result.get("code") == 200:
                new_token = TokenInfo.from_dict(result.get("data", {}))
                self._token_store.save_token(new_token)
                _logger.info("令牌刷新成功")
                return True
            _logger.error("令牌刷新失败: %s", result.get("message"))
            return False
        except Exception as exc:
            _logger.error("令牌刷新异常: %s", exc)
            return False

    def close(self) -> None:
        """关闭同步 HTTP 会话，释放连接资源。"""
        if self._session is not None:
            self._session.close()
            self._session = None

    async def aclose(self) -> None:
        """关闭异步 HTTP 会话，释放连接资源。"""
        if self._async_session is not None:
            await self._async_session.close()
            self._async_session = None


__all__ = ["HTTPTransport"]
