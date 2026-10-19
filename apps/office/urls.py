from django.urls import path

from . import views as v

app_name = "office"


def crud(prefix, slug, list_v, create_v, edit_v, delete_v, detail_v=None):
    pats = [
        path(f"{slug}/", list_v.as_view(), name=f"{prefix}_list"),
        path(f"{slug}/them/", create_v.as_view(), name=f"{prefix}_create"),
        path(f"{slug}/<int:pk>/sua/", edit_v.as_view(), name=f"{prefix}_edit"),
        path(f"{slug}/<int:pk>/xoa/", delete_v.as_view(), name=f"{prefix}_delete"),
    ]
    if detail_v:
        pats.append(path(f"{slug}/<int:pk>/", detail_v.as_view(), name=f"{prefix}_detail"))
    return pats


urlpatterns = [
    *crud("doc", "van-ban", v.DocList, v.DocCreate, v.DocUpdate, v.DocDelete, v.DocDetail),
    path("van-ban/<int:pk>/tai-xuong/", v.doc_download, name="doc_download"),
    path("van-ban/xuat-excel/", v.doc_export, name="doc_export"),
    *crud("plan", "ke-hoach", v.PlanList, v.PlanCreate, v.PlanUpdate, v.PlanDelete, v.PlanDetail),
    path("ke-hoach/<int:pk>/chuyen/<slug:name>/", v.plan_transition, name="plan_transition"),
    path("ke-hoach/<int:pk>/gop-y/", v.plan_comment, name="plan_comment"),
    path("ke-hoach/<int:pk>/tai-xuong/", v.plan_download, name="plan_download"),
    path("ke-hoach/<int:pk>/tai-xuong/v<int:version>/", v.plan_download, name="plan_download_version"),
    path("ke-hoach/<int:pk>/xuat/<slug:fmt>/", v.plan_export, name="plan_export"),
    *crud("template", "mau-xuat-ke-hoach", v.TemplateList, v.TemplateCreate, v.TemplateUpdate, v.TemplateDelete),
    *crud("task", "nhiem-vu", v.TaskList, v.TaskCreate, v.TaskUpdate, v.TaskDelete, v.TaskDetail),
    path("nhiem-vu/<int:pk>/trang-thai/", v.task_status, name="task_status"),
    path("nhiem-vu/<int:pk>/nhan-xet/", v.task_comment, name="task_comment"),
    path("nhiem-vu/<int:pk>/minh-chung/", v.task_attach, name="task_attach"),
    path("nhiem-vu/tep/<int:pk>/", v.task_attachment_download, name="task_attachment"),
    path("nhiem-vu/xuat-excel/", v.task_export, name="task_export"),
    *crud(
        "evcat", "danh-muc-minh-chung", v.EvidenceCategoryList, v.EvidenceCategoryCreate, v.EvidenceCategoryUpdate, v.EvidenceCategoryDelete
    ),
    *crud("evidence", "minh-chung", v.EvidenceList, v.EvidenceCreate, v.EvidenceUpdate, v.EvidenceDelete, v.EvidenceDetail),
    path("minh-chung/<int:pk>/tai-len/", v.evidence_upload, name="evidence_upload"),
    path("minh-chung/<int:pk>/tai-xuong/v<int:version>/", v.evidence_download, name="evidence_download"),
    path("minh-chung/xuat-excel/", v.evidence_export, name="evidence_export"),
]
