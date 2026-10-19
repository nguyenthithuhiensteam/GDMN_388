"""Kiểm tra tệp tải lên: phần mở rộng, dung lượng và chữ ký nội dung (magic bytes)."""

import os

from django.conf import settings
from django.core.exceptions import ValidationError

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".odt",
    ".ods",
    ".odp",
    ".txt",
    ".csv",
}
VIDEO_EXTENSIONS = {".mp4", ".webm"}

_ZIP = b"PK\x03\x04"
_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
SIGNATURES = {
    ".pdf": [b"%PDF"],
    ".docx": [_ZIP],
    ".xlsx": [_ZIP],
    ".pptx": [_ZIP],
    ".odt": [_ZIP],
    ".ods": [_ZIP],
    ".odp": [_ZIP],
    ".doc": [_OLE],
    ".xls": [_OLE],
    ".ppt": [_OLE],
}
# Nội dung không được phép xuất hiện ở đầu tệp văn bản thuần (tránh HTML/script trá hình).
TEXT_FORBIDDEN_PREFIXES = (b"<!doctype", b"<html", b"<script", b"<?php", b"<svg")


def _ext(name):
    return os.path.splitext(name or "")[1].lower()


def _head(f, n=16):
    pos = f.tell() if hasattr(f, "tell") else 0
    try:
        f.seek(0)
        data = f.read(n)
    finally:
        f.seek(pos)
    return data or b""


def _check_size(f, max_mb):
    if f.size and f.size > max_mb * 1024 * 1024:
        raise ValidationError(f"Tệp vượt quá dung lượng cho phép ({max_mb} MB).")


def validate_document_upload(f):
    if not f or getattr(f, "_committed", False):
        return  # tệp đã lưu trước đó, không kiểm tra lại
    ext = _ext(f.name)
    if ext not in DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS:
        raise ValidationError("Định dạng không được phép. Chấp nhận: " + ", ".join(sorted(DOCUMENT_EXTENSIONS | IMAGE_EXTENSIONS)))
    _check_size(f, settings.MAX_UPLOAD_MB)
    head = _head(f, 64)
    if ext in IMAGE_EXTENSIONS:
        _verify_image(f)
    elif ext in SIGNATURES and not any(head.startswith(sig) for sig in SIGNATURES[ext]):
        raise ValidationError("Nội dung tệp không khớp với định dạng khai báo.")
    elif ext in {".txt", ".csv"} and head.lstrip().lower().startswith(TEXT_FORBIDDEN_PREFIXES):
        raise ValidationError("Tệp văn bản chứa nội dung không được phép.")


def _verify_image(f):
    from PIL import Image

    pos = f.tell()
    try:
        f.seek(0)
        img = Image.open(f)
        img.verify()
    except Exception as exc:  # noqa: BLE001
        raise ValidationError("Tệp ảnh không hợp lệ hoặc bị hỏng.") from exc
    finally:
        f.seek(pos)


def validate_image_upload(f):
    if not f or getattr(f, "_committed", False):
        return
    if _ext(f.name) not in IMAGE_EXTENSIONS:
        raise ValidationError("Chỉ chấp nhận ảnh: " + ", ".join(sorted(IMAGE_EXTENSIONS)))
    _check_size(f, settings.MAX_IMAGE_MB)
    _verify_image(f)


def validate_video_upload(f):
    if not f or getattr(f, "_committed", False):
        return
    if _ext(f.name) not in VIDEO_EXTENSIONS:
        raise ValidationError("Chỉ chấp nhận video: " + ", ".join(sorted(VIDEO_EXTENSIONS)))
    _check_size(f, settings.MAX_UPLOAD_MB)
