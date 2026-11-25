from django.contrib.auth.backends import ModelBackend

from .models import User


class EmailBackend(ModelBackend):
    """仅允许「邮箱 + 密码」登录，邮箱大小写不敏感。"""

    def authenticate(self, request, username=None, password=None, **kwargs):
        email = kwargs.get('email') or username
        if not email or not password:
            return None
        try:
            user = User.objects.get(email=str(email).strip().lower())
        except User.DoesNotExist:
            return None
        if not user.is_active or not user.check_password(password):
            return None
        return user
