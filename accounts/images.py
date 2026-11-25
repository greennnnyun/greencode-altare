import io
import uuid

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_WIDTH = 1600
ALLOWED_FORMATS = {'JPEG', 'PNG', 'WEBP'}


def prepare_image(upload, max_width=MAX_WIDTH):
    """校验 jpg/png/webp、≤5MB，Pillow 二次校验后压缩为宽 ≤1600 的 JPEG，文件名 uuid 化。"""
    if upload.size > MAX_FILE_SIZE:
        raise ValidationError('图片大小不能超过 5MB')
    try:
        upload.seek(0)
        probe = Image.open(upload)
        probe.verify()
        fmt = probe.format
    except (UnidentifiedImageError, OSError, AttributeError):
        raise ValidationError('无法识别的图片文件，请上传 jpg / png / webp')
    if fmt not in ALLOWED_FORMATS:
        raise ValidationError('仅支持 jpg / png / webp 格式')

    upload.seek(0)
    image = Image.open(upload)
    image = ImageOps.exif_transpose(image)
    if image.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', image.size, (255, 255, 255))
        rgba = image.convert('RGBA')
        background.paste(rgba, mask=rgba.split()[-1])
        image = background
    elif image.mode != 'RGB':
        image = image.convert('RGB')

    if image.width > max_width:
        ratio = max_width / image.width
        image = image.resize((max_width, max(1, int(image.height * ratio))), Image.LANCZOS)

    buffer = io.BytesIO()
    image.save(buffer, format='JPEG', quality=82, optimize=True)
    return ContentFile(buffer.getvalue(), name=f'{uuid.uuid4().hex}.jpg')
