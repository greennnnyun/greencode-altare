from django.core.management.base import BaseCommand

from accounts.emails import send_test_email


class Command(BaseCommand):
    help = '发送一封 QQ SMTP 测试邮件，验证 .env 中的邮箱与授权码配置'

    def add_arguments(self, parser):
        parser.add_argument('to', help='收件邮箱，例如 you@example.com')

    def handle(self, *args, **options):
        to = options['to']
        self.stdout.write(f'正在通过 QQ SMTP 发送测试邮件到 {to} ...')
        try:
            send_test_email(to)
        except Exception as exc:  # noqa: BLE001
            self.stderr.write(self.style.ERROR(f'发送失败：{exc}'))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS('测试邮件发送成功，请查收（注意垃圾邮件箱）'))
