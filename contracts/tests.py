from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from listings.models import Listing
from listings.testing import make_listing

from .models import RentalApplication

PASSWORD = 'Passw0rd123'


def make_user(email, role):
    return User.objects.create_user(
        username=email, email=email, password=PASSWORD, role=role, is_active=True
    )


def make_contract_listing(owner, rent=3000, payment='y1m3'):
    return make_listing(
        owner,
        district='黄浦区',
        title='合同测试房源',
        rent=rent,
        payment=payment,
        house_type='two',
        area=60,
        floor='7/15 层',
        orientation='南北',
        amenities=['空调', '洗衣机', '冰箱'],
        images=['listings/seed/room-03.jpg'],
        description='自动化测试用房源描述，长度超过六十个字符，用于合同签署流程测试。',
    )


class ContractTests(TestCase):
    def setUp(self):
        self.owner = make_user('owner@example.com', User.ROLE_LANDLORD)
        self.tenant = make_user('tenant@example.com', User.ROLE_TENANT)
        self.other_tenant = make_user('other@example.com', User.ROLE_TENANT)
        self.listing = make_contract_listing(self.owner)

    def _apply(self):
        self.client.login(username='tenant@example.com', password=PASSWORD)
        self.client.post(reverse('contracts:apply', args=[self.listing.pk]))
        return RentalApplication.objects.get(user=self.tenant, listing=self.listing)

    def test_apply_is_idempotent_and_first_payment(self):
        application = self._apply()
        # 首期应付 = 押金 + 月租 × 付款月数（押一付三 → 3000 + 3000×3）
        self.assertEqual(application.deposit, 3000)
        self.assertEqual(application.first_payment, 3000 + 3000 * 3)

        self.client.post(reverse('contracts:apply', args=[self.listing.pk]))
        self.assertEqual(
            RentalApplication.objects.filter(user=self.tenant, listing=self.listing).count(), 1
        )

    def test_sign_then_resign_is_idempotent(self):
        application = self._apply()
        start = (timezone.localdate() + timedelta(days=10)).isoformat()
        payload = {'start_date': start, 'months': '12', 'agree': 'on'}
        response = self.client.post(reverse('contracts:sign', args=[application.pk]), payload)
        self.assertEqual(response.status_code, 302)
        application.refresh_from_db()
        self.assertEqual(application.status, RentalApplication.STATUS_SIGNED)
        self.assertIsNotNone(application.signed_at)
        first_signed_at = application.signed_at

        # 重复提交：不报错、不产生新记录、signed_at 不变
        response = self.client.post(reverse('contracts:sign', args=[application.pk]), payload)
        self.assertEqual(response.status_code, 302)
        application.refresh_from_db()
        self.assertEqual(application.signed_at, first_signed_at)
        self.assertEqual(
            RentalApplication.objects.filter(user=self.tenant, listing=self.listing).count(), 1
        )

    def test_sign_others_contract_forbidden(self):
        application = self._apply()
        self.client.logout()
        self.client.login(username='other@example.com', password=PASSWORD)
        response = self.client.post(
            reverse('contracts:sign', args=[application.pk]),
            {'start_date': timezone.localdate().isoformat(), 'months': '12', 'agree': 'on'},
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse('contracts:contract', args=[application.pk]))
        self.assertEqual(response.status_code, 403)

    def test_landlord_can_view_own_listing_contract_and_list(self):
        application = self._apply()
        self.client.logout()
        self.client.login(username='owner@example.com', password=PASSWORD)

        response = self.client.get(reverse('contracts:contract', args=[application.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['is_applicant'])

        response = self.client.get(reverse('contracts:list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['pending_apps']), 1)
        self.assertEqual(len(response.context['signed_apps']), 0)

    def test_tenant_contract_list_groups(self):
        application = self._apply()
        response = self.client.get(reverse('contracts:list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['pending_apps']), 1)
        self.assertEqual(len(response.context['signed_apps']), 0)

        start = (timezone.localdate() + timedelta(days=10)).isoformat()
        self.client.post(
            reverse('contracts:sign', args=[application.pk]),
            {'start_date': start, 'months': '12', 'agree': 'on'},
        )
        response = self.client.get(reverse('contracts:list'))
        self.assertEqual(len(response.context['pending_apps']), 0)
        self.assertEqual(len(response.context['signed_apps']), 1)

    def test_landlord_cannot_sign_contract(self):
        application = self._apply()
        self.client.logout()
        self.client.login(username='owner@example.com', password=PASSWORD)
        response = self.client.post(
            reverse('contracts:sign', args=[application.pk]),
            {'start_date': timezone.localdate().isoformat(), 'months': '12', 'agree': 'on'},
        )
        self.assertEqual(response.status_code, 403)
