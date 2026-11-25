from django.contrib import admin

from .models import RentalApplication


@admin.register(RentalApplication)
class RentalApplicationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'listing', 'status', 'start_date', 'months', 'first_payment', 'signed_at')
    list_filter = ('status',)
    search_fields = ('user__email', 'listing__title')
    readonly_fields = ('created_at', 'signed_at')
