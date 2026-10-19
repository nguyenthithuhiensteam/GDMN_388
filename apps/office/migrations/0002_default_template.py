from django.db import migrations


def forwards(apps, schema_editor):
    T = apps.get_model("office", "PlanExportTemplate")
    if not T.objects.exists():
        T.objects.create(
            name="Mẫu kế hoạch mặc định",
            header_left="",  # để trống: tự lấy Cơ quan chủ quản + Tên trường từ cấu hình
            header_right="CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\nĐộc lập - Tự do - Hạnh phúc",
            title_prefix="KẾ HOẠCH",
            signature_title="HIỆU TRƯỞNG",
            footer_note="Nơi nhận:\n- Như trên;\n- Lưu: VT.",
            is_default=True,
        )


class Migration(migrations.Migration):
    dependencies = [("office", "0001_initial")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
