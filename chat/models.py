from django.conf import settings
from django.db import models


class Conversation(models.Model):
    listing = models.ForeignKey(
        'listings.Listing', on_delete=models.CASCADE, related_name='conversations', verbose_name='房源'
    )
    tenant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tenant_conversations', verbose_name='租客'
    )
    landlord = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='landlord_conversations', verbose_name='房东'
    )
    tenant_last_read_id = models.BigIntegerField('租客已读游标', default=0)
    landlord_last_read_id = models.BigIntegerField('房东已读游标', default=0)
    tenant_cleared_id = models.BigIntegerField('租客清空游标', default=0)
    landlord_cleared_id = models.BigIntegerField('房东清空游标', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '会话'
        verbose_name_plural = '会话'
        unique_together = [('listing', 'tenant', 'landlord')]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.tenant.email} ↔ {self.landlord.email} · {self.listing.title}'

    def other_user(self, user):
        return self.landlord if user.id == self.tenant_id else self.tenant

    def read_cursor(self, user):
        return self.tenant_last_read_id if user.id == self.tenant_id else self.landlord_last_read_id

    def read_field(self, user):
        return 'tenant_last_read_id' if user.id == self.tenant_id else 'landlord_last_read_id'

    def cleared_cursor(self, user):
        return self.tenant_cleared_id if user.id == self.tenant_id else self.landlord_cleared_id

    def cleared_field(self, user):
        return 'tenant_cleared_id' if user.id == self.tenant_id else 'landlord_cleared_id'

    def unread_for(self, user):
        cursor = max(self.read_cursor(user), self.cleared_cursor(user))
        return self.messages.exclude(sender=user).filter(id__gt=cursor).count()

    def visible_messages(self, user):
        """该用户能看到的消息：清空游标之后的部分。"""
        return self.messages.filter(id__gt=self.cleared_cursor(user))

    def last_message(self, user=None):
        queryset = self.messages.all() if user is None else self.visible_messages(user)
        return queryset.order_by('-id').first()

    def has_visible_content(self, user):
        """清空过且之后没有新消息的会话，从该用户的列表里消失。"""
        return self.cleared_cursor(user) == 0 or self.visible_messages(user).exists()


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='messages', verbose_name='会话'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages', verbose_name='发送者'
    )
    content = models.TextField('内容', max_length=2000)
    created_at = models.DateTimeField('发送时间', auto_now_add=True)

    class Meta:
        verbose_name = '消息'
        verbose_name_plural = '消息'
        ordering = ['id']
        indexes = [models.Index(fields=['conversation', 'id'])]

    def __str__(self):
        return f'{self.sender.email}: {self.content[:30]}'
