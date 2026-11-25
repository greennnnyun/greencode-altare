import threading
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import EmailOTP, Profile
from .otp import verify_otp

User = get_user_model()


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class OTPActivationTests(TestCase):
    def test_signup_otp_activation_success(self):
        user = User.objects.create_user(
            username='new@eggshell.cn', email='new@eggshell.cn',
            password='Abc12345', is_active=False,
        )
        otp = EmailOTP.objects.create(
            email='new@eggshell.cn',
            code='123456',
            purpose=EmailOTP.PURPOSE_SIGNUP,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        response = self.client.post(
            reverse('accounts:verify_otp'),
            {
                'email': 'new@eggshell.cn',
                'purpose': EmailOTP.PURPOSE_SIGNUP,
                'code': otp.code,
            },
        )

        self.assertEqual(response.status_code, 302)
        user.refresh_from_db()
        otp.refresh_from_db()
        self.assertTrue(user.is_active, '验证码正确后账号应被激活')
        self.assertTrue(otp.used, '验证码使用后应标记为已使用')
        self.assertEqual(response.url, reverse('listings:home'))

    def test_five_wrong_attempts_invalidate_otp(self):
        otp = EmailOTP.objects.create(
            email='wrong@eggshell.cn',
            code='654321',
            purpose=EmailOTP.PURPOSE_SIGNUP,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        for _ in range(5):
            ok, _msg = verify_otp('wrong@eggshell.cn', EmailOTP.PURPOSE_SIGNUP, '000000')
            self.assertFalse(ok)

        otp.refresh_from_db()
        self.assertTrue(otp.used, '同一邮箱累计 5 次错误后验证码应作废')
        self.assertEqual(otp.attempts, 5)

        ok, msg = verify_otp('wrong@eggshell.cn', EmailOTP.PURPOSE_SIGNUP, '654321')
        self.assertFalse(ok, '已作废的验证码即使输入正确也不应通过')
        self.assertTrue(msg)


class IdCardPermissionTests(TestCase):
    def test_other_user_cannot_view_id_card(self):
        owner = User.objects.create_user(
            username='owner@eggshell.cn', email='owner@eggshell.cn', password='Abc12345'
        )
        intruder = User.objects.create_user(
            username='intruder@eggshell.cn', email='intruder@eggshell.cn', password='Abc12345'
        )
        profile = Profile.objects.get_or_create(user=owner)[0]
        profile.id_card_front = 'id_cards/fake-front.jpg'
        profile.save(update_fields=['id_card_front'])

        self.client.force_login(intruder)
        response = self.client.get(
            reverse('accounts:id_card_admin', args=[profile.pk, 'front'])
        )
        self.assertEqual(response.status_code, 403, '非本人且非运营不应访问身份证照片')


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ConcurrentRegisterTests(TransactionTestCase):
    def test_two_concurrent_registrations_same_email_no_500(self):
        """同一邮箱被并发提交两次时，不应抛 500，且只创建一个账号。"""
        email = 'race@eggshell.cn'
        payload = {
            'email': email,
            'role': 'tenant',
            'password1': 'EgShell2026!',
            'password2': 'EgShell2026!',
        }
        results = [None, None]

        def worker(idx):
            client = Client()
            resp = client.post(reverse('accounts:register'), payload)
            results[idx] = resp.status_code

        t1 = threading.Thread(target=worker, args=(0,))
        t2 = threading.Thread(target=worker, args=(1,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        for code in results:
            self.assertIn(code, (200, 302), f'并发注册不应返回 500，实际 {code}')
        self.assertEqual(User.objects.filter(email=email).count(), 1)
