from apps.core.forms_base import BaseModelForm

from .models import Campus, Catalog, ProfessionalGroup, SchoolClass, SchoolYear


class SchoolYearForm(BaseModelForm):
    class Meta:
        model = SchoolYear
        fields = ["name", "start_date", "end_date", "is_current"]


class CampusForm(BaseModelForm):
    class Meta:
        model = Campus
        fields = ["name", "code", "address", "phone", "is_main", "description", "order", "is_active"]


class GroupForm(BaseModelForm):
    class Meta:
        model = ProfessionalGroup
        fields = ["name", "code", "description", "is_active"]


class SchoolClassForm(BaseModelForm):
    class Meta:
        model = SchoolClass
        fields = ["name", "school_year", "campus", "group", "age_group", "is_active"]


class CatalogForm(BaseModelForm):
    class Meta:
        model = Catalog
        fields = ["kind", "name", "order", "is_active"]
