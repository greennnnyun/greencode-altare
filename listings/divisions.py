"""全国行政区划数据加载与导入（供 seed_divisions 命令与数据迁移共用）。

数据文件：data/china_divisions.json
格式：扁平数组，每项 {code, name, level, parent_code}，level 1=省 2=市 3=区县。
"""
import json
from pathlib import Path

from django.conf import settings

DATA_FILE = Path(settings.BASE_DIR) / 'data' / 'china_divisions.json'


def load_divisions():
    if not DATA_FILE.exists():
        raise FileNotFoundError(f'缺少行政区划数据文件：{DATA_FILE}')
    data = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    if not isinstance(data, list) or not data:
        raise ValueError(f'行政区划数据格式异常：{DATA_FILE}')
    return data


def import_divisions(Region):
    """幂等导入：按 code upsert，返回 (created, updated, total)。

    分两步：先按 code 建行（parent 暂空），再统一回填 parent，避免父行尚未创建。
    """
    rows = load_divisions()
    codes = [row['code'] for row in rows]

    existing = {region.code: region for region in Region.objects.filter(code__in=codes)}
    to_create = [
        Region(code=row['code'], name=row['name'], level=row['level'], parent_id=None)
        for row in rows
        if row['code'] not in existing
    ]
    if to_create:
        Region.objects.bulk_create(to_create, batch_size=1000)

    by_code = {region.code: region for region in Region.objects.filter(code__in=codes)}
    to_update = []
    for row in rows:
        region = by_code[row['code']]
        parent = by_code.get(row['parent_code']) if row['parent_code'] else None
        parent_id = parent.pk if parent else None
        if region.name != row['name'] or region.level != row['level'] or region.parent_id != parent_id:
            region.name = row['name']
            region.level = row['level']
            region.parent_id = parent_id
            to_update.append(region)
    if to_update:
        Region.objects.bulk_update(to_update, ['name', 'level', 'parent'], batch_size=1000)

    return len(to_create), len(to_update), len(rows)
