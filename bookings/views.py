import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

from listings.models import Listing

from .forms import ViewingForm
from .models import Viewing

HTMX_TRIGGER = json.dumps({'bookingCreated': {'message': '预约成功，请等待管家联系'}})


def _login_redirect(request):
    if request.headers.get('HX-Request'):
        response = HttpResponse(status=401)
        response['HX-Redirect'] = reverse('accounts:login') + '?' + urlencode(
            {'next': request.get_full_path()}
        )
        return response
    return redirect(reverse('accounts:login') + '?' + urlencode({'next': request.get_full_path()}))


def create_viewing(request, listing_id):
    if not request.user.is_authenticated:
        return _login_redirect(request)
    listing = get_object_or_404(Listing, pk=listing_id, is_deleted=False)
    if not request.user.is_tenant:
        raise PermissionDenied('仅租客账号可以发起看房预约')
    if listing.status != Listing.STATUS_LISTED:
        return HttpResponseBadRequest('该房源当前不可预约（已下架或已租出）')

    if request.method == 'POST':
        form = ViewingForm(request.POST)
        if form.is_valid():
            viewing = form.save(commit=False)
            viewing.user = request.user
            viewing.listing = listing
            viewing.save()
            if request.headers.get('HX-Request'):
                response = HttpResponse(status=204)
                response['HX-Trigger'] = HTMX_TRIGGER
                return response
            messages.success(request, '预约成功，请等待管家联系')
            return redirect('bookings:mine')
        if request.headers.get('HX-Request'):
            return render(
                request,
                'bookings/partials/viewing_form.html',
                {'form': form, 'listing': listing},
                status=200,
            )
    else:
        form = ViewingForm()
    return render(
        request,
        'bookings/create.html',
        {'form': form, 'listing': listing},
    )


@login_required
def my_viewings(request):
    viewings = Viewing.objects.filter(user=request.user).select_related(
        'listing', 'listing__owner'
    )
    return render(request, 'bookings/mine.html', {'viewings': viewings})


@login_required
@require_POST
def cancel_viewing(request, pk):
    viewing = get_object_or_404(Viewing, pk=pk)
    if viewing.user_id != request.user.id:
        raise PermissionDenied('只能取消自己的预约')
    if not viewing.can_cancel:
        messages.error(request, '当前状态不可取消')
    else:
        viewing.status = Viewing.STATUS_CANCELLED
        viewing.save(update_fields=['status'])
        messages.success(request, '预约已取消')
    return redirect('bookings:mine')


@login_required
def manage_viewings(request):
    if not request.user.is_landlord:
        raise PermissionDenied('仅房东账号可以管理预约')
    listings = Listing.objects.filter(owner=request.user, is_deleted=False).order_by('-created_at')
    queryset = Viewing.objects.filter(listing__owner=request.user).select_related(
        'listing', 'user', 'user__profile'
    )
    listing_id = request.GET.get('listing')
    if listing_id and listing_id.isdigit():
        queryset = queryset.filter(listing_id=int(listing_id))
    return render(
        request,
        'bookings/manage.html',
        {
            'viewings': queryset,
            'listings': listings,
            'selected_listing': listing_id or '',
        },
    )


@login_required
@require_POST
def update_viewing(request, pk):
    if not request.user.is_landlord:
        raise PermissionDenied('仅房东账号可以管理预约')
    viewing = get_object_or_404(Viewing, pk=pk)
    if viewing.listing.owner_id != request.user.id:
        raise PermissionDenied('只能处理自己房源的预约')
    action = request.POST.get('action')
    transitions = {
        'confirm': (Viewing.STATUS_PENDING, Viewing.STATUS_CONFIRMED, '预约已确认'),
        'cancel': (Viewing.STATUS_PENDING, Viewing.STATUS_CANCELLED, '预约已取消'),
        'complete': (Viewing.STATUS_CONFIRMED, Viewing.STATUS_COMPLETED, '预约已完成'),
    }
    if action not in transitions:
        return HttpResponseBadRequest('无效的操作')
    required, target, message = transitions[action]
    if viewing.status != required:
        return HttpResponseBadRequest('当前状态不允许该操作')
    viewing.status = target
    viewing.save(update_fields=['status'])
    messages.success(request, message)
    return redirect('bookings:manage')
