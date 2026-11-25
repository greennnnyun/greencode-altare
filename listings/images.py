from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage

from accounts.images import prepare_image

MAX_IMAGES = 8


def save_listing_images(files, existing=None):
    """保存房源图片到 MEDIA_ROOT/listings，返回相对路径列表。"""
    existing = list(existing or [])
    files = [f for f in files if f]
    if len(existing) + len(files) > MAX_IMAGES:
        raise ValidationError(f'最多保留 {MAX_IMAGES} 张图片')
    paths = []
    for upload in files:
        content = prepare_image(upload)
        paths.append(default_storage.save(f'listings/{content.name}', content))
    return paths


def delete_listing_image(path):
    if path:
        default_storage.delete(path)
