import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)


def _purpose_label(purpose):
    return {'signup': '注册激活', 'reset_password': '重置密码'}.get(purpose, '身份验证')


def build_mail(code, purpose):
    plain = (
        '您好！\n\n'
        f'您正在「蛋壳栖所」{_purpose_label(purpose)}，验证码为：{code}\n'
        '验证码 10 分钟内有效，请勿泄露给他人。\n'
        '如非本人操作，请忽略本邮件。\n\n'
        '蛋壳栖所 · 把每一次搬家，都变成一次归巢。'
    )
    html = f"""
    <div style="font-family:Arial,'PingFang SC','Microsoft YaHei',sans-serif;background:#faf7f1;padding:32px;">
      <div style="max-width:560px;margin:0 auto;background:#fffdf8;border:1px solid #eadfce;border-radius:16px;padding:32px;">
        <h2 style="margin:0 0 16px;font-size:20px;color:#3b3128;">蛋壳栖所 · 验证码</h2>
        <p style="margin:0 0 12px;color:#6b5d4f;font-size:14px;line-height:1.8;">
          您正在{_purpose_label(purpose)}，本次验证码为：
        </p>
        <div style="margin:20px 0;padding:16px;background:#f6ead9;border-radius:12px;text-align:center;">
          <span style="font-size:30px;letter-spacing:8px;font-weight:700;color:#c2571a;">{code}</span>
        </div>
        <p style="margin:0;color:#8b7a69;font-size:13px;line-height:1.8;">
          验证码 10 分钟内有效，请勿泄露给他人。如非本人操作，请忽略本邮件。
        </p>
      </div>
      <p style="text-align:center;color:#a99a89;font-size:12px;margin-top:20px;">
        蛋壳栖所 · 把每一次搬家，都变成一次归巢。
      </p>
    </div>
    """
    subject = '蛋壳栖所 · 验证码'
    from_email = settings.DEFAULT_FROM_EMAIL
    message = EmailMultiAlternatives(subject, plain, from_email, [])
    message.attach_alternative(html, 'text/html')
    return message


def send_otp_email(email, code, purpose):
    """发送验证码邮件。返回 (成功?, 错误提示)。异常不会被静默吞掉。"""
    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        logger.error('SMTP 账号未配置，无法发送验证码邮件')
        return False, '邮件服务未配置，请联系管理员或稍后重试'
    message = build_mail(code, purpose)
    message.to = [email]
    try:
        message.send(fail_silently=False)
        logger.info('验证码邮件已发送至 %s（用途 %s）', email, purpose)
        return True, ''
    except Exception as exc:  # noqa: BLE001 - 需要给前端明确提示
        logger.exception('验证码邮件发送失败: %s', exc)
        return False, '验证码发送失败，请稍后重试'


def send_test_email(to_email):
    subject = '蛋壳栖所 · 测试邮件'
    plain = '这是一封来自蛋壳栖所的测试邮件。收到它说明 QQ SMTP 授权码配置正确。'
    html = (
        '<div style="font-family:Arial,\'Microsoft YaHei\',sans-serif;padding:24px;background:#faf7f1;">'
        '<div style="max-width:520px;margin:auto;background:#fffdf8;border:1px solid #eadfce;'
        'border-radius:16px;padding:28px;color:#3b3128;">'
        '<h2 style="margin:0 0 12px;font-size:19px;">蛋壳栖所 · 测试邮件</h2>'
        '<p style="color:#6b5d4f;font-size:14px;line-height:1.8;">'
        '收到它说明 QQ SMTP 授权码配置正确，验证码邮件可以正常发出。</p>'
        '</div></div>'
    )
    message = EmailMultiAlternatives(subject, plain, settings.DEFAULT_FROM_EMAIL, [to_email])
    message.attach_alternative(html, 'text/html')
    message.send(fail_silently=False)
    return True
