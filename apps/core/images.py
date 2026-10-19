"""Tối ưu ảnh tải lên: thu nhỏ kích thước, xóa dữ liệu EXIF (có thể chứa vị trí GPS)."""
import io
import os

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageOps


def optimize_image_field(field_file, max_dim=None):
    """Đọc ảnh, xoay theo EXIF, thu nhỏ, lưu lại không kèm EXIF. Trả về True nếu đã xử lý."""
    if not field_file:
        return False
    max_dim = max_dim or settings.IMAGE_MAX_DIMENSION
    field_file.open("rb")
    try:
        img = Image.open(field_file)
        fmt = (img.format or "JPEG").upper()
        if fmt == "GIF":
            return False  # giữ nguyên ảnh động
        img = ImageOps.exif_transpose(img)
        img.thumbnail((max_dim, max_dim))
        out = io.BytesIO()
        if fmt in ("JPEG", "MPO"):
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.save(out, "JPEG", quality=82, optimize=True, progressive=True)
            ext = ".jpg"
        elif fmt == "WEBP":
            img.save(out, "WEBP", quality=82)
            ext = ".webp"
        else:
            img.save(out, "PNG", optimize=True)
            ext = ".png"
    finally:
        field_file.close()
    name = os.path.splitext(os.path.basename(field_file.name))[0] + ext
    old_name = field_file.name
    field_file.save(name, ContentFile(out.getvalue()), save=False)
    if old_name != field_file.name:
        field_file.storage.delete(old_name)
    return True
