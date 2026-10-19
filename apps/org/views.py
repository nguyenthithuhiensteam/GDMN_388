"""CRUD cơ cấu tổ chức: năm học, điểm trường, tổ chuyên môn, lớp, danh mục chuyên môn."""
from django.http import Http404
from django.urls import reverse

from apps.core.crud import AdminCreateView, AdminDeleteView, AdminListView, AdminUpdateView


from . import forms
from .models import Campus, Catalog, ProfessionalGroup, SchoolClass, SchoolYear

ORG_ENTITIES = {
    "nam-hoc": (SchoolYear, forms.SchoolYearForm, "Năm học",
                [("name", "Năm học"), ("start_date", "Bắt đầu"), ("end_date", "Kết thúc"), ("is_current", "Hiện hành")],
                ["name"], []),
    "diem-truong": (Campus, forms.CampusForm, "Điểm trường",
                    [("name", "Tên"), ("address", "Địa chỉ"), ("is_main", "Chính"), ("is_active", "Hoạt động")],
                    ["name", "address"], []),
    "to-chuyen-mon": (ProfessionalGroup, forms.GroupForm, "Tổ chuyên môn",
                      [("name", "Tên tổ"), ("code", "Mã"), ("is_active", "Hoạt động")], ["name"], []),
    "lop": (SchoolClass, forms.SchoolClassForm, "Lớp",
            [("name", "Lớp"), ("age_group", "Độ tuổi"), ("campus", "Điểm trường"), ("group", "Tổ"), ("school_year", "Năm học")],
            ["name"], ["school_year", "campus", "age_group"]),
    "danh-muc": (Catalog, forms.CatalogForm, "Danh mục chuyên môn",
                 [("kind", "Loại"), ("name", "Tên"), ("order", "Thứ tự"), ("is_active", "Đang dùng")],
                 ["name"], ["kind"]),
}


class _OrgMixin:
    module = "org"
    owner_field = "none"

    def dispatch(self, request, *args, **kwargs):
        self.entity = kwargs.pop("entity")
        if self.entity not in ORG_ENTITIES:
            raise Http404
        (self.model, self.form_class, self.page_title, self.columns,
         self.search_fields, self.filter_fields) = ORG_ENTITIES[self.entity]
        return super().dispatch(request, *args, **kwargs)

    def can_modify(self, obj):
        return True  # quyền org.* đã được kiểm tra ở mức chức năng

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["entity"] = self.entity
        ctx["org_entities"] = [(k, v[2]) for k, v in ORG_ENTITIES.items()]
        return ctx

    def get_list_url(self):
        return reverse("org:list", kwargs={"entity": self.entity})

    def get_success_url(self):
        return self.get_list_url()


class OrgList(_OrgMixin, AdminListView):
    url_prefix = "org"


class OrgCreate(_OrgMixin, AdminCreateView):
    url_prefix = "org"


class OrgUpdate(_OrgMixin, AdminUpdateView):
    url_prefix = "org"


class OrgDelete(_OrgMixin, AdminDeleteView):
    url_prefix = "org"
