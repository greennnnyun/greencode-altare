"""生成幂等的本地演示数据：2 个账号 + 12 套房源（4 个城市）+ 本地图片。

前置：先执行 python manage.py seed_divisions 导入全国行政区划。
用法：python manage.py seed
重复执行不会产生重复账号或重复房源（按 owner + title 幂等）。
"""

import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Profile, User
from bookings.models import Viewing
from chat.models import Conversation, Message
from listings.models import Favorite, Listing, Region

LANDLORD_EMAIL = 'landlord@eggshell.cn'
TENANT_EMAIL = 'tenant@eggshell.cn'
DEMO_PASSWORD = 'Eggshell2026'

# 图片循环使用 seed_media 下的本地图片，保证每套至少 3 张
IMAGE_POOL = [f'room-{index:02d}.jpg' for index in range(1, 22)]

LISTINGS = [
    {
        'title': '云栖小筑 · 静安一室',
        'city': '上海市',
        'district': '静安区',
        'address': '南京西路 1218 弄 3 号楼 802 室',
        'house_type': 'one',
        'area': 48,
        'floor': '8/18 层',
        'orientation': '南',
        'rent': 5200,
        'payment': 'y1m3',
        'amenities': ['空调', '洗衣机', '冰箱', '宽带', '电梯', '独立卫浴'],
        'description': (
            '整租一室一厅，步行到静安寺约九分钟，楼下就是便利店与咖啡馆。'
            '房子朝南采光充足，独立卫浴干湿分离，家电齐全可直接拎包入住，'
            '适合通勤稳定的上班族。'
        ),
        'images': ['room-01.jpg', 'room-02.jpg', 'room-03.jpg'],
    },
    {
        'title': '梧桐里 · 徐汇单间',
        'city': '上海市',
        'district': '徐汇区',
        'address': '衡山路 8 号 2 号楼 301 室',
        'house_type': 'studio',
        'area': 26,
        'floor': '3/6 层',
        'orientation': '南',
        'rent': 3200,
        'payment': 'y1m1',
        'amenities': ['空调', '洗衣机', '宽带', '书桌'],
        'description': (
            '位于衡山路老洋房片区的温馨单间，推窗就是梧桐树影。'
            '房间不大但收纳做得很好，配书桌与宽带，步行可达地铁站，'
            '适合刚来上海、希望住得安静又方便的你。'
        ),
        'images': ['room-04.jpg', 'room-05.jpg', 'room-06.jpg'],
    },
    {
        'title': '江畔暖居 · 浦东两室',
        'city': '上海市',
        'district': '浦东新区',
        'address': '世纪大道 100 号 5 号楼 1203 室',
        'house_type': 'two',
        'area': 78,
        'floor': '12/28 层',
        'orientation': '南北',
        'rent': 6000,
        'payment': 'y1m3',
        'amenities': ['空调', '冰箱', '洗衣机', '阳台', '电梯', '厨房'],
        'description': (
            '两室一厅南北通透，客厅带大阳台，能看到黄浦江方向的天空。'
            '厨房可开火，电梯直达，适合两位朋友合租或小家庭，'
            '周边商场与地铁都在十分钟生活圈内。'
        ),
        'images': ['room-07.jpg', 'room-08.jpg', 'room-09.jpg'],
    },
    {
        'title': '暖木一居 · 长宁',
        'city': '上海市',
        'district': '长宁区',
        'address': '愚园路 718 弄 6 号楼 502 室',
        'house_type': 'one',
        'area': 52,
        'floor': '5/7 层',
        'orientation': '东南',
        'rent': 4800,
        'payment': 'y1m1',
        'amenities': ['空调', '冰箱', '衣柜', '宽带', '厨房'],
        'description': (
            '一室一厅小户型，暖木色家具搭配米白墙面，午后阳光会落在客厅地板上。'
            '步行五分钟到地铁站，社区安静，房东自住过，保养得很好，'
            '适合喜欢温馨小家的独立租客。'
        ),
        'images': ['room-10.jpg', 'room-11.jpg', 'room-12.jpg'],
    },
    {
        'title': '青年蛋壳 · 普陀单间',
        'city': '上海市',
        'district': '普陀区',
        'address': '长寿路 468 号 4 号楼 408 室',
        'house_type': 'studio',
        'area': 22,
        'floor': '4/9 层',
        'orientation': '东',
        'rent': 2000,
        'payment': 'y1m1',
        'amenities': ['空调', '宽带', '独立卫浴', '书桌'],
        'description': (
            '青年公寓式单间，独立卫浴、书桌与宽带一应俱全，楼下有共享厨房与洗衣房。'
            '租金友好，适合刚毕业的年轻人，管家每周会做一次公共区域清洁，'
            '入住流程简单省心。'
        ),
        'images': ['room-13.jpg', 'room-14.jpg', 'room-15.jpg'],
    },
    {
        'title': '杨浦朝南两室',
        'city': '上海市',
        'district': '杨浦区',
        'address': '国定路 600 号 7 号楼 602 室',
        'house_type': 'two',
        'area': 86,
        'floor': '6/18 层',
        'orientation': '南',
        'rent': 5600,
        'payment': 'y1m3',
        'amenities': ['空调', '洗衣机', '冰箱', '阳台', '电梯', '沙发'],
        'description': (
            '朝南两室一厅，主卧带飘窗，次卧可做书房。小区绿化好、有电梯与地面停车位，'
            '周边菜场、超市、地铁站都在步行范围内，适合长期稳定租住的小家庭。'
        ),
        'images': ['room-16.jpg', 'room-17.jpg', 'room-18.jpg'],
    },
    {
        'title': '朝阳公园旁 · 北京单间',
        'city': '北京市',
        'district': '朝阳区',
        'address': '朝阳公园南路 8 号院 2 号楼 601 室',
        'house_type': 'studio',
        'area': 28,
        'floor': '6/12 层',
        'orientation': '南',
        'rent': 3400,
        'payment': 'y1m1',
        'amenities': ['空调', '洗衣机', '宽带', '衣柜', '电梯'],
        'description': (
            '紧邻朝阳公园的单间，早上可以去公园跑步，晚上回家很安静。'
            '房间朝南，采光和通风都不错，配独立衣柜与宽带，'
            '地铁 14 号线步行十分钟可达，适合在国贸一带上班的朋友。'
        ),
        'images': ['room-19.jpg', 'room-20.jpg', 'room-21.jpg'],
    },
    {
        'title': '中关村一室一厅 · 海淀',
        'city': '北京市',
        'district': '海淀区',
        'address': '中关村大街 27 号 3 号楼 1102 室',
        'house_type': 'one',
        'area': 45,
        'floor': '11/20 层',
        'orientation': '南',
        'rent': 4500,
        'payment': 'y1m3',
        'amenities': ['空调', '冰箱', '洗衣机', '电梯', '厨房', '智能门锁'],
        'description': (
            '中关村核心区一室一厅，家电齐全，厨房可以简单开火。'
            '小区门禁严格、有电梯，通勤到各大科技公司基本都在半小时内，'
            '适合长期在北京工作的程序员与产品同学。'
        ),
        'images': ['room-01.jpg', 'room-04.jpg', 'room-07.jpg'],
    },
    {
        'title': '西湖边的两室 · 杭州',
        'city': '杭州市',
        'district': '西湖区',
        'address': '文二路 188 号 5 号楼 702 室',
        'house_type': 'two',
        'area': 72,
        'floor': '7/16 层',
        'orientation': '南北',
        'rent': 4200,
        'payment': 'y1m3',
        'amenities': ['空调', '冰箱', '洗衣机', '阳台', '电梯', '厨房'],
        'description': (
            '西湖区成熟社区的两室一厅，南北通透，阳台可以看到小区中央花园。'
            '骑车十五分钟到西湖边，周边菜场与商场齐全，'
            '适合情侣或两位朋友合租，房东可配合办理居住登记。'
        ),
        'images': ['room-10.jpg', 'room-13.jpg', 'room-16.jpg'],
    },
    {
        'title': '滨江单间 · 近地铁 1 号线',
        'city': '杭州市',
        'district': '滨江区',
        'address': '江南大道 588 号 2 号楼 905 室',
        'house_type': 'studio',
        'area': 25,
        'floor': '9/18 层',
        'orientation': '西南',
        'rent': 2200,
        'payment': 'y1m1',
        'amenities': ['空调', '宽带', '独立卫浴', '书桌'],
        'description': (
            '滨江互联网园区附近的单间，独立卫浴、宽带与书桌都有，'
            '楼下便利店与外卖柜齐全，步行八分钟到地铁 1 号线。'
            '租金在滨江算友好，适合刚入职的应届生。'
        ),
        'images': ['room-19.jpg', 'room-02.jpg', 'room-05.jpg'],
    },
    {
        'title': '锦江畔一室 · 成都',
        'city': '成都市',
        'district': '锦江区',
        'address': '东大街 99 号 4 号楼 1802 室',
        'house_type': 'one',
        'area': 42,
        'floor': '18/26 层',
        'orientation': '南',
        'rent': 2800,
        'payment': 'y1m1',
        'amenities': ['空调', '洗衣机', '冰箱', '宽带', '电梯'],
        'description': (
            '锦江区一室一厅，高层视野好，晚上能看到城市灯光。'
            '步行十分钟到春熙路商圈，楼下小吃与茶馆很多，'
            '生活节奏舒服，适合在成都长期生活的年轻人。'
        ),
        'images': ['room-08.jpg', 'room-11.jpg', 'room-14.jpg'],
    },
    {
        'title': '武侯两室 · 成都南门',
        'city': '成都市',
        'district': '武侯区',
        'address': '人民南路四段 66 号 1 号楼 603 室',
        'house_type': 'two',
        'area': 76,
        'floor': '6/11 层',
        'orientation': '南北',
        'rent': 3800,
        'payment': 'y1m3',
        'amenities': ['空调', '洗衣机', '冰箱', '阳台', '厨房', '沙发'],
        'description': (
            '武侯区两室一厅，南北通透，客厅带沙发与阳台，厨房可明火做饭。'
            '小区楼下就是菜市场，公交与地铁都在十分钟内，'
            '房东希望租客作息规律、爱干净，长租可以再谈一点。'
        ),
        'images': ['room-17.jpg', 'room-20.jpg', 'room-03.jpg'],
    },
]


class Command(BaseCommand):
    help = '生成幂等的演示数据（演示账号 + 12 套四城房源 + 本地图片）'

    def handle(self, *args, **options):
        if Region.objects.count() == 0:
            raise CommandError('行政区划尚未导入，请先执行：python manage.py seed_divisions')

        seed_dir = Path(settings.BASE_DIR) / 'seed_media'
        if not seed_dir.exists():
            raise CommandError(f'缺少 seed_media 目录：{seed_dir}')

        missing = sorted({name for item in LISTINGS for name in item['images']} - {
            p.name for p in seed_dir.glob('*.jpg')
        })
        if missing:
            raise CommandError(f'seed_media 缺少图片：{"、".join(missing)}')

        dest_dir = Path(settings.MEDIA_ROOT) / 'listings' / 'seed'
        dest_dir.mkdir(parents=True, exist_ok=True)

        created_listings = 0
        with transaction.atomic():
            landlord = self._ensure_user(
                LANDLORD_EMAIL, '蛋壳房东', User.ROLE_LANDLORD
            )
            tenant = self._ensure_user(
                TENANT_EMAIL, '小蛋壳', User.ROLE_TENANT
            )

            for item in LISTINGS:
                images = [self._copy_image(seed_dir, dest_dir, name) for name in item['images']]
                province, city, district = self._resolve_region(item['city'], item['district'])
                defaults = {
                    'province': province,
                    'city': city,
                    'district': district,
                    'address': item['address'],
                    'house_type': item['house_type'],
                    'area': item['area'],
                    'floor': item['floor'],
                    'orientation': item['orientation'],
                    'rent': item['rent'],
                    'payment': item['payment'],
                    'amenities': item['amenities'],
                    'description': item['description'],
                    'images': images,
                    'status': Listing.STATUS_LISTED,
                    'is_deleted': False,
                }
                listing, created = Listing.objects.get_or_create(
                    owner=landlord, title=item['title'], defaults=defaults
                )
                if not created:
                    for key, value in defaults.items():
                        setattr(listing, key, value)
                    listing.save()
                else:
                    created_listings += 1

            self._ensure_demo_interactions(tenant, landlord)

        self.stdout.write(self.style.SUCCESS('演示数据准备完成'))
        self.stdout.write(f'  房东账号：{landlord.email} / {DEMO_PASSWORD}')
        self.stdout.write(f'  租客账号：{tenant.email} / {DEMO_PASSWORD}')
        self.stdout.write(
            f'  房源：共 {Listing.objects.filter(owner=landlord, is_deleted=False).count()} 套'
            f'（本次新增 {created_listings} 套，覆盖 '
            f'{Listing.objects.filter(owner=landlord, is_deleted=False).values("city").distinct().count()} 个城市）'
        )
        self.stdout.write(f'  图片目录：{dest_dir}')

    def _ensure_demo_interactions(self, tenant, landlord):
        """示例收藏 / 预约 / 会话，全部按业务唯一键幂等。"""
        from datetime import timedelta

        from django.utils import timezone

        first, second = Listing.objects.filter(owner=landlord, is_deleted=False).order_by('pk')[:2]
        if first is None:
            return
        Favorite.objects.get_or_create(user=tenant, listing=first)
        if second is not None:
            Viewing.objects.get_or_create(
                user=tenant,
                listing=second,
                visit_date=timezone.localdate() + timedelta(days=3),
                defaults={'name': '小蛋壳', 'phone': '13800001111', 'note': '周末下午方便看房'},
            )
        conversation, _ = Conversation.objects.get_or_create(
            listing=first, tenant=tenant, landlord=landlord
        )
        if not conversation.messages.exists():
            Message.objects.create(
                conversation=conversation, sender=tenant, content='您好，这套房子周末可以看房吗？'
            )
            Message.objects.create(
                conversation=conversation, sender=landlord, content='可以的，周六下午两点方便吗？'
            )

    def _resolve_region(self, city_name, district_name):
        city = Region.objects.filter(level=Region.LEVEL_CITY, name=city_name).first()
        if city is None:
            raise CommandError(
                f'行政区划缺少城市「{city_name}」，请重新执行 python manage.py seed_divisions'
            )
        district = Region.objects.filter(
            level=Region.LEVEL_DISTRICT, name=district_name, parent=city
        ).first()
        if district is None:
            raise CommandError(
                f'行政区划缺少「{city_name} / {district_name}」，请重新执行 python manage.py seed_divisions'
            )
        return city.parent, city, district

    def _ensure_user(self, email, nickname, role):
        user = User.objects.filter(email=email).first()
        if user is None:
            user = User.objects.create_user(
                username=email, email=email, password=DEMO_PASSWORD, role=role
            )
        else:
            user.role = role
        user.is_active = True
        user.is_staff = False
        user.set_password(DEMO_PASSWORD)
        user.save()

        profile, _ = Profile.objects.get_or_create(user=user)
        if not profile.nickname:
            profile.nickname = nickname
            profile.save(update_fields=['nickname'])
        return user

    def _copy_image(self, seed_dir, dest_dir, name):
        source = seed_dir / name
        target = dest_dir / name
        if not target.exists() or target.stat().st_size != source.stat().st_size:
            shutil.copyfile(source, target)
        return f'listings/seed/{name}'
