import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from .storage import PrivateMediaStorage, avatar_upload_to, id_card_upload_to


class User(AbstractUser):
    ROLE_TENANT = 'tenant'
    ROLE_LANDLORD = 'landlord'
    ROLE_CHOICES = [
        (ROLE_TENANT, '租客'),
        (ROLE_LANDLORD, '房东'),
    ]

    role = models.CharField('身份', max_length=10, choices=ROLE_CHOICES, default=ROLE_TENANT)
    email = models.EmailField('邮箱', unique=True)
    login_failures = models.PositiveSmallIntegerField('连续登录失败次数', default=0)
    locked_until = models.DateTimeField('锁定截止时间', null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '用户'

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)

    @property
    def role_label(self):
        return self.get_role_display()

    @property
    def is_landlord(self):
        return self.role == self.ROLE_LANDLORD

    @property
    def is_tenant(self):
        return self.role == self.ROLE_TENANT

    def __str__(self):
        return self.email


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile', verbose_name='用户'
    )
    nickname = models.CharField('昵称', max_length=40, blank=True)
    phone = models.CharField('手机号', max_length=20, blank=True)
    avatar = models.FileField('头像', upload_to=avatar_upload_to, blank=True)
    id_card_front = models.FileField(
        '身份证正面', upload_to=id_card_upload_to, storage=PrivateMediaStorage(), blank=True
    )
    id_card_back = models.FileField(
        '身份证反面', upload_to=id_card_upload_to, storage=PrivateMediaStorage(), blank=True
    )
    verified = models.BooleanField('实名已认证', default=False)

    class Meta:
        verbose_name = '个人资料'
        verbose_name_plural = '个人资料'

    def save(self, *args, **kwargs):
        self.verified = bool(self.id_card_front and self.id_card_back)
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        return self.nickname or self.user.get_full_name() or self.user.email.split('@')[0]

    def __str__(self):
        return f'{self.user.email} 的资料'


class EmailOTP(models.Model):
    PURPOSE_SIGNUP = 'signup'
    PURPOSE_RESET = 'reset_password'
    PURPOSE_CHOICES = [
        (PURPOSE_SIGNUP, '注册激活'),
        (PURPOSE_RESET, '重置密码'),
    ]

    email = models.EmailField('邮箱', db_index=True)
    code = models.CharField('验证码', max_length=6)
    purpose = models.CharField('用途', max_length=16, choices=PURPOSE_CHOICES)
    expires_at = models.DateTimeField('过期时间')
    used = models.BooleanField('已使用', default=False)
    attempts = models.PositiveSmallIntegerField('错误次数', default=0)
    request_ip = models.GenericIPAddressField('请求 IP', null=True, blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '邮箱验证码'
        verbose_name_plural = '邮箱验证码'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.email} {self.purpose} {self.code}'
