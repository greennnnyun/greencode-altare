from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from listings.models import Listing

from .models import RentalApplication


def _first_payment(listing):
    return listing.rent + listing.rent * listing.payment_months


@login_required
@require_POST
def apply_rental(request, listing_id):
    listing = get_object_or_404(Listing, pk=listing_id, is_deleted=False)
    if not request.user.is_tenant:
        raise PermissionDenied('仅租客账号可以申请租房')
    if listing.owner_id == request.user.id:
        raise PermissionDenied('不能申请自己发布的房源')
    if listing.status != Listing.STATUS_LISTED:
        return HttpResponseBadRequest('该房源当前不可申请（已下架或已租出）')

    with transaction.atomic():
        application, created = RentalApplication.objects.get_or_create(
            user=request.user,
            listing=listing,
            defaults={
                'start_date': date.today() + timedelta(days=7),
                'months': 12,
                'deposit': listing.rent,
                'first_payment': _first_payment(listing),
            },
        )
    if created:
        messages.success(request, '租房申请已创建，请确认合同信息并签署')
    else:
        messages.info(request, '你已经申请过这套房源，请继续完成签署')
    return redirect('contracts:contract', pk=application.pk)


def _clauses(application, listing):
    landlord_name = getattr(getattr(listing.owner, 'profile', None), 'display_name', None) or listing.owner.email
    tenant_name = getattr(getattr(application.user, 'profile', None), 'display_name', None) or application.user.email
    payment_label = listing.payment_label
    return [
        (
            '01',
            '租赁期限',
            f'出租方（{landlord_name}）将位于{listing.region_display}{listing.address}的房屋出租给承租方'
            f'（{tenant_name}）居住使用。租赁期限为 {application.months} 个月，自 {application.start_date:%Y 年 %m 月 %d 日} 起算。',
        ),
        (
            '02',
            '租金与押金',
            f'该房屋月租金为人民币 {listing.rent} 元，押金为人民币 {application.deposit} 元。'
            '押金于租期届满、房屋及附属设施验收无损坏且费用结清后无息退还。',
        ),
        (
            '03',
            '付款方式',
            f'付款方式为「{payment_label}」，按房源约定周期支付租金。首期应付为人民币 '
            f'{application.first_payment} 元（押金 {application.deposit} 元 + 月租 × {listing.payment_months} 个月）。',
        ),
        (
            '04',
            '房屋用途',
            '承租方仅可将该房屋用于自住，不得用于经营、仓储或群租；未经出租方书面同意，不得转租、转借或改变房屋结构。',
        ),
        (
            '05',
            '维修责任',
            '房屋主体结构及非承租方原因造成的设施损坏由出租方负责维修；因承租方使用不当造成损坏的，由承租方承担维修或赔偿责任。',
        ),
        (
            '06',
            '违约责任',
            '承租方提前退租应提前 30 日书面告知，押金不予退还；承租方逾期支付租金超过 7 日，按应付金额每日万分之五支付违约金。',
        ),
        (
            '07',
            '争议解决',
            '本合同履行过程中如发生争议，双方应友好协商解决；协商不成的，任何一方均可向房屋所在地有管辖权的人民法院提起诉讼。',
        ),
    ]


@login_required
def contract_list(request):
    """合同列表：租客查看本人申请的合同，房东查看自家房源相关的合同，按签署状态分组。"""
    user = request.user
    if user.is_landlord:
        queryset = RentalApplication.objects.filter(
            listing__owner=user
        ).select_related('listing', 'listing__owner', 'user', 'user__profile')
        listings = Listing.objects.filter(owner=user, is_deleted=False).order_by('-created_at')
        listing_id = request.GET.get('listing')
        if listing_id and listing_id.isdigit():
            queryset = queryset.filter(listing_id=int(listing_id))
        context = {
            'is_landlord_view': True,
            'listings': listings,
            'selected_listing': listing_id or '',
        }
    else:
        queryset = RentalApplication.objects.filter(user=user).select_related(
            'listing', 'listing__owner', 'listing__owner__profile'
        )
        context = {'is_landlord_view': False}

    context['pending_apps'] = queryset.filter(status=RentalApplication.STATUS_PENDING)
    context['signed_apps'] = queryset.filter(status=RentalApplication.STATUS_SIGNED)
    return render(request, 'contracts/list.html', context)


@login_required
def contract_view(request, pk):
    application = get_object_or_404(
        RentalApplication.objects.select_related(
            'listing', 'listing__owner', 'listing__owner__profile', 'user', 'user__profile'
        ),
        pk=pk,
    )
    if application.user_id != request.user.id and application.listing.owner_id != request.user.id:
        raise PermissionDenied('只能查看本人相关的租房合同')
    clauses = _clauses(application, application.listing)
    return render(
        request,
        'contracts/contract.html',
        {
            'application': application,
            'listing': application.listing,
            'clauses': clauses,
            'is_applicant': application.user_id == request.user.id,
            'signed': application.status == RentalApplication.STATUS_SIGNED,
            'just_signed': request.GET.get('signed') == '1',
            'min_start_date': date.today().isoformat(),
            'month_options': [3, 6, 12, 24, 36],
        },
    )


@login_required
@require_POST
def sign_contract(request, pk):
    application = get_object_or_404(
        RentalApplication.objects.select_related('listing'), pk=pk
    )
    if application.user_id != request.user.id:
        raise PermissionDenied('只能签署自己的租房申请')

    if application.status == RentalApplication.STATUS_SIGNED:
        messages.info(request, '该合同已签署，无需重复提交')
        return redirect('contracts:contract', pk=application.pk)

    try:
        start_date = date.fromisoformat(request.POST.get('start_date', ''))
        months = int(request.POST.get('months', '12'))
    except (TypeError, ValueError):
        messages.error(request, '起租日或租期格式不正确')
        return redirect('contracts:contract', pk=application.pk)
    if start_date < date.today():
        messages.error(request, '起租日不能早于今天')
        return redirect('contracts:contract', pk=application.pk)
    if months < 1 or months > 36:
        messages.error(request, '租期需在 1–36 个月之间')
        return redirect('contracts:contract', pk=application.pk)
    if not request.POST.get('agree'):
        messages.error(request, '请先阅读并勾选同意合同条款')
        return redirect('contracts:contract', pk=application.pk)

    with transaction.atomic():
        locked = (
            RentalApplication.objects.select_for_update()
            .select_related('listing')
            .get(pk=application.pk)
        )
        if locked.status == RentalApplication.STATUS_SIGNED:
            messages.info(request, '该合同已签署，无需重复提交')
            return redirect('contracts:contract', pk=locked.pk)
        locked.start_date = start_date
        locked.months = months
        locked.deposit = locked.listing.rent
        locked.first_payment = _first_payment(locked.listing)
        locked.status = RentalApplication.STATUS_SIGNED
        locked.signed_at = timezone.now()
        locked.save(
            update_fields=['start_date', 'months', 'deposit', 'first_payment', 'status', 'signed_at']
        )
    messages.success(request, '合同签署成功，管家会尽快与你联系')
    return redirect(f'/contracts/{application.pk}/?signed=1')
