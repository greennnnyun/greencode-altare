"""导航栏「我的收藏」数字徽标。"""
from .models import Favorite


def favorite_counter(request):
    if not request.user.is_authenticated:
        return {'nav_favorites': 0}
    return {
        'nav_favorites': Favorite.objects.filter(
            user=request.user, listing__is_deleted=False
        ).count()
    }
