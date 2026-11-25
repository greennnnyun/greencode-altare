from django.core.exceptions import ValidationError


class LetterNumberValidator:
    def validate(self, password, user=None):
        if not any(ch.isalpha() for ch in password) or not any(ch.isdigit() for ch in password):
            raise ValidationError('密码必须同时包含字母和数字', code='password_no_letter_number')

    def get_help_text(self):
        return '密码必须同时包含字母和数字。'

    def __call__(self, value):
        self.validate(value)
