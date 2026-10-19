"""Phục vụ tệp nội bộ sau khi đã kiểm tra quyền."""
import mimetypes
import os
from urllib.parse import quote

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse


def serve_protected(field_file, download_name=None):
    if not field_file:
        raise Http404
    name = download_name or os.path.basename(field_file.name)
    ext = os.path.splitext(field_file.name)[1]
    if download_name and not download_name.lower().endswith(ext):
        name = download_name + ext
    content_type = mimetypes.guess_type(field_file.name)[0] or "application/octet-stream"
    disposition = f"attachment; filename*=UTF-8''{quote(name)}"
    prefix = settings.PROTECTED_MEDIA_ACCEL_PREFIX
    if prefix:
        resp = HttpResponse(content_type=content_type)
        resp["X-Accel-Redirect"] = prefix.rstrip("/") + "/" + quote(field_file.name)
    else:
        try:
            resp = FileResponse(field_file.storage.open(field_file.name, "rb"), content_type=content_type)
        except FileNotFoundError as exc:
            raise Http404 from exc
    resp["Content-Disposition"] = disposition
    resp["X-Content-Type-Options"] = "nosniff"
    resp["Cache-Control"] = "private, no-store"
    return resp
