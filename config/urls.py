from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('listings.urls')),
    path('accounts/', include('accounts.urls')),
    path('bookings/', include('bookings.urls')),
    path('chat/', include('chat.urls')),
    path('contracts/', include('contracts.urls')),
]

# 仅本地演示环境：媒体文件直接由 Django 提供，生产环境请改用对象存储 / 受控网关。
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

admin.site.site_header = '蛋壳栖所 · 运营后台'
admin.site.site_title = '蛋壳栖所运营后台'
admin.site.index_title = '数据管理'
