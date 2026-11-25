from django.contrib import admin

from .models import Favorite, Listing


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'owner', 'district', 'house_type', 'rent', 'status', 'is_deleted', 'created_at')
    list_filter = ('status', 'city', 'district', 'house_type', 'is_deleted')
    search_fields = ('title', 'address', 'owner__email')
    readonly_fields = ('created_at',)


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'listing', 'created_at')
    search_fields = ('user__email', 'listing__title')
