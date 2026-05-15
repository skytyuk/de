from django.apps import AppConfig


class RoleUserConfig(AppConfig):
    name = 'role_user'

    def ready(self):
        import role_user.signals  # noqa: F401
