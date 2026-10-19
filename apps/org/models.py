"""Cơ cấu tổ chức: năm học, điểm trường, tổ chuyên môn, lớp, danh mục chuyên môn."""

from django.core.exceptions import ValidationError
from django.db import models


class SchoolYear(models.Model):
    name = models.CharField("Năm học", max_length=20, unique=True, help_text="Ví dụ: 2026-2027")
    start_date = models.DateField("Ngày bắt đầu")
    end_date = models.DateField("Ngày kết thúc")
    is_current = models.BooleanField("Năm học hiện hành", default=False)

    class Meta:
        ordering = ["-start_date"]
        verbose_name = "Năm học"
        verbose_name_plural = "Năm học"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_current:
            SchoolYear.objects.exclude(pk=self.pk).filter(is_current=True).update(is_current=False)

    def clean(self):
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError("Ngày kết thúc phải sau ngày bắt đầu.")

    @classmethod
    def current(cls):
        return cls.objects.filter(is_current=True).first()


class Campus(models.Model):
    name = models.CharField("Tên điểm trường", max_length=150, unique=True)
    code = models.SlugField("Mã", max_length=30, unique=True)
    address = models.CharField("Địa chỉ", max_length=255, blank=True)
    phone = models.CharField("Điện thoại", max_length=30, blank=True)
    is_main = models.BooleanField("Điểm trường chính", default=False)
    description = models.TextField("Mô tả cơ sở vật chất", blank=True)
    is_active = models.BooleanField("Đang hoạt động", default=True)
    order = models.PositiveIntegerField("Thứ tự", default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Điểm trường"
        verbose_name_plural = "Điểm trường"

    def __str__(self):
        return self.name


class ProfessionalGroup(models.Model):
    name = models.CharField("Tên tổ", max_length=150, unique=True)
    code = models.SlugField("Mã", max_length=30, unique=True)
    description = models.TextField("Mô tả", blank=True)
    is_active = models.BooleanField("Đang hoạt động", default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Tổ chuyên môn"
        verbose_name_plural = "Tổ chuyên môn"

    def __str__(self):
        return self.name


class SchoolClass(models.Model):
    AGE_GROUPS = [
        ("nha_tre", "Nhà trẻ"),
        ("3_4", "Mẫu giáo 3-4 tuổi"),
        ("4_5", "Mẫu giáo 4-5 tuổi"),
        ("5_6", "Mẫu giáo 5-6 tuổi"),
        ("ghep", "Lớp ghép"),
    ]
    name = models.CharField("Tên lớp", max_length=100)
    school_year = models.ForeignKey(SchoolYear, on_delete=models.PROTECT, verbose_name="Năm học", related_name="classes")
    campus = models.ForeignKey(Campus, on_delete=models.PROTECT, verbose_name="Điểm trường", related_name="classes")
    group = models.ForeignKey(
        ProfessionalGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Tổ chuyên môn",
        related_name="classes",
    )
    age_group = models.CharField("Độ tuổi", max_length=10, choices=AGE_GROUPS)
    is_active = models.BooleanField("Đang hoạt động", default=True)

    class Meta:
        ordering = ["campus__order", "name"]
        verbose_name = "Lớp"
        verbose_name_plural = "Lớp"
        constraints = [
            models.UniqueConstraint(fields=["name", "school_year", "campus"], name="uniq_class_per_year_campus"),
        ]

    def __str__(self):
        return f"{self.name} ({self.campus}, {self.school_year})"


class Catalog(models.Model):
    """Danh mục chuyên môn cấu hình được: loại văn bản, lĩnh vực, cơ quan ban hành..."""

    KINDS = [
        ("doc_type", "Loại văn bản"),
        ("field", "Lĩnh vực"),
        ("issuer", "Cơ quan ban hành"),
    ]
    kind = models.CharField("Loại danh mục", max_length=20, choices=KINDS, db_index=True)
    name = models.CharField("Tên", max_length=200)
    order = models.PositiveIntegerField("Thứ tự", default=0)
    is_active = models.BooleanField("Đang sử dụng", default=True)

    class Meta:
        ordering = ["kind", "order", "name"]
        verbose_name = "Danh mục chuyên môn"
        verbose_name_plural = "Danh mục chuyên môn"
        constraints = [models.UniqueConstraint(fields=["kind", "name"], name="uniq_catalog_kind_name")]

    def __str__(self):
        return self.name
