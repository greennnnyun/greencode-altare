"""Region 模型 + Listing 地区改为省/市/区三级外键。

旧的 district CharField（上海 9 个区）在此迁移中退场：
1. 建 Region 并导入全国行政区划；
2. 新增 province / city / district_ref（临时名）三个外键；
3. 按区名把现有房源映射到对应 Region；
4. 删除旧 CharField，把临时字段改名为 district，并补索引。
"""
import django.db.models.deletion
from django.db import migrations, models


def forwards(apps, schema_editor):
    from listings.divisions import import_divisions

    Region = apps.get_model('listings', 'Region')
    Listing = apps.get_model('listings', 'Listing')
    db = schema_editor.connection.alias

    created, updated, total = import_divisions(Region)
    if total == 0:
        raise RuntimeError('行政区划导入为空，无法回填房源地区')

    shanghai = Region.objects.using(db).filter(level=1, name='上海市').first()
    if shanghai is None:
        raise RuntimeError('行政区划数据缺少上海市，无法回填')
    city = Region.objects.using(db).filter(level=2, parent=shanghai).first()
    if city is None:
        raise RuntimeError('行政区划数据缺少上海市下辖城市，无法回填')
    fallback = Region.objects.using(db).filter(level=3, parent=city).first()
    if fallback is None:
        raise RuntimeError('行政区划数据缺少上海市辖区，无法回填')

    for listing in Listing.objects.using(db).all():
        name = (listing.district or '').strip()
        region = None
        if name:
            region = Region.objects.using(db).filter(level=3, name=name, parent=city).first()
        if region is None:
            region = fallback
        listing.province_id = shanghai.pk
        listing.city_id = city.pk
        listing.district_ref_id = region.pk
        listing.save(update_fields=['province', 'city', 'district_ref'])


def backwards(apps, schema_editor):
    """回滚只恢复字段结构，具体区名无法精确还原。"""
    return None


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Region',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=12, unique=True, verbose_name='行政区划代码')),
                ('name', models.CharField(max_length=80, verbose_name='名称')),
                (
                    'level',
                    models.PositiveSmallIntegerField(
                        choices=[(1, '省级'), (2, '地级'), (3, '区县')], verbose_name='层级'
                    ),
                ),
                (
                    'parent',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='children',
                        to='listings.region',
                        verbose_name='上级',
                    ),
                ),
            ],
            options={
                'verbose_name': '行政区划',
                'verbose_name_plural': '行政区划',
                'ordering': ['code'],
                'indexes': [models.Index(fields=['level', 'parent'], name='region_level_parent_idx')],
            },
        ),
        migrations.AddField(
            model_name='listing',
            name='province',
            field=models.ForeignKey(
                limit_choices_to={'level': 1},
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+',
                to='listings.region',
                verbose_name='省份',
            ),
        ),
        migrations.AddField(
            model_name='listing',
            name='city',
            field=models.ForeignKey(
                limit_choices_to={'level': 2},
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+',
                to='listings.region',
                verbose_name='城市',
            ),
        ),
        migrations.AddField(
            model_name='listing',
            name='district_ref',
            field=models.ForeignKey(
                limit_choices_to={'level': 3},
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+',
                to='listings.region',
                verbose_name='区县',
            ),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveIndex(
            model_name='listing',
            name='listings_li_status_6b5738_idx',
        ),
        migrations.RemoveField(
            model_name='listing',
            name='district',
        ),
        migrations.RenameField(
            model_name='listing',
            old_name='district_ref',
            new_name='district',
        ),
        migrations.AlterField(
            model_name='listing',
            name='province',
            field=models.ForeignKey(
                limit_choices_to={'level': 1},
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+',
                to='listings.region',
                verbose_name='省份',
            ),
        ),
        migrations.AlterField(
            model_name='listing',
            name='city',
            field=models.ForeignKey(
                limit_choices_to={'level': 2},
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+',
                to='listings.region',
                verbose_name='城市',
            ),
        ),
        migrations.AlterField(
            model_name='listing',
            name='district',
            field=models.ForeignKey(
                limit_choices_to={'level': 3},
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+',
                to='listings.region',
                verbose_name='区县',
            ),
        ),
        migrations.AddIndex(
            model_name='listing',
            index=models.Index(
                fields=['status', 'is_deleted', 'city', 'district'],
                name='listing_status_city_dist_idx',
            ),
        ),
    ]
