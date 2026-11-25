from django.contrib import admin

from .models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'listing', 'tenant', 'landlord', 'tenant_last_read_id', 'landlord_last_read_id')
    search_fields = ('listing__title', 'tenant__email', 'landlord__email')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'content', 'created_at')
    search_fields = ('content', 'sender__email')
    readonly_fields = ('created_at',)
