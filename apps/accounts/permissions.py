"""
Ma trận phân quyền theo vai trò.

- Vai trò (ROLE_*) gắn với từng tài khoản.
- Mỗi chức năng (MODULES) có các thao tác (ACTIONS) được phép.
- Giá trị mặc định nằm trong DEFAULT_MATRIX; được nạp vào bảng RolePermission
  sau migrate và có thể chỉnh sửa tại /quan-tri/phan-quyen/ (trừ vai trò Quản trị
  hệ thống luôn có toàn quyền).
- Quyền luôn được kiểm tra ở phía máy chủ qua has_perm() / require_perm.
"""

ROLE_ADMIN = "quan_tri"
ROLE_PRINCIPAL = "hieu_truong"
ROLE_VICE = "pho_hieu_truong"
ROLE_OFFICE = "van_phong"
ROLE_GROUP_LEADER = "to_truong"
ROLE_TEACHER = "giao_vien"
ROLE_STAFF = "nhan_vien"

ROLE_CHOICES = [
    (ROLE_ADMIN, "Quản trị hệ thống"),
    (ROLE_PRINCIPAL, "Hiệu trưởng"),
    (ROLE_VICE, "Phó Hiệu trưởng"),
    (ROLE_OFFICE, "Nhân viên văn phòng"),
    (ROLE_GROUP_LEADER, "Tổ trưởng chuyên môn"),
    (ROLE_TEACHER, "Giáo viên"),
    (ROLE_STAFF, "Nhân viên khác"),
]
ROLE_LABELS = dict(ROLE_CHOICES)

# Vai trò được xem dữ liệu toàn trường (không giới hạn theo điểm trường/tổ/lớp).
FULL_SCOPE_ROLES = {ROLE_ADMIN, ROLE_PRINCIPAL, ROLE_VICE, ROLE_OFFICE}
# Vai trò quản lý: được giao việc cho toàn trường, xem văn bản mức "lãnh đạo".
MANAGER_ROLES = {ROLE_ADMIN, ROLE_PRINCIPAL, ROLE_VICE}

ACTIONS = [
    ("view", "Xem"),
    ("create", "Tạo"),
    ("edit", "Sửa"),
    ("delete", "Xóa"),
    ("approve", "Duyệt"),
    ("publish", "Xuất bản"),
    ("download", "Tải xuống"),
    ("export", "Xuất dữ liệu"),
    ("use", "Sử dụng"),
]
ACTION_LABELS = dict(ACTIONS)

# module: (nhãn, các thao tác áp dụng)
MODULES = {
    "news": ("Tin tức", ["view", "create", "edit", "delete", "approve", "publish"]),
    "announcement": ("Thông báo", ["view", "create", "edit", "delete", "approve", "publish"]),
    "page": ("Trang giới thiệu", ["view", "create", "edit", "delete", "publish"]),
    "album": ("Thư viện ảnh/video", ["view", "create", "edit", "delete", "approve", "publish"]),
    "public_document": ("Tài liệu tải xuống công khai", ["view", "create", "edit", "delete", "publish"]),
    "disclosure": ("Công khai giáo dục", ["view", "create", "edit", "delete", "approve", "publish"]),
    "staff_profile": ("Đội ngũ (hiển thị công khai)", ["view", "create", "edit", "delete"]),
    "official_doc": ("Quản lý văn bản", ["view", "create", "edit", "delete", "download", "export"]),
    "plan": ("Kế hoạch giáo dục", ["view", "create", "edit", "delete", "approve", "download", "export"]),
    "task": ("Nhiệm vụ", ["view", "create", "edit", "delete", "approve", "export"]),
    "evidence": ("Minh chứng", ["view", "create", "edit", "delete", "download", "export"]),
    "report": ("Báo cáo, thống kê", ["view", "export"]),
    "user": ("Tài khoản người dùng", ["view", "create", "edit", "delete"]),
    "org": ("Cơ cấu tổ chức, danh mục", ["view", "create", "edit", "delete"]),
    "settings": ("Cấu hình hệ thống", ["view", "edit"]),
    "audit": ("Nhật ký hệ thống", ["view", "export"]),
    "contact": ("Liên hệ từ phụ huynh", ["view", "delete"]),
    "ai": ("AI hỗ trợ", ["use"]),
}

ALL = "__all__"

DEFAULT_MATRIX = {
    ROLE_ADMIN: ALL,
    ROLE_PRINCIPAL: {m: [a for a in acts if not (m == "user" and a == "delete")] for m, (_, acts) in MODULES.items()},
    ROLE_VICE: {
        "news": ALL,
        "announcement": ALL,
        "page": ALL,
        "album": ALL,
        "public_document": ALL,
        "disclosure": ["view", "create", "edit", "approve"],
        "staff_profile": ALL,
        "official_doc": ["view", "create", "edit", "download", "export"],
        "plan": ALL,
        "task": ALL,
        "evidence": ALL,
        "report": ALL,
        "user": ["view"],
        "org": ["view"],
        "settings": ["view"],
        "contact": ["view"],
        "ai": ALL,
    },
    ROLE_OFFICE: {
        "news": ["view", "create", "edit"],
        "announcement": ["view", "create", "edit"],
        "page": ["view", "create", "edit"],
        "album": ["view", "create", "edit"],
        "public_document": ALL,
        "disclosure": ["view", "create", "edit"],
        "staff_profile": ALL,
        "official_doc": ALL,
        "plan": ["view", "download"],
        "task": ["view", "edit"],
        "evidence": ["view", "create", "edit", "download", "export"],
        "report": ["view"],
        "user": ["view"],
        "org": ["view", "create", "edit"],
        "contact": ALL,
        "ai": ALL,
    },
    ROLE_GROUP_LEADER: {
        "news": ["view", "create", "edit"],
        "announcement": ["view"],
        "album": ["view", "create", "edit"],
        "official_doc": ["view", "download"],
        "plan": ["view", "create", "edit", "approve", "download", "export"],
        "task": ["view", "create", "edit", "approve"],
        "evidence": ["view", "create", "edit", "download"],
        "report": ["view"],
        "org": ["view"],
        "ai": ALL,
    },
    ROLE_TEACHER: {
        "news": ["view", "create", "edit"],
        "album": ["view", "create", "edit"],
        "official_doc": ["view", "download"],
        "plan": ["view", "create", "edit", "download"],
        "task": ["view", "edit"],
        "evidence": ["view", "create", "edit", "download"],
        "ai": ALL,
    },
    ROLE_STAFF: {
        "news": ["view"],
        "official_doc": ["view", "download"],
        "task": ["view", "edit"],
        "evidence": ["view"],
    },
}


def default_allowed(role, module, action):
    spec = DEFAULT_MATRIX.get(role, {})
    if spec == ALL:
        return True
    acts = spec.get(module, [])
    if acts == ALL:
        return action in MODULES[module][1]
    return action in acts


def iter_matrix_keys():
    for role, _ in ROLE_CHOICES:
        for module, (_, acts) in MODULES.items():
            for action in acts:
                yield role, module, action


def has_perm(user, module, action):
    """Kiểm tra quyền theo ma trận. Kết quả được lưu đệm trên đối tượng user cho mỗi request."""
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser or user.role == ROLE_ADMIN:
        return True
    cache = getattr(user, "_perm_cache", None)
    if cache is None:
        from .models import RolePermission

        cache = set(RolePermission.objects.filter(role=user.role, allowed=True).values_list("module", "action"))
        user._perm_cache = cache
    return (module, action) in cache


def has_full_scope(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.role in FULL_SCOPE_ROLES))


def is_manager(user):
    return bool(user and user.is_authenticated and (user.is_superuser or user.role in MANAGER_ROLES))


def is_last_active_admin(user):
    """True nếu `user` là tài khoản Quản trị hệ thống đang hoạt động duy nhất (không được khóa/xóa/hạ quyền)."""
    from django.db.models import Q

    from .models import User

    if not user.pk or not (user.is_superuser or user.role == ROLE_ADMIN) or not user.is_active:
        return False
    others = User.objects.filter(Q(role=ROLE_ADMIN) | Q(is_superuser=True), is_active=True).exclude(pk=user.pk)
    return not others.exists()


def effective_permissions(user):
    """Danh sách (nhãn chức năng, [nhãn thao tác]) mà người dùng đang được phép — để hiển thị."""
    result = []
    for module, (label, acts) in MODULES.items():
        allowed = [ACTION_LABELS[a] for a in acts if has_perm(user, module, a)]
        if allowed:
            result.append((label, allowed))
    return result
