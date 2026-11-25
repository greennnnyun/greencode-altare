from django import forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError

from .models import Profile


class RegisterForm(forms.Form):
    email = forms.EmailField(
        label='邮箱',
        widget=forms.EmailInput(attrs={'class': 'input input-bordered w-full field-glow', 'placeholder': 'you@example.com'}),
    )
    role = forms.ChoiceField(
        label='我想要',
        choices=[('tenant', '我是租客，想找房'), ('landlord', '我是房东，想出租')],
        widget=forms.RadioSelect(attrs={'class': 'radio radio-primary'}),
        initial='tenant',
    )
    password1 = forms.CharField(
        label='密码',
        min_length=8,
        widget=forms.PasswordInput(attrs={'class': 'input input-bordered w-full field-glow', 'placeholder': '至少 8 位，含字母和数字'}),
    )
    password2 = forms.CharField(
        label='确认密码',
        widget=forms.PasswordInput(attrs={'class': 'input input-bordered w-full field-glow', 'placeholder': '再次输入密码'}),
    )

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        return email

    def clean(self):
        data = super().clean()
        p1, p2 = data.get('password1'), data.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', '两次输入的密码不一致')
        if p1:
            try:
                password_validation.validate_password(p1)
            except ValidationError as exc:
                self.add_error('password1', exc)
        return data

    def clean_role(self):
        role = self.cleaned_data['role']
        if role not in {'tenant', 'landlord'}:
            raise ValidationError('请选择有效的身份')
        return role


class LoginForm(forms.Form):
    email = forms.EmailField(
        label='邮箱',
        widget=forms.EmailInput(attrs={'class': 'input input-bordered w-full field-glow', 'placeholder': '请输入注册邮箱'}),
    )
    password = forms.CharField(
        label='密码',
        widget=forms.PasswordInput(attrs={'class': 'input input-bordered w-full field-glow', 'placeholder': '请输入密码'}),
    )

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()


class ResetRequestForm(forms.Form):
    email = forms.EmailField(
        label='邮箱',
        widget=forms.EmailInput(attrs={'class': 'input input-bordered w-full field-glow', 'placeholder': '请输入注册邮箱'}),
    )

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()


class ResetConfirmForm(forms.Form):
    code = forms.CharField(
        label='验证码',
        max_length=6,
        min_length=6,
        widget=forms.TextInput(
            attrs={
                'class': 'input input-bordered w-full tracking-[0.4em] text-center field-glow',
                'placeholder': '6 位数字',
                'inputmode': 'numeric',
                'autocomplete': 'one-time-code',
            }
        ),
    )
    password1 = forms.CharField(
        label='新密码',
        min_length=8,
        widget=forms.PasswordInput(attrs={'class': 'input input-bordered w-full field-glow', 'placeholder': '至少 8 位，含字母和数字'}),
    )
    password2 = forms.CharField(
        label='确认新密码',
        widget=forms.PasswordInput(attrs={'class': 'input input-bordered w-full field-glow', 'placeholder': '再次输入新密码'}),
    )

    def clean_code(self):
        code = self.cleaned_data['code'].strip()
        if not code.isdigit():
            raise ValidationError('验证码应为 6 位数字')
        return code

    def clean(self):
        data = super().clean()
        p1, p2 = data.get('password1'), data.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', '两次输入的密码不一致')
        if p1:
            try:
                password_validation.validate_password(p1)
            except ValidationError as exc:
                self.add_error('password1', exc)
        return data


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['nickname', 'phone', 'avatar']
        widgets = {
            'nickname': forms.TextInput(attrs={'class': 'input input-bordered w-full field-glow', 'placeholder': '给自己起个昵称'}),
            'phone': forms.TextInput(attrs={'class': 'input input-bordered w-full field-glow', 'placeholder': '选填，1 开头的 11 位手机号'}),
            'avatar': forms.FileInput(attrs={'class': 'file-input file-input-bordered w-full', 'accept': 'image/jpeg,image/png,image/webp'}),
        }

    def clean_phone(self):
        phone = (self.cleaned_data.get('phone') or '').strip()
        if phone and not phone.isdigit():
            raise ValidationError('手机号只能包含数字')
        if phone and (len(phone) != 11 or not phone.startswith('1')):
            raise ValidationError('请输入 1 开头的 11 位手机号')
        return phone

    def clean_avatar(self):
        from .images import prepare_image

        upload = self.cleaned_data.get('avatar')
        if upload and hasattr(upload, 'size'):
            return prepare_image(upload)
        return upload


class IdCardForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['id_card_front', 'id_card_back']
        widgets = {
            'id_card_front': forms.FileInput(attrs={'class': 'file-input file-input-bordered w-full', 'accept': 'image/jpeg,image/png,image/webp'}),
            'id_card_back': forms.FileInput(attrs={'class': 'file-input file-input-bordered w-full', 'accept': 'image/jpeg,image/png,image/webp'}),
        }

    def _clean_card(self, field):
        from .images import prepare_image

        upload = self.cleaned_data.get(field)
        if upload and hasattr(upload, 'size'):
            return prepare_image(upload)
        return upload

    def clean_id_card_front(self):
        return self._clean_card('id_card_front')

    def clean_id_card_back(self):
        return self._clean_card('id_card_back')


class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(
        label='当前密码',
        widget=forms.PasswordInput(attrs={'class': 'input input-bordered w-full field-glow'}),
    )
    new_password1 = forms.CharField(
        label='新密码',
        min_length=8,
        widget=forms.PasswordInput(attrs={'class': 'input input-bordered w-full field-glow'}),
    )
    new_password2 = forms.CharField(
        label='确认新密码',
        widget=forms.PasswordInput(attrs={'class': 'input input-bordered w-full field-glow'}),
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        old = self.cleaned_data['old_password']
        if not self.user.check_password(old):
            raise ValidationError('当前密码不正确')
        return old

    def clean(self):
        data = super().clean()
        p1, p2 = data.get('new_password1'), data.get('new_password2')
        if p1 and p2 and p1 != p2:
            self.add_error('new_password2', '两次输入的密码不一致')
        if p1:
            try:
                password_validation.validate_password(p1, self.user)
            except ValidationError as exc:
                self.add_error('new_password1', exc)
        return data

    def save(self):
        self.user.set_password(self.cleaned_data['new_password1'])
        self.user.save(update_fields=['password'])
        return self.user
