import shutil

from django.conf import settings
from django.test import TestCase

from apps.accounts import permissions as P

from .helpers import make_org, make_user


class BaseTestCase(TestCase):
    """Tạo cơ cấu tổ chức và một tài khoản cho mỗi vai trò."""

    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        o = cls.org
        cls.admin = make_user("quantri", P.ROLE_ADMIN)
        cls.principal = make_user("hieutruong", P.ROLE_PRINCIPAL, campus=o["campus"])
        cls.vice = make_user("phohieutruong", P.ROLE_VICE, campus=o["campus"])
        cls.office = make_user("vanphong", P.ROLE_OFFICE, campus=o["campus"])
        cls.leader = make_user("totruong", P.ROLE_GROUP_LEADER, campus=o["campus"], group=o["g1"])
        cls.teacher = make_user("giaovien", P.ROLE_TEACHER, campus=o["campus"], group=o["g1"])
        cls.teacher.classes.add(o["cls"])
        cls.teacher2 = make_user("giaovien2", P.ROLE_TEACHER, campus=o["campus2"], group=o["g2"])
        cls.staff = make_user("nhanvien", P.ROLE_STAFF, campus=o["campus"])

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        for path in (settings.MEDIA_ROOT, settings.PROTECTED_MEDIA_ROOT, settings.BACKUP_DIR):
            shutil.rmtree(path, ignore_errors=True)

    def setUp(self):
        super().setUp()
        from django.core.cache import cache

        cache.clear()

    def login(self, user):
        self.client.force_login(user)
        return self.client
