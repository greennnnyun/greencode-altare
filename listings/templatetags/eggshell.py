from django.conf import settings
from django.template.defaultfilters import register


@register.filter
def media_url(path):
    if not path:
        return ''
    return f'{settings.MEDIA_URL}{path}'
