from django.conf import settings
from django.db import models


class RentalApplication(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_SIGNED = 'signed'
    STATUS_CHOICES = [
        (STATUS_PENDING, '待签署'),
        (STATUS_SIGNED, '已签署'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='applications', verbose_name='申请人'
    )
    listing = models.ForeignKey(
        'listings.Listing', on_delete=models.PROTECT, related_name='applications', verbose_name='房源'
    )
    status = models.CharField('状态', max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    start_date = models.DateField('起租日')
    months = models.PositiveSmallIntegerField('租期（月）', default=12)
    deposit = models.PositiveIntegerField('押金', default=0)
    first_payment = models.PositiveIntegerField('首期应付', default=0)
    signed_at = models.DateTimeField('签署时间', null=True, blank=True)
    created_at = models.DateTimeField('申请时间', auto_now_add=True)

    class Meta:
        verbose_name = '租房申请'
        verbose_name_plural = '租房申请'
        unique_together = [('user', 'listing')]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.email} 申请 {self.listing.title}（{self.get_status_display()}）'

    @property
    def status_label(self):
        return self.get_status_display()

    @property
    def status_badge_class(self):
        return 'badge-success' if self.status == self.STATUS_SIGNED else 'badge-warning'
