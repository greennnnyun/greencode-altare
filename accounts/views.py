from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import (
    ChangePasswordForm,
    IdCardForm,
    LoginForm,
    ProfileForm,
    RegisterForm,
    ResetConfirmForm,
    ResetRequestForm,
)
from .models import EmailOTP, Profile, User
from .otp import client_ip, issue_otp, verify_otp

LOGIN_LOCK_LIMIT = 5
LOGIN_LOCK_MINUTES = 10


def _profile_for(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def register_view(request):
    if request.user.is_authenticated:
        return redirect('listings:home')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        role = form.cleaned_data['role']
        password = form.cleaned_data['password1']
        user = User.objects.filter(email=email).first()
        if user and user.is_active:
            form.add_error('email', '该邮箱已注册，请直接登录')
        else:
            if user:
                user.role = role
                user.set_password(password)
                user.is_active = False
                user.save()
            else:
                try:
                    user = User.objects.create_user(
                        username=email, email=email, password=password, role=role, is_active=False
                    )
                except IntegrityError:
                    # 并发：另一个请求刚用同一邮箱创建了账号，重新读取并复用
                    user = User.objects.filter(email=email).first()
                    if user is None:
                        form.add_error(None, '注册失败，请稍后重试')
                        return render(request, 'accounts/register.html', {'form': form})
                    if user.is_active:
                        form.add_error('email', '该邮箱已注册，请直接登录')
                        return render(request, 'accounts/register.html', {'form': form})
                    user.role = role
                    user.set_password(password)
                    user.is_active = False
                    user.save(update_fields=['role', 'password', 'is_active'])
            _profile_for(user)
            _, error = issue_otp(email, EmailOTP.PURPOSE_SIGNUP, client_ip(request))
            if error:
                messages.error(request, error)
            else:
                messages.success(request, '验证码已发送，请在 10 分钟内完成验证')
                return redirect(
                    reverse('accounts:verify_otp')
                    + f'?email={email}&purpose={EmailOTP.PURPOSE_SIGNUP}'
                )
    return render(request, 'accounts/register.html', {'form': form})


def verify_otp_view(request):
    email = (request.GET.get('email') or request.POST.get('email') or '').strip().lower()
    purpose = request.GET.get('purpose') or request.POST.get('purpose') or EmailOTP.PURPOSE_SIGNUP
    if purpose not in dict(EmailOTP.PURPOSE_CHOICES):
        purpose = EmailOTP.PURPOSE_SIGNUP
    if not email:
        messages.error(request, '请先填写邮箱')
        return redirect('accounts:register')

    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        if not code:
            messages.error(request, '请输入验证码')
        else:
            ok, error = verify_otp(email, purpose, code)
            if ok:
                user = User.objects.filter(email=email).first()
                if not user:
                    messages.error(request, '账号不存在，请重新注册')
                    return redirect('accounts:register')
                if purpose == EmailOTP.PURPOSE_SIGNUP:
                    user.is_active = True
                    user.login_failures = 0
                    user.locked_until = None
                    user.save(update_fields=['is_active', 'login_failures', 'locked_until'])
                    login(request, user, backend='accounts.backends.EmailBackend')
                    messages.success(request, '邮箱验证成功，欢迎来到蛋壳栖所')
                    return redirect('listings:home')
                request.session['reset_email'] = email
                return redirect(reverse('accounts:reset_password_verify') + f'?email={email}')
            messages.error(request, error)

    return render(
        request,
        'accounts/verify_otp.html',
        {'email': email, 'purpose': purpose, 'purpose_label': dict(EmailOTP.PURPOSE_CHOICES).get(purpose)},
    )


@require_POST
def resend_otp_view(request):
    email = (request.POST.get('email') or '').strip().lower()
    purpose = request.POST.get('purpose') or EmailOTP.PURPOSE_SIGNUP
    if purpose not in dict(EmailOTP.PURPOSE_CHOICES):
        purpose = EmailOTP.PURPOSE_SIGNUP
    user = User.objects.filter(email=email).first()
    if not user:
        messages.error(request, '该邮箱尚未注册')
        return redirect('accounts:register')
    _, error = issue_otp(email, purpose, client_ip(request))
    if error:
        messages.error(request, error)
    else:
        messages.success(request, '新的验证码已发送，请查收邮件')
    return redirect(reverse('accounts:verify_otp') + f'?email={email}&purpose={purpose}')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('listings:home')
    form = LoginForm(request.POST or None)
    next_url = request.GET.get('next') or request.POST.get('next') or ''
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']
        user = User.objects.filter(email=email).first()
        now = timezone.now()
        if user and user.locked_until and user.locked_until > now:
            minutes = max(1, int((user.locked_until - now).total_seconds() // 60) + 1)
            form.add_error(None, f'登录失败次数过多，账号已锁定，请约 {minutes} 分钟后再试')
        elif not user:
            form.add_error(None, '邮箱或密码不正确')
        elif not user.is_active:
            form.add_error(None, '账号尚未激活，请先完成邮箱验证')
        else:
            auth_user = authenticate(request, username=email, password=password)
            if auth_user is None:
                user.login_failures += 1
                update_fields = ['login_failures']
                if user.login_failures >= LOGIN_LOCK_LIMIT:
                    user.locked_until = now + timedelta(minutes=LOGIN_LOCK_MINUTES)
                    user.login_failures = 0
                    update_fields.append('locked_until')
                    user.save(update_fields=update_fields)
                    form.add_error(None, f'连续 {LOGIN_LOCK_LIMIT} 次登录失败，账号已锁定 10 分钟')
                else:
                    user.save(update_fields=update_fields)
                    remaining = LOGIN_LOCK_LIMIT - user.login_failures
                    form.add_error(None, f'邮箱或密码不正确，还可尝试 {remaining} 次')
            else:
                if user.login_failures or user.locked_until:
                    user.login_failures = 0
                    user.locked_until = None
                    user.save(update_fields=['login_failures', 'locked_until'])
                login(request, auth_user, backend='accounts.backends.EmailBackend')
                messages.success(request, f'欢迎回来，{_profile_for(user).display_name}')
                if next_url and url_has_allowed_host_and_scheme(
                    next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
                ):
                    return redirect(next_url)
                return redirect('listings:home')
    return render(request, 'accounts/login.html', {'form': form, 'next_url': next_url})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, '已安全退出登录')
    return redirect('listings:home')


def password_reset_view(request):
    if request.user.is_authenticated:
        return redirect('accounts:profile')
    form = ResetRequestForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        user = User.objects.filter(email=email).first()
        if not user:
            form.add_error('email', '该邮箱尚未注册')
        else:
            _, error = issue_otp(email, EmailOTP.PURPOSE_RESET, client_ip(request))
            if error:
                messages.error(request, error)
            else:
                messages.success(request, '重置验证码已发送，请在 10 分钟内完成操作')
                return redirect(
                    reverse('accounts:reset_password_verify')
                    + f'?email={email}&purpose={EmailOTP.PURPOSE_RESET}'
                )
    return render(request, 'accounts/password_reset.html', {'form': form})


def password_reset_verify_view(request):
    email = (request.GET.get('email') or request.POST.get('email') or '').strip().lower()
    if not email:
        return redirect('accounts:password_reset')
    user = User.objects.filter(email=email).first()
    if not user:
        messages.error(request, '该邮箱尚未注册')
        return redirect('accounts:password_reset')

    form = ResetConfirmForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        ok, error = verify_otp(email, EmailOTP.PURPOSE_RESET, form.cleaned_data['code'])
        if not ok:
            messages.error(request, error)
        else:
            user.set_password(form.cleaned_data['password1'])
            user.login_failures = 0
            user.locked_until = None
            user.save(update_fields=['password', 'login_failures', 'locked_until'])
            messages.success(request, '密码已重置，请使用新密码登录')
            return redirect('accounts:login')
    return render(
        request,
        'accounts/password_reset_verify.html',
        {'form': form, 'email': email},
    )


@login_required
def profile_view(request):
    profile = _profile_for(request.user)
    return render(
        request,
        'accounts/profile.html',
        {
            'profile': profile,
            'profile_form': ProfileForm(instance=profile),
            'id_card_form': IdCardForm(instance=profile),
        },
    )


@login_required
@require_POST
def profile_update_view(request):
    profile = _profile_for(request.user)
    form = ProfileForm(request.POST, request.FILES, instance=profile)
    if form.is_valid():
        form.save()
        messages.success(request, '个人资料已更新')
    else:
        messages.error(request, '资料保存失败：' + '；'.join(sum(form.errors.values(), [])))
    return redirect('accounts:profile')


@login_required
@require_POST
def id_card_update_view(request):
    profile = _profile_for(request.user)
    form = IdCardForm(request.POST, request.FILES, instance=profile)
    if form.is_valid():
        profile = form.save()
        if profile.verified:
            messages.success(request, '身份证正反面已齐全，实名认证已点亮')
        else:
            messages.info(request, '已保存，请补齐身份证正反面后自动完成认证')
    else:
        messages.error(request, '上传失败：' + '；'.join(sum(form.errors.values(), [])))
    return redirect('accounts:profile')


@login_required
def id_card_view(request, side, profile_id=None):
    if side not in {'front', 'back'}:
        raise Http404
    if profile_id is None:
        profile = get_object_or_404(Profile, user=request.user)
    else:
        profile = get_object_or_404(Profile, pk=profile_id)
        if request.user != profile.user and not request.user.is_staff:
            raise PermissionDenied('无权查看该身份证照片')
    field = profile.id_card_front if side == 'front' else profile.id_card_back
    if not field:
        raise Http404
    response = FileResponse(field.storage.open(field.name, 'rb'), content_type='image/jpeg')
    response['Cache-Control'] = 'private, no-store'
    return response


@login_required
def change_password_view(request):
    form = ChangePasswordForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        update_session_auth_hash(request, request.user)
        messages.success(request, '密码修改成功')
        return redirect('accounts:profile')
    return render(request, 'accounts/change_password.html', {'form': form})
