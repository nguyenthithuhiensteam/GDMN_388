from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    verbose_name = "Tài khoản và phân quyền"

    def ready(self):
        from . import signals  # noqa: F401
