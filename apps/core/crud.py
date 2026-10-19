"""
Khung CRUD dùng chung cho khu vực quản trị. Mọi view đều:
- yêu cầu đăng nhập và quyền (module, action) theo ma trận;
- kiểm tra quyền theo đối tượng khi sửa/xóa (người tạo, cùng tổ, hoặc phạm vi toàn trường);
- ghi nhật ký tạo/sửa/xóa.
"""
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import ProtectedError, Q
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.accounts.permissions import has_perm

from .audit import diff_instances, log_action, snapshot
from .permissions_mixins import ModulePermissionMixin, owns_or_scoped


class AdminContextMixin:
    page_title = ""
    url_prefix = ""  # tiền tố tên URL, ví dụ "content:news" → content:news_list, _create, _edit, _delete, _detail
    owner_field = "created_by"

    def url_name(self, suffix):
        return f"{self.url_prefix}_{suffix}"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx.update(
            page_title=self.page_title,
            module=self.module,
            url_prefix=self.url_prefix,
            can_create=has_perm(user, self.module, "create"),
            can_edit=has_perm(user, self.module, "edit"),
            can_delete=has_perm(user, self.module, "delete"),
            list_url=self.get_list_url(),
        )
        return ctx

    def get_list_url(self):
        return reverse(self.url_name("list"))

    def can_modify(self, obj):
        return owns_or_scoped(self.request.user, obj, self.owner_field)


class AdminListView(AdminContextMixin, ModulePermissionMixin, ListView):
    action = "view"
    template_name = "admin/generic_list.html"
    paginate_by = 20
    columns = []  # [(thuộc tính, nhãn)]
    search_fields = []
    filter_fields = []  # tên trường có choices hoặc FK
    has_detail = False

    def scope_queryset(self, qs):
        return qs

    def get_queryset(self):
        qs = self.scope_queryset(super().get_queryset())
        q = self.request.GET.get("q", "").strip()
        if q and self.search_fields:
            cond = Q()
            for f in self.search_fields:
                cond |= Q(**{f"{f}__icontains": q})
            qs = qs.filter(cond)
        for f in self.filter_fields:
            val = self.request.GET.get(f)
            if val:
                qs = qs.filter(**{f: val})
        return qs

    def get_filters(self):
        model = self.model
        result = []
        for name in self.filter_fields:
            field = model._meta.get_field(name)
            if field.choices:
                options = [(str(k), v) for k, v in field.choices]
            elif field.is_relation:
                options = [(str(o.pk), str(o)) for o in field.related_model.objects.all()[:200]]
            else:
                continue
            result.append({"name": name, "label": field.verbose_name, "options": options,
                           "value": self.request.GET.get(name, "")})
        return result

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx.update(
            columns=self.columns,
            filters=self.get_filters(),
            q=self.request.GET.get("q", ""),
            has_search=bool(self.search_fields),
            querystring=params.urlencode(),
            has_detail=self.has_detail,
        )
        return ctx


class AdminFormMixin(AdminContextMixin):
    template_name = "admin/generic_form.html"
    success_message = "Đã lưu thành công."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return self.get_list_url()

    def form_invalid(self, form):
        messages.error(self.request, "Vui lòng kiểm tra lại các trường được đánh dấu.")
        return super().form_invalid(form)


class AdminCreateView(AdminFormMixin, ModulePermissionMixin, CreateView):
    action = "create"

    def form_valid(self, form):
        obj = form.save(commit=False)
        if hasattr(obj, "created_by_id"):
            obj.created_by = self.request.user
        if hasattr(obj, "updated_by_id"):
            obj.updated_by = self.request.user
        self.before_save(form, obj, created=True)
        obj.save()
        form.save_m2m()
        self.object = obj
        self.after_save(form, obj, created=True)
        log_action(self.request, "create", obj, module=self.module)
        messages.success(self.request, self.success_message)
        return redirect(self.get_success_url())

    def before_save(self, form, obj, created):
        pass

    def after_save(self, form, obj, created):
        pass


class AdminUpdateView(AdminFormMixin, ModulePermissionMixin, UpdateView):
    action = "edit"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not self.can_modify(obj):
            raise PermissionDenied
        self._before = snapshot(obj)
        return obj

    def form_valid(self, form):
        obj = form.save(commit=False)
        if hasattr(obj, "updated_by_id"):
            obj.updated_by = self.request.user
        self.before_save(form, obj, created=False)
        obj.save()
        form.save_m2m()
        self.object = obj
        self.after_save(form, obj, created=False)
        log_action(self.request, "update", obj, module=self.module, changes=diff_instances(self._before, snapshot(obj)))
        messages.success(self.request, self.success_message)
        return redirect(self.get_success_url())

    def before_save(self, form, obj, created):
        pass

    def after_save(self, form, obj, created):
        pass


class AdminDeleteView(AdminContextMixin, ModulePermissionMixin, DeleteView):
    action = "delete"
    template_name = "admin/confirm_delete.html"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not self.can_modify(obj):
            raise PermissionDenied
        return obj

    def get_success_url(self):
        return self.get_list_url()

    def form_valid(self, form):
        obj = self.get_object()
        repr_, pk = str(obj), obj.pk
        try:
            obj.delete()
        except ProtectedError:
            messages.error(self.request, "Không thể xóa vì đang có dữ liệu liên quan. Hãy ẩn/lưu trữ thay vì xóa.")
            return redirect(self.get_success_url())
        obj.pk = pk
        log_action(self.request, "delete", obj, module=self.module, object_repr=repr_)
        messages.success(self.request, f"Đã xóa: {repr_}")
        return redirect(self.get_success_url())


class AdminDetailView(AdminContextMixin, ModulePermissionMixin, DetailView):
    action = "view"
