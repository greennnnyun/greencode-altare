from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import ListingForm
from .models import Favorite, Listing, Region
from .testing import make_listing

User = get_user_model()
PASSWORD = 'Abc12345'


def make_user(email, role):
    return User.objects.create_user(
        username=email, email=email, password=PASSWORD, role=role
    )


class FavoriteTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner@eggshell.cn', User.ROLE_LANDLORD)
        self.tenant = make_user('tenant@eggshell.cn', User.ROLE_TENANT)
        self.listing = make_listing(self.owner)

    def test_repeated_favorite_is_idempotent(self):
        self.client.force_login(self.tenant)
        url = reverse('listings:favorite', args=[self.listing.pk])

        first = self.client.post(url)
        second = self.client.post(url)

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302, '重复收藏不应报错')
        self.assertEqual(
            Favorite.objects.filter(user=self.tenant, listing=self.listing).count(), 1,
            '重复收藏不应产生重复记录',
        )

    def test_favorites_page_requires_login(self):
        response = self.client.get(reverse('listings:my_favorites'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_favorites_page_shows_own_favorites(self):
        Favorite.objects.create(user=self.tenant, listing=self.listing)
        self.client.force_login(self.tenant)

        response = self.client.get(reverse('listings:my_favorites'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.listing.title)
        self.assertEqual(len(response.context['available_listings']), 1)

    def test_favorites_page_hides_other_users_favorites(self):
        other_tenant = make_user('other-tenant@eggshell.cn', User.ROLE_TENANT)
        Favorite.objects.create(user=other_tenant, listing=self.listing)
        self.client.force_login(self.tenant)

        response = self.client.get(reverse('listings:my_favorites'))

        self.assertNotContains(response, self.listing.title, msg_prefix='不应看到别人的收藏')

    def test_unlisted_favorite_is_grouped_as_unavailable(self):
        Favorite.objects.create(user=self.tenant, listing=self.listing)
        self.listing.status = Listing.STATUS_OFF
        self.listing.save(update_fields=['status'])
        self.client.force_login(self.tenant)

        response = self.client.get(reverse('listings:my_favorites'))

        self.assertContains(response, '暂不可租')
        self.assertContains(response, self.listing.title)
        self.assertEqual(len(response.context['available_listings']), 0)
        self.assertEqual(len(response.context['unavailable_listings']), 1)

    def test_remove_from_favorites_page_removes_card(self):
        Favorite.objects.create(user=self.tenant, listing=self.listing)
        self.client.force_login(self.tenant)

        response = self.client.post(
            reverse('listings:favorite', args=[self.listing.pk]),
            {'action': 'remove', 'mode': 'favorites'},
            headers={'HX-Request': 'true'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Favorite.objects.filter(user=self.tenant, listing=self.listing).exists()
        )

    def test_favorites_page_empty_state(self):
        self.client.force_login(self.tenant)

        response = self.client.get(reverse('listings:my_favorites'))

        self.assertContains(response, '还没有收藏的房源')
        self.assertEqual(response.context['total_count'], 0)

    def test_nav_badge_counts_favorites(self):
        Favorite.objects.create(user=self.tenant, listing=self.listing)
        self.client.force_login(self.tenant)

        response = self.client.get(reverse('listings:home'))

        self.assertEqual(response.context['nav_favorites'], 1)


class ListingOwnershipTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner@eggshell.cn', User.ROLE_LANDLORD)
        self.other_landlord = make_user('other@eggshell.cn', User.ROLE_LANDLORD)
        self.listing = make_listing(self.owner)

    def test_other_landlord_cannot_edit_listing(self):
        self.client.force_login(self.other_landlord)
        response = self.client.get(
            reverse('listings:listing_edit', args=[self.listing.pk])
        )
        self.assertEqual(response.status_code, 403, '越权修改他人房源应返回 403')

    def test_edit_form_preselects_region(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('listings:listing_edit', args=[self.listing.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="310104" selected')
        self.assertContains(response, 'value="3101" selected')


class RegionFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        owner = make_user('filter-owner@eggshell.cn', User.ROLE_LANDLORD)
        cls.sh_jingan = make_listing(owner, district='静安区', title='上海静安一室')
        cls.sh_xuhui = make_listing(owner, district='徐汇区', title='上海徐汇一室')
        cls.bj_chaoyang = make_listing(owner, district='朝阳区', title='北京朝阳单间')
        cls.hz_xihu = make_listing(owner, district='西湖区', title='杭州西湖两室')

    def _ids(self, response):
        return {listing.pk for listing in response.context['listings']}

    def test_city_filter(self):
        response = self.client.get(reverse('listings:home'), {'city': '3101'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._ids(response), {self.sh_jingan.pk, self.sh_xuhui.pk})

    def test_city_and_district_combination(self):
        response = self.client.get(
            reverse('listings:home'), {'city': '3101', 'district': '310106'}
        )
        self.assertEqual(self._ids(response), {self.sh_jingan.pk})

    def test_district_from_other_city_is_ignored(self):
        response = self.client.get(
            reverse('listings:home'), {'city': '3101', 'district': '110105'}
        )
        # 区不属于该市 → 忽略区条件，仍返回该市全部
        self.assertEqual(self._ids(response), {self.sh_jingan.pk, self.sh_xuhui.pk})

    def test_invalid_codes_are_ignored(self):
        response = self.client.get(
            reverse('listings:home'), {'city': '999999', 'district': 'not-a-code'}
        )
        self.assertEqual(
            self._ids(response),
            {self.sh_jingan.pk, self.sh_xuhui.pk, self.bj_chaoyang.pk, self.hz_xihu.pk},
        )

    def test_no_cross_city_leak(self):
        response = self.client.get(reverse('listings:home'), {'city': '3301'})
        self.assertEqual(self._ids(response), {self.hz_xihu.pk})

    def test_city_change_clears_district_options(self):
        response = self.client.get(reverse('listings:home'), {'city': '1101'})
        names = [region.name for region in response.context['district_options']]
        self.assertIn('朝阳区', names)
        self.assertNotIn('徐汇区', names, '切换城市后区县选项不应残留其他城市')

    def test_region_options_endpoint(self):
        response = self.client.get(reverse('listings:region_options'), {'city': '3101'})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('徐汇区', content)
        self.assertIn('静安区', content)
        self.assertNotIn('朝阳区', content)

    def test_region_options_requires_parent(self):
        response = self.client.get(reverse('listings:region_options'), {'city': '31'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('<option value="310104"', response.content.decode())


class ListingFormRegionValidationTests(TestCase):
    def setUp(self):
        self.landlord = make_user('form-owner@eggshell.cn', User.ROLE_LANDLORD)

    def _payload(self, **overrides):
        data = {
            'title': '新发布测试房源',
            'province': '31',
            'city': '3101',
            'district': '310104',
            'address': '测试路 88 号',
            'house_type': 'one',
            'area': 40,
            'floor': '3/9 层',
            'orientation': '南',
            'rent': 3800,
            'payment': 'y1m1',
            'amenities': ['空调', '宽带', '洗衣机'],
            'description': '这是一套用于表单校验测试的房源，采光充足，交通便利，适合长期居住。',
        }
        data.update(overrides)
        return data

    def test_city_must_belong_to_province(self):
        form = ListingForm(data=self._payload(city='1101'))
        self.assertFalse(form.is_valid())
        self.assertIn('city', form.errors)

    def test_district_must_belong_to_city(self):
        form = ListingForm(data=self._payload(district='110105'))
        self.assertFalse(form.is_valid())
        self.assertIn('district', form.errors)

    def test_valid_region_passes(self):
        form = ListingForm(data=self._payload())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['province'].code, '31')
        self.assertEqual(form.cleaned_data['district'].code, '310104')

    def test_invalid_region_returns_form_error_not_500(self):
        self.client.force_login(self.landlord)
        response = self.client.post(reverse('listings:listing_create'), self._payload(city='1101'))
        self.assertEqual(response.status_code, 200, '非法地区应返回表单错误而不是 500')
        self.assertIn('city', response.context['form'].errors)
        self.assertEqual(Listing.objects.count(), 0)

    def test_region_model_levels(self):
        response = self.client.get(reverse('listings:region_options'), {'level': '2', 'province': '31'})
        self.assertIn('上海市', response.content.decode())
        self.assertNotIn('朝阳区', response.content.decode())
