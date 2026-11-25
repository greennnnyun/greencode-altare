from django.contrib import admin

from .models import Viewing


@admin.register(Viewing)
class ViewingAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'phone', 'listing', 'visit_date', 'status', 'created_at')
    list_filter = ('status', 'visit_date')
    search_fields = ('name', 'phone', 'listing__title', 'user__email')
    readonly_fields = ('created_at',)
