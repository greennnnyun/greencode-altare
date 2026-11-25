import uuid

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateMediaStorage(FileSystemStorage):
    """身份证等敏感文件存储：不产生 MEDIA_URL，只能经鉴权视图读取。"""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('location', settings.PRIVATE_MEDIA_ROOT)
        kwargs.setdefault('base_url', None)
        super().__init__(*args, **kwargs)


def id_card_upload_to(instance, filename):
    return f'id_cards/{uuid.uuid4().hex}.jpg'


def avatar_upload_to(instance, filename):
    return f'avatars/{uuid.uuid4().hex}.jpg'
