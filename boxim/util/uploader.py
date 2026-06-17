from __future__ import annotations

import mimetypes
import os
from typing import List, Optional

from boxim.util.config import SDKConfig
from boxim.util.exceptions import ValidationError
from boxim.util.models import UploadResult
from boxim.util.transport_http import HTTPTransport


class FileUploader:
    """文件上传工具。

    封装图片、视频、普通文件的上传逻辑，并在上传前进行大小和类型校验。
    """

    def __init__(self, http: HTTPTransport, config: SDKConfig) -> None:
        self._http = http
        self._config = config

    def _validate_file(
        self,
        file_path: str,
        max_size: int,
        allowed_types: Optional[List[str]] = None,
    ) -> str:
        """校验文件有效性。

        Args:
            file_path: 文件路径
            max_size: 最大允许字节数
            allowed_types: 允许的 MIME 类型前缀列表（如 ["image/"]）

        Returns:
            文件的 MIME 类型字符串

        Raises:
            ValidationError: 文件不存在、超出大小限制或类型不允许
        """
        if not os.path.exists(file_path):
            raise ValidationError(f"文件不存在: {file_path}")

        file_size = os.path.getsize(file_path)
        if file_size > max_size:
            raise ValidationError(
                f"文件大小 ({file_size} bytes) 超过限制"
                f" ({max_size // (1024 * 1024)} MB)"
            )

        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "application/octet-stream"

        if allowed_types and not any(
            mime_type.startswith(t) for t in allowed_types
        ):
            raise ValidationError(
                f"不支持的文件类型: {mime_type}，"
                f"允许: {', '.join(allowed_types)}"
            )

        return mime_type

    def upload_image(self, file_path: str) -> UploadResult:
        """同步上传图片。

        Args:
            file_path: 本地图片文件路径

        Returns:
            UploadResult: 上传结果

        Raises:
            ValidationError: 文件校验失败
        """
        self._validate_file(
            file_path, self._config.max_image_size, ["image/"]
        )
        data = self._http.upload_file_sync(
            "/api/image/upload",
            file_path,
            params={"isPermanent": "true"},
        )
        if isinstance(data, dict):
            return UploadResult.from_image_dict(data)
        return UploadResult(url=str(data))

    async def aupload_image(self, file_path: str) -> UploadResult:
        """异步上传图片。

        Args:
            file_path: 本地图片文件路径

        Returns:
            UploadResult: 上传结果

        Raises:
            ValidationError: 文件校验失败
        """
        self._validate_file(
            file_path, self._config.max_image_size, ["image/"]
        )
        data = await self._http.upload_file_async(
            "/api/image/upload",
            file_path,
            params={"isPermanent": "true"},
        )
        if isinstance(data, dict):
            return UploadResult.from_image_dict(data)
        return UploadResult(url=str(data))

    def upload_file(self, file_path: str) -> UploadResult:
        """同步上传文件。

        Args:
            file_path: 本地文件路径

        Returns:
            UploadResult: 上传结果

        Raises:
            ValidationError: 文件校验失败
        """
        self._validate_file(file_path, self._config.max_file_size)
        data = self._http.upload_file_sync("/api/file/upload", file_path)
        url = data if isinstance(data, str) else data.get("url", "")
        return UploadResult.from_file_url(url, file_path)

    async def aupload_file(self, file_path: str) -> UploadResult:
        """异步上传文件。

        Args:
            file_path: 本地文件路径

        Returns:
            UploadResult: 上传结果

        Raises:
            ValidationError: 文件校验失败
        """
        self._validate_file(file_path, self._config.max_file_size)
        data = await self._http.upload_file_async(
            "/api/file/upload", file_path
        )
        url = data if isinstance(data, str) else data.get("url", "")
        return UploadResult.from_file_url(url, file_path)

    def upload_video(self, file_path: str) -> UploadResult:
        """同步上传视频。

        Args:
            file_path: 本地视频文件路径

        Returns:
            UploadResult: 上传结果

        Raises:
            ValidationError: 文件校验失败
        """
        self._validate_file(file_path, self._config.max_video_size)
        data = self._http.upload_file_sync(
            "/api/video/upload",
            file_path,
        )
        if isinstance(data, dict):
            return UploadResult.from_video_dict(data)
        return UploadResult(url=str(data))

    async def aupload_video(self, file_path: str) -> UploadResult:
        """异步上传视频。

        Args:
            file_path: 本地视频文件路径

        Returns:
            UploadResult: 上传结果

        Raises:
            ValidationError: 文件校验失败
        """
        self._validate_file(file_path, self._config.max_video_size)
        data = await self._http.upload_file_async(
            "/api/video/upload",
            file_path,
        )
        if isinstance(data, dict):
            return UploadResult.from_video_dict(data)
        return UploadResult(url=str(data))


__all__ = ["FileUploader"]
