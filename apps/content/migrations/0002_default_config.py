"""Cấu hình mặc định (không phải dữ liệu mẫu): danh mục tin, mục công khai.
Các mục công khai là khung gợi ý; nhà trường cần rà soát, chỉnh sửa theo quy định hiện hành."""
from django.db import migrations

CATEGORIES = [("Hoạt động nhà trường", "hoat-dong-nha-truong"), ("Hoạt động chuyên môn", "hoat-dong-chuyen-mon"),
              ("Phụ huynh cần biết", "phu-huynh-can-biet"), ("Tin tuyển sinh", "tin-tuyen-sinh")]
SECTIONS = [
    "Thông tin chung về cơ sở giáo dục",
    "Điều kiện bảo đảm chất lượng (đội ngũ, cơ sở vật chất)",
    "Kế hoạch và kết quả hoạt động giáo dục",
    "Thu, chi tài chính",
    "Báo cáo thường niên",
]


def forwards(apps, schema_editor):
    Category = apps.get_model("content", "Category")
    Section = apps.get_model("content", "DisclosureSection")
    for i, (name, slug) in enumerate(CATEGORIES):
        Category.objects.get_or_create(slug=slug, defaults={"name": name, "order": i})
    for i, name in enumerate(SECTIONS):
        Section.objects.get_or_create(name=name, defaults={"order": i})


class Migration(migrations.Migration):
    dependencies = [("content", "0001_initial")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
