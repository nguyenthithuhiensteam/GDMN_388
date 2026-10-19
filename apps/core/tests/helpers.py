"""Hàm hỗ trợ kiểm thử."""
import io
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.accounts.models import User
from apps.org.models import Campus, ProfessionalGroup, SchoolClass, SchoolYear

PASSWORD = "Mat-khau-An-Toan-2026"


def make_org():
    year = SchoolYear.objects.create(name="2026-2027", start_date=date(2026, 9, 1), end_date=date(2027, 5, 31), is_current=True)
    campus = Campus.objects.create(name="Điểm chính", code="chinh", is_main=True)
    campus2 = Campus.objects.create(name="Điểm lẻ", code="le")
    g1 = ProfessionalGroup.objects.create(name="Tổ MGL", code="mgl")
    g2 = ProfessionalGroup.objects.create(name="Tổ NT", code="nt")
    cls = SchoolClass.objects.create(name="Lớp A", school_year=year, campus=campus, group=g1, age_group="5_6")
    return {"year": year, "campus": campus, "campus2": campus2, "g1": g1, "g2": g2, "cls": cls}


def make_user(username, role, **kw):
    u = User(username=username, full_name=username.title(), role=role, email=f"{username}@example.com", **kw)
    u.set_password(PASSWORD)
    u.save()
    return u


def png_file(name="anh.png", size=(40, 30)):
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 100, 50)).save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def pdf_file(name="tai-lieu.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4\n%test\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF", content_type="application/pdf")
