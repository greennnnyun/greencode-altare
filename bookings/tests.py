from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from listings.models import Listing
from listings.testing import make_listing

from .models import Viewing

User = get_user_model()


class ViewingPermissionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner@eggshell.cn', email='owner@eggshell.cn',
            password='Abc12345', role=User.ROLE_LANDLORD,
        )
        self.other_landlord = User.objects.create_user(
            username='other@eggshell.cn', email='other@eggshell.cn',
            password='Abc12345', role=User.ROLE_LANDLORD,
        )
        self.tenant = User.objects.create_user(
            username='tenant@eggshell.cn', email='tenant@eggshell.cn',
            password='Abc12345', role=User.ROLE_TENANT,
        )
        self.listing = make_listing(self.owner)
        self.viewing = Viewing.objects.create(
            user=self.tenant,
            listing=self.listing,
            name='小蛋壳',
            phone='13800138000',
            visit_date=timezone.localdate() + timedelta(days=2),
            status=Viewing.STATUS_PENDING,
        )

    def test_non_owner_landlord_cannot_confirm_booking(self):
        self.client.force_login(self.other_landlord)
        response = self.client.post(
            reverse('bookings:update', args=[self.viewing.pk]),
            {'action': 'confirm'},
        )
        self.assertEqual(response.status_code, 403, '非房源 owner 确认预约应返回 403')
        self.viewing.refresh_from_db()
        self.assertEqual(self.viewing.status, Viewing.STATUS_PENDING)


class RentedListingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner@eggshell.cn', email='owner@eggshell.cn',
            password='Abc12345', role=User.ROLE_LANDLORD,
        )
        self.tenant = User.objects.create_user(
            username='tenant@eggshell.cn', email='tenant@eggshell.cn',
            password='Abc12345', role=User.ROLE_TENANT,
        )
        self.listing = make_listing(self.owner, status=Listing.STATUS_RENTED)

    def test_rented_listing_rejects_new_viewing(self):
        self.client.force_login(self.tenant)
        response = self.client.post(
            reverse('bookings:create', args=[self.listing.pk]),
            {
                'name': '小蛋壳',
                'phone': '13800138000',
                'visit_date': (timezone.localdate() + timedelta(days=3)).isoformat(),
                'note': '周末上午方便',
            },
        )
        self.assertEqual(response.status_code, 400, '已租出房源不应接受新预约')
        self.assertEqual(Viewing.objects.filter(listing=self.listing).count(), 0)

    def test_rented_listing_rejects_new_application(self):
        self.client.force_login(self.tenant)
        response = self.client.post(
            reverse('contracts:apply', args=[self.listing.pk])
        )
        self.assertEqual(response.status_code, 400, '已租出房源不应接受新的租房申请')
