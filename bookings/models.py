from django.conf import settings
from django.db import models


class Viewing(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING, '待确认'),
        (STATUS_CONFIRMED, '已确认'),
        (STATUS_COMPLETED, '已完成'),
        (STATUS_CANCELLED, '已取消'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='viewings', verbose_name='租客'
    )
    listing = models.ForeignKey(
        'listings.Listing', on_delete=models.CASCADE, related_name='viewings', verbose_name='房源'
    )
    name = models.CharField('联系人', max_length=40)
    phone = models.CharField('手机号', max_length=11)
    visit_date = models.DateField('期望看房日期')
    note = models.CharField('备注', max_length=200, blank=True)
    status = models.CharField('状态', max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField('提交时间', auto_now_add=True)

    class Meta:
        verbose_name = '预约看房'
        verbose_name_plural = '预约看房'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['listing', 'status']), models.Index(fields=['user', 'status'])]

    def __str__(self):
        return f'{self.user.email} → {self.listing.title}（{self.get_status_display()}）'

    @property
    def status_badge_class(self):
        return {
            self.STATUS_PENDING: 'badge-warning',
            self.STATUS_CONFIRMED: 'badge-info',
            self.STATUS_COMPLETED: 'badge-success',
            self.STATUS_CANCELLED: 'badge-ghost',
        }.get(self.status, 'badge-ghost')

    @property
    def can_cancel(self):
        return self.status in {self.STATUS_PENDING, self.STATUS_CONFIRMED}
