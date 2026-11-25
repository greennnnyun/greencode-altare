from django.conf import settings
from django.db import models

HOUSE_TYPES = [
    ('studio', '单间'),
    ('one', '一室一厅'),
    ('two', '两室一厅'),
    ('three', '三室两厅'),
]

PAYMENT_CHOICES = [
    ('y1m1', '押一付一'),
    ('y1m3', '押一付三'),
    ('y1m6', '押一付六'),
]

PAYMENT_MONTHS = {
    'y1m1': 1,
    'y1m3': 3,
    'y1m6': 6,
}

AMENITIES = [
    '独立卫浴',
    '空调',
    '洗衣机',
    '冰箱',
    '衣柜',
    '宽带',
    '阳台',
    '地暖',
    '电梯',
    '厨房',
    '书桌',
    '沙发',
    '智能门锁',
    '停车位',
]

ORIENTATIONS = [
    ('南', '南'),
    ('北', '北'),
    ('南北', '南北通透'),
    ('东', '东'),
    ('西', '西'),
    ('东南', '东南'),
    ('西南', '西南'),
]


class Region(models.Model):
    """全国行政区划：省 / 市 / 区县三级，数据由 seed_divisions 从 data/china_divisions.json 导入。"""

    LEVEL_PROVINCE = 1
    LEVEL_CITY = 2
    LEVEL_DISTRICT = 3
    LEVEL_CHOICES = [
        (LEVEL_PROVINCE, '省级'),
        (LEVEL_CITY, '地级'),
        (LEVEL_DISTRICT, '区县'),
    ]

    code = models.CharField('行政区划代码', max_length=12, unique=True)
    name = models.CharField('名称', max_length=80)
    level = models.PositiveSmallIntegerField('层级', choices=LEVEL_CHOICES)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='children',
        verbose_name='上级',
    )

    class Meta:
        verbose_name = '行政区划'
        verbose_name_plural = '行政区划'
        ordering = ['code']
        indexes = [models.Index(fields=['level', 'parent'], name='region_level_parent_idx')]

    def __str__(self):
        return self.name

    @property
    def full_name(self):
        if self.level == self.LEVEL_DISTRICT and self.parent_id:
            return f'{self.parent.name} · {self.name}'
        return self.name


class Listing(models.Model):
    STATUS_LISTED = 'listed'
    STATUS_OFF = 'off'
    STATUS_RENTED = 'rented'
    STATUS_CHOICES = [
        (STATUS_LISTED, '上架中'),
        (STATUS_OFF, '已下架'),
        (STATUS_RENTED, '已租出'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='listings', verbose_name='房东'
    )
    title = models.CharField('房源名称', max_length=80)
    province = models.ForeignKey(
        Region,
        on_delete=models.PROTECT,
        related_name='+',
        limit_choices_to={'level': Region.LEVEL_PROVINCE},
        verbose_name='省份',
    )
    city = models.ForeignKey(
        Region,
        on_delete=models.PROTECT,
        related_name='+',
        limit_choices_to={'level': Region.LEVEL_CITY},
        verbose_name='城市',
    )
    district = models.ForeignKey(
        Region,
        on_delete=models.PROTECT,
        related_name='+',
        limit_choices_to={'level': Region.LEVEL_DISTRICT},
        verbose_name='区县',
    )
    address = models.CharField('详细地址', max_length=200)
    house_type = models.CharField('户型', max_length=20, choices=HOUSE_TYPES)
    area = models.PositiveIntegerField('面积（㎡）')
    floor = models.CharField('楼层', max_length=30, help_text='例如 5/18 层')
    orientation = models.CharField('朝向', max_length=10, choices=ORIENTATIONS, default='南')
    rent = models.PositiveIntegerField('月租金（元）')
    payment = models.CharField('付款方式', max_length=10, choices=PAYMENT_CHOICES, default='y1m3')
    amenities = models.JSONField('设施', default=list, blank=True)
    images = models.JSONField('图片', default=list, blank=True)
    description = models.TextField('房源描述')
    status = models.CharField('状态', max_length=10, choices=STATUS_CHOICES, default=STATUS_LISTED)
    is_deleted = models.BooleanField('已删除', default=False)
    created_at = models.DateTimeField('发布时间', auto_now_add=True)

    class Meta:
        verbose_name = '房源'
        verbose_name_plural = '房源'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'is_deleted', 'city', 'district'], name='listing_status_city_dist_idx'),
            models.Index(fields=['status', 'rent']),
        ]

    def __str__(self):
        return self.title

    @property
    def cover_image(self):
        return self.images[0] if self.images else ''

    @property
    def gallery_images(self):
        return list(self.images or [])

    @property
    def amenities_preview(self):
        return list(self.amenities or [])[:4]

    @property
    def amenities_extra(self):
        return max(0, len(self.amenities or []) - 4)

    @property
    def payment_months(self):
        return PAYMENT_MONTHS.get(self.payment, 3)

    @property
    def payment_label(self):
        return dict(PAYMENT_CHOICES).get(self.payment, self.payment)

    @property
    def first_payment_estimate(self):
        return self.rent * (1 + self.payment_months)

    @property
    def house_type_label(self):
        return dict(HOUSE_TYPES).get(self.house_type, self.house_type)

    @property
    def region_display(self):
        """统一展示口径：『上海市 · 徐汇区』。"""
        return f'{self.city.name} · {self.district.name}'

    @property
    def status_label(self):
        return self.get_status_display()

    @property
    def status_badge_class(self):
        return {
            self.STATUS_LISTED: 'badge-success',
            self.STATUS_OFF: 'badge-ghost',
            self.STATUS_RENTED: 'badge-error',
        }.get(self.status, 'badge-ghost')

    @property
    def is_listed(self):
        return self.status == self.STATUS_LISTED and not self.is_deleted


class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favorites', verbose_name='用户'
    )
    listing = models.ForeignKey(
        Listing, on_delete=models.CASCADE, related_name='favorites', verbose_name='房源'
    )
    created_at = models.DateTimeField('收藏时间', auto_now_add=True)

    class Meta:
        verbose_name = '收藏'
        verbose_name_plural = '收藏'
        unique_together = [('user', 'listing')]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.email} ♥ {self.listing.title}'
