"""Kho lưu trữ tệp nội bộ: không có URL công khai, chỉ tải qua view có kiểm tra quyền."""
import os
import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
from django.utils.deconstruct import deconstructible
from django.utils.functional import LazyObject


class ProtectedStorage(FileSystemStorage):
    def __init__(self, **kwargs):
        kwargs.setdefault("location", settings.PROTECTED_MEDIA_ROOT)
        kwargs["base_url"] = None
        super().__init__(**kwargs)

    def url(self, name):  # pragma: no cover - cố ý không cung cấp URL trực tiếp
        raise NotImplementedError("Tệp nội bộ chỉ được tải qua view có kiểm tra quyền.")


class _LazyProtectedStorage(LazyObject):
    def _setup(self):
        self._wrapped = ProtectedStorage()


protected_storage = _LazyProtectedStorage()


def get_protected_storage():
    return protected_storage


@deconstructible
class UniqueUploadPath:
    """Đặt tên tệp ngẫu nhiên để tránh ghi đè và tránh lộ tên tệp gốc trong đường dẫn."""

    def __init__(self, prefix):
        self.prefix = prefix

    def __call__(self, instance, filename):
        ext = os.path.splitext(filename)[1].lower()[:10]
        return f"{self.prefix}/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{ext}"

    def __eq__(self, other):
        return isinstance(other, UniqueUploadPath) and other.prefix == self.prefix
