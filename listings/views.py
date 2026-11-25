from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ListingForm
from .images import delete_listing_image, save_listing_images
from .models import HOUSE_TYPES, PAYMENT_CHOICES, Favorite, Listing, Region


def _landlord_only(request):
    if not request.user.is_landlord:
        raise PermissionDenied('仅房东账号可以管理房源')


def _parse_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def home(request):
    queryset = Listing.objects.filter(is_deleted=False, status=Listing.STATUS_LISTED).select_related(
        'owner', 'owner__profile', 'province', 'city', 'district'
    )
    city_code = (request.GET.get('city') or '').strip()
    district_code = (request.GET.get('district') or '').strip()
    house_type = (request.GET.get('house_type') or '').strip()
    min_rent = _parse_int(request.GET.get('min_rent'))
    max_rent = _parse_int(request.GET.get('max_rent'))
    sort = request.GET.get('sort') or 'new'

    city = Region.objects.filter(code=city_code, level=Region.LEVEL_CITY).first() if city_code else None
    district = (
        Region.objects.filter(code=district_code, level=Region.LEVEL_DISTRICT).first()
        if district_code
        else None
    )
    # 非法/不匹配的 code 一律忽略，不报错也不串数据
    if district is not None and city is not None and district.parent_id != city.id:
        district = None
    if city is not None:
        queryset = queryset.filter(city=city)
    if district is not None:
        queryset = queryset.filter(district=district)
    if house_type in dict(HOUSE_TYPES):
        queryset = queryset.filter(house_type=house_type)
    if min_rent is not None:
        queryset = queryset.filter(rent__gte=min_rent)
    if max_rent is not None:
        queryset = queryset.filter(rent__lte=max_rent)
    queryset = queryset.order_by(
        {'price_asc': 'rent', 'price_desc': '-rent'}.get(sort, '-created_at')
    )

    favorites = set()
    if request.user.is_authenticated:
        favorites = set(
            Favorite.objects.filter(user=request.user, listing__in=queryset).values_list(
                'listing_id', flat=True
            )
        )

    query_string = request.GET.copy()
    query_string.pop('page', None)
    if query_string:
        query_string.pop('submit', None)

    listings = list(queryset)
    for item in listings:
        item.favorited = item.pk in favorites

    district_options = city.children.order_by('code') if city else Region.objects.none()

    return render(
        request,
        'listings/home.html',
        {
            'listings': listings,
            'result_count': len(listings),
            'favorites': favorites,
            'city_groups': _city_groups(),
            'district_options': district_options,
            'house_types': HOUSE_TYPES,
            'filters': {
                'city': city_code if city else '',
                'district': district_code if district else '',
                'house_type': house_type,
                'min_rent': request.GET.get('min_rent', ''),
                'max_rent': request.GET.get('max_rent', ''),
                'sort': sort,
            },
            'querystring': query_string.urlencode(),
        },
    )


def _city_groups():
    """按省分组返回地级市，供下拉框 optgroup 使用（固定 2 次查询）。"""
    provinces = list(Region.objects.filter(level=Region.LEVEL_PROVINCE).order_by('code'))
    cities = list(Region.objects.filter(level=Region.LEVEL_CITY).order_by('code'))
    grouped = {province.pk: [] for province in provinces}
    for city in cities:
        grouped.setdefault(city.parent_id, []).append(city)
    return [
        {'province': province, 'cities': grouped.get(province.pk, [])}
        for province in provinces
    ]


def region_options(request):
    """HTMX 片段：返回某一行政级别下的 <option> 列表。

    - /listings/regions/?city=<code>        → 该市下辖区县（首页筛选）
    - /listings/regions/?level=2&province=  → 该省下辖城市（发布表单）
    - /listings/regions/?level=3&city=      → 该市下辖区县（发布表单）
    """
    try:
        level = int(request.GET.get('level') or Region.LEVEL_DISTRICT)
    except (TypeError, ValueError):
        level = Region.LEVEL_DISTRICT
    if level not in (Region.LEVEL_CITY, Region.LEVEL_DISTRICT):
        level = Region.LEVEL_DISTRICT

    parent_code = (
        request.GET.get('parent')
        or request.GET.get('city')
        or request.GET.get('province')
        or ''
    ).strip()

    regions = Region.objects.filter(level=level)
    if parent_code:
        regions = regions.filter(parent__code=parent_code)
    else:
        regions = Region.objects.none()

    return render(
        request,
        'listings/partials/region_options.html',
        {
            'regions': regions.order_by('code'),
            'placeholder': '请选择城市' if level == Region.LEVEL_CITY else '全部区域',
            'selected': (request.GET.get('selected') or '').strip(),
        },
    )


def listing_detail(request, pk):
    listing = get_object_or_404(
        Listing.objects.select_related(
            'owner', 'owner__profile', 'province', 'city', 'district'
        ),
        pk=pk,
        is_deleted=False,
    )
    is_owner = request.user.is_authenticated and listing.owner_id == request.user.id
    if listing.status != Listing.STATUS_LISTED and not is_owner and not request.user.is_staff:
        messages.error(request, '该房源当前不可对外展示')
        return redirect('listings:home')

    favorited = False
    existing_application = None
    viewing_form = None
    if request.user.is_authenticated:
        favorited = Favorite.objects.filter(user=request.user, listing=listing).exists()
        from bookings.forms import ViewingForm

        profile = getattr(request.user, 'profile', None)
        viewing_form = ViewingForm(
            initial={
                'name': (profile.display_name if profile else request.user.email),
                'phone': (profile.phone if profile else ''),
            }
        )
        from contracts.models import RentalApplication

        existing_application = RentalApplication.objects.filter(
            user=request.user, listing=listing
        ).first()

    related = list(
        Listing.objects.filter(
            is_deleted=False,
            status=Listing.STATUS_LISTED,
            city=listing.city,
            district=listing.district,
        )
        .select_related('province', 'city', 'district')
        .exclude(pk=listing.pk)
        .order_by('-created_at')[:3]
    )
    if request.user.is_authenticated:
        related_favorites = set(
            Favorite.objects.filter(user=request.user, listing__in=related).values_list(
                'listing_id', flat=True
            )
        )
        for item in related:
            item.favorited = item.pk in related_favorites
    else:
        for item in related:
            item.favorited = False

    return render(
        request,
        'listings/detail.html',
        {
            'listing': listing,
            'is_owner': is_owner,
            'favorited': favorited,
            'viewing_form': viewing_form,
            'existing_application': existing_application,
            'related': related,
            'can_apply': request.user.is_authenticated
            and request.user.is_tenant
            and not is_owner
            and listing.status == Listing.STATUS_LISTED,
            'can_contact': request.user.is_authenticated and not is_owner,
        },
    )


@login_required
@require_POST
def favorite_toggle(request, pk):
    listing = get_object_or_404(Listing, pk=pk, is_deleted=False)
    action = request.POST.get('action', 'add')
    if action == 'remove':
        Favorite.objects.filter(user=request.user, listing=listing).delete()
        favorited = False
    else:
        Favorite.objects.get_or_create(user=request.user, listing=listing)
        favorited = True
    mode = request.POST.get('mode', 'card')
    if request.headers.get('HX-Request'):
        # 收藏页点「取消收藏」时整张卡片一起撤掉，并联动更新统计与空分区
        if mode == 'favorites' and not favorited:
            remaining = Favorite.objects.filter(
                user=request.user, listing__is_deleted=False
            )
            total_count = remaining.count()
            if total_count == 0:
                response = HttpResponse('')
                response['HX-Refresh'] = 'true'
                return response
            available_count = remaining.filter(
                listing__status=Listing.STATUS_LISTED
            ).count()
            return render(
                request,
                'listings/partials/favorite_removed.html',
                {
                    'total_count': total_count,
                    'available_count': available_count,
                    'unavailable_count': total_count - available_count,
                },
            )
        return render(
            request,
            'listings/partials/favorite_button.html',
            {
                'listing': listing,
                'favorited': favorited,
                'mode': mode,
            },
        )
    return redirect('listings:detail', pk=listing.pk)


@login_required
def my_favorites(request):
    """我的收藏：按收藏时间倒序，可租房源与已下架/已租出房源分区展示。"""
    rows = list(
        Favorite.objects.filter(user=request.user, listing__is_deleted=False)
        .select_related(
            'listing',
            'listing__owner',
            'listing__owner__profile',
            'listing__province',
            'listing__city',
            'listing__district',
        )
        .order_by('-created_at')
    )

    available, unavailable = [], []
    for row in rows:
        listing = row.listing
        listing.favorited = True
        listing.favorited_at = row.created_at
        (available if listing.is_listed else unavailable).append(listing)

    return render(
        request,
        'listings/favorites.html',
        {
            'available_listings': available,
            'unavailable_listings': unavailable,
            'total_count': len(rows),
        },
    )


@login_required
def landlord_listings(request):
    _landlord_only(request)
    listings = (
        Listing.objects.filter(owner=request.user, is_deleted=False)
        .select_related('owner', 'province', 'city', 'district')
        .order_by('-created_at')
    )
    return render(request, 'listings/landlord_list.html', {'listings': listings})


@login_required
def listing_create(request):
    _landlord_only(request)
    form = ListingForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        files = request.FILES.getlist('images')
        try:
            paths = save_listing_images(files)
            if not paths:
                raise ValidationError('请至少上传 1 张房源图片')
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            listing = form.save(commit=False)
            listing.owner = request.user
            listing.images = paths
            listing.save()
            messages.success(request, '房源已发布，租客马上就能在广场看到它')
            return redirect('listings:landlord_listings')
    return render(
        request,
        'listings/listing_form.html',
        {'form': form, 'mode': 'create', 'existing_images': [], 'payment_choices': PAYMENT_CHOICES},
    )


@login_required
def listing_edit(request, pk):
    _landlord_only(request)
    listing = get_object_or_404(Listing, pk=pk, is_deleted=False)
    if listing.owner_id != request.user.id:
        raise PermissionDenied('只能编辑自己的房源')
    form = ListingForm(request.POST or None, instance=listing)
    existing_images = list(listing.images or [])
    if request.method == 'POST' and form.is_valid():
        remove = [path for path in request.POST.getlist('remove_images') if path in existing_images]
        remaining = [path for path in existing_images if path not in remove]
        try:
            new_paths = save_listing_images(request.FILES.getlist('new_images'), remaining)
            if not remaining and not new_paths:
                raise ValidationError('房源至少需要保留 1 张图片')
        except ValidationError as exc:
            form.add_error(None, exc)
            existing_images = remaining
        else:
            listing = form.save(commit=False)
            listing.images = remaining + new_paths
            listing.save()
            for path in remove:
                delete_listing_image(path)
            messages.success(request, '房源信息已更新')
            return redirect('listings:landlord_listings')
    return render(
        request,
        'listings/listing_form.html',
        {
            'form': form,
            'mode': 'edit',
            'listing': listing,
            'existing_images': existing_images,
            'payment_choices': PAYMENT_CHOICES,
        },
    )


@login_required
@require_POST
def listing_delete(request, pk):
    _landlord_only(request)
    listing = get_object_or_404(Listing, pk=pk, is_deleted=False)
    if listing.owner_id != request.user.id:
        raise PermissionDenied('只能删除自己的房源')
    listing.is_deleted = True
    listing.save(update_fields=['is_deleted'])
    messages.success(request, '房源已删除（历史合同与消息已保留）')
    return redirect('listings:landlord_listings')


@login_required
@require_POST
def listing_status(request, pk):
    _landlord_only(request)
    listing = get_object_or_404(Listing, pk=pk, is_deleted=False)
    if listing.owner_id != request.user.id:
        raise PermissionDenied('只能操作自己的房源')
    action = request.POST.get('action')
    if action == 'off' and listing.status == Listing.STATUS_LISTED:
        listing.status = Listing.STATUS_OFF
        listing.save(update_fields=['status'])
        messages.success(request, '房源已下架')
    elif action == 'relist' and listing.status in {Listing.STATUS_OFF, Listing.STATUS_RENTED}:
        listing.status = Listing.STATUS_LISTED
        listing.save(update_fields=['status'])
        messages.success(request, '房源已重新上架')
    elif action == 'rented' and listing.status == Listing.STATUS_LISTED:
        from bookings.models import Viewing

        with transaction.atomic():
            listing.status = Listing.STATUS_RENTED
            listing.save(update_fields=['status'])
            Viewing.objects.filter(listing=listing, status=Viewing.STATUS_PENDING).update(
                status=Viewing.STATUS_CANCELLED
            )
        messages.success(request, '已标记为租出，待确认的预约已自动取消')
    else:
        return HttpResponseBadRequest('无效的状态操作')
    return redirect('listings:landlord_listings')
