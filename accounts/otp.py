import secrets
from datetime import timedelta

from django.utils import timezone

from .emails import send_otp_email
from .models import EmailOTP

OTP_EXPIRE_MINUTES = 10
RESEND_COOLDOWN_SECONDS = 60
MAX_ATTEMPTS = 5
IP_HOURLY_LIMIT = 10


def client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') or None


def _cooldown_seconds(email):
    latest = EmailOTP.objects.filter(email=email).order_by('-created_at').first()
    if not latest:
        return 0
    elapsed = (timezone.now() - latest.created_at).total_seconds()
    return max(0, int(RESEND_COOLDOWN_SECONDS - elapsed))


def issue_otp(email, purpose, ip=None):
    """生成并发送验证码。返回 (otp, 错误提示)。"""
    email = email.strip().lower()
    wait = _cooldown_seconds(email)
    if wait > 0:
        return None, f'发送太频繁啦，请 {wait} 秒后再试'
    if ip and EmailOTP.objects.filter(
        request_ip=ip, created_at__gte=timezone.now() - timedelta(hours=1)
    ).count() >= IP_HOURLY_LIMIT:
        return None, '当前网络发送验证码过于频繁，请稍后再试'

    EmailOTP.objects.filter(email=email, purpose=purpose, used=False).update(used=True)
    code = f'{secrets.randbelow(1_000_000):06d}'
    otp = EmailOTP.objects.create(
        email=email,
        code=code,
        purpose=purpose,
        expires_at=timezone.now() + timedelta(minutes=OTP_EXPIRE_MINUTES),
        request_ip=ip,
    )
    ok, error = send_otp_email(email, code, purpose)
    if not ok:
        # 发送失败则回收本次记录，允许用户马上重试
        otp.delete()
        return None, error
    return otp, ''


def verify_otp(email, purpose, code):
    """校验验证码。返回 (成功?, 提示)。累计 5 次错误即作废。"""
    email = email.strip().lower()
    otp = (
        EmailOTP.objects.filter(email=email, purpose=purpose, used=False)
        .order_by('-created_at')
        .first()
    )
    if not otp:
        return False, '请先获取验证码'
    if otp.expires_at <= timezone.now():
        otp.used = True
        otp.save(update_fields=['used'])
        return False, '验证码已过期，请重新获取'
    if otp.attempts >= MAX_ATTEMPTS:
        otp.used = True
        otp.save(update_fields=['used'])
        return False, '验证码错误次数过多，已作废，请重新获取'
    if not secrets.compare_digest(otp.code, str(code).strip()):
        otp.attempts += 1
        update_fields = ['attempts']
        message = '验证码不正确'
        if otp.attempts >= MAX_ATTEMPTS:
            otp.used = True
            update_fields.append('used')
            message = '验证码错误次数过多，已作废，请重新获取'
        otp.save(update_fields=update_fields)
        return False, message
    otp.used = True
    otp.save(update_fields=['used'])
    return True, ''
