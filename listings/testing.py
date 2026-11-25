"""测试用的房源构造辅助（复用 data/china_divisions.json 导入的真实行政区划）。"""
from listings.models import Listing

# 区县名 → (省 code, 市 code, 区 code)，与 data/china_divisions.json 保持一致
DISTRICT_CODES = {
    '徐汇区': ('31', '3101', '310104'),
    '静安区': ('31', '3101', '310106'),
    '黄浦区': ('31', '3101', '310101'),
    '长宁区': ('31', '3101', '310105'),
    '普陀区': ('31', '3101', '310107'),
    '浦东新区': ('31', '3101', '310115'),
    '杨浦区': ('31', '3101', '310110'),
    '朝阳区': ('11', '1101', '110105'),
    '西湖区': ('33', '3301', '330106'),
}


def make_listing(owner, district='徐汇区', **overrides):
    from listings.models import Region

    province_code, city_code, district_code = DISTRICT_CODES[district]
    data = {
        'owner': owner,
        'title': f'测试房源 · {district}',
        'province': Region.objects.get(code=province_code),
        'city': Region.objects.get(code=city_code),
        'district': Region.objects.get(code=district_code),
        'address': '测试路 100 号',
        'house_type': 'one',
        'area': 45,
        'floor': '5/10 层',
        'orientation': '南',
        'rent': 4200,
        'payment': 'y1m1',
        'amenities': ['空调', '宽带', '洗衣机'],
        'images': ['listings/seed/room-01.jpg'],
        'description': '用于自动化测试的房源描述，采光好，交通便利，家电齐全，可拎包入住。',
        'status': Listing.STATUS_LISTED,
    }
    data.update(overrides)
    return Listing.objects.create(**data)
