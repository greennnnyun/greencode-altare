"""导入全国行政区划数据（省/市/区三级）。

用法：python manage.py seed_divisions
幂等：重复执行只更新变化行，不会重复插入。
"""
from django.core.management.base import BaseCommand

from listings.divisions import import_divisions
from listings.models import Region


class Command(BaseCommand):
    help = '从 data/china_divisions.json 导入全国省/市/区行政区划（幂等）'

    def handle(self, *args, **options):
        created, updated, total = import_divisions(Region)
        self.stdout.write(
            self.style.SUCCESS(
                f'行政区划导入完成：新增 {created} 条，更新 {updated} 条，共 {total} 条'
                f'（省 {Region.objects.filter(level=1).count()} / '
                f'市 {Region.objects.filter(level=2).count()} / '
                f'区县 {Region.objects.filter(level=3).count()}）'
            )
        )
