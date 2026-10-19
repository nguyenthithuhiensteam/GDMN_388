from django.db import migrations

DEFAULTS = {
    "doc_type": ["Quyết định", "Công văn", "Kế hoạch", "Thông báo", "Báo cáo", "Hướng dẫn", "Tờ trình", "Biên bản", "Khác"],
    "field": ["Chuyên môn", "Tổ chức - nhân sự", "Tài chính", "Cơ sở vật chất", "Y tế - dinh dưỡng - an toàn",
              "Tuyển sinh", "Thi đua - khen thưởng", "Khác"],
}


def forwards(apps, schema_editor):
    Catalog = apps.get_model("org", "Catalog")
    for kind, names in DEFAULTS.items():
        for i, name in enumerate(names):
            Catalog.objects.get_or_create(kind=kind, name=name, defaults={"order": i})


class Migration(migrations.Migration):
    dependencies = [("org", "0001_initial")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
