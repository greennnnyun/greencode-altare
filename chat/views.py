from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from listings.models import Listing

from .context_processors import conversations_for, total_unread
from .models import Conversation, Message


def _get_participant_conversation(user, conversation_id):
    conversation = get_object_or_404(
        Conversation.objects.select_related('listing', 'tenant', 'landlord'), pk=conversation_id
    )
    if user.id not in {conversation.tenant_id, conversation.landlord_id}:
        raise PermissionDenied('你不是该会话的参与方')
    return conversation


def _message_payload(message, user):
    return {
        'id': message.id,
        'mine': message.sender_id == user.id,
        'sender': message.sender.profile.display_name
        if hasattr(message.sender, 'profile') and message.sender.profile
        else message.sender.email.split('@')[0],
        'content': message.content,
        'date': message.created_at.astimezone().strftime('%Y-%m-%d'),
        'time': message.created_at.astimezone().strftime('%H:%M'),
    }


def _mark_read(conversation, user):
    latest = conversation.messages.order_by('-id').values_list('id', flat=True).first() or 0
    cursor = conversation.read_cursor(user)
    if latest > cursor:
        setattr(conversation, conversation.read_field(user), latest)
        conversation.save(update_fields=[conversation.read_field(user)])


@login_required
def inbox(request):
    conversations = list(conversations_for(request.user))
    active_id = request.GET.get('c')
    active = None
    chat_messages = []
    if active_id and active_id.isdigit():
        active = _get_participant_conversation(request.user, int(active_id))
        _mark_read(active, request.user)
        chat_messages = list(
            active.visible_messages(request.user)
            .select_related('sender', 'sender__profile')
            .order_by('id')
        )

    contacts = []
    for conversation in conversations:
        last = conversation.last_message(request.user)
        unread = conversation.unread_for(request.user)
        contacts.append(
            {
                'conversation': conversation,
                'other': conversation.other_user(request.user),
                'last': last,
                'unread': unread,
                'active': bool(active and active.id == conversation.id),
            }
        )

    return render(
        request,
        'chat/inbox.html',
        {
            'contacts': contacts,
            'active': active,
            'chat_messages': chat_messages,
            'active_id': active.id if active else 0,
            'active_cleared': bool(active and active.cleared_cursor(request.user) > 0),
            'nav_unread': total_unread(request.user),
        },
    )


@login_required
@require_POST
def start_conversation(request, listing_id):
    listing = get_object_or_404(Listing, pk=listing_id, is_deleted=False)
    if listing.owner_id == request.user.id:
        raise PermissionDenied('房东不能与自己发起会话')
    if not request.user.is_tenant:
        raise PermissionDenied('仅租客账号可以发起与房东的会话')
    conversation, _ = Conversation.objects.get_or_create(
        listing=listing, tenant=request.user, landlord=listing.owner
    )
    return redirect(f'/chat/?c={conversation.id}')


@login_required
@require_POST
def send_message(request, conversation_id):
    conversation = _get_participant_conversation(request.user, conversation_id)
    content = (request.POST.get('content') or '').strip()
    if not content:
        return HttpResponseBadRequest('消息不能为空')
    if len(content) > 2000:
        return HttpResponseBadRequest('单条消息不能超过 2000 字')
    message = Message.objects.create(
        conversation=conversation, sender=request.user, content=content
    )
    return JsonResponse({'ok': True, 'message': _message_payload(message, request.user)})


@login_required
@require_GET
def poll_messages(request, conversation_id):
    conversation = _get_participant_conversation(request.user, conversation_id)
    try:
        after = int(request.GET.get('after', 0))
    except (TypeError, ValueError):
        after = 0
    if after < 0:
        after = 0
    after = max(after, conversation.cleared_cursor(request.user))
    incoming = list(
        conversation.messages.filter(id__gt=after)
        .select_related('sender', 'sender__profile')
        .order_by('id')[:100]
    )
    _mark_read(conversation, request.user)
    cleared = conversation.cleared_cursor(request.user)
    latest = conversation.messages.order_by('-id').values_list('id', flat=True).first() or after
    return JsonResponse(
        {
            'ok': True,
            'messages': [_message_payload(message, request.user) for message in incoming],
            'last_id': max(latest, cleared),
            'unread_total': total_unread(request.user),
            'unread_in_conversation': 0,
        }
    )


@login_required
@require_POST
def clear_conversation(request, conversation_id):
    """清空聊天记录：只清空当前用户这一侧，对方仍可看到全部历史。"""
    conversation = _get_participant_conversation(request.user, conversation_id)
    latest = conversation.messages.order_by('-id').values_list('id', flat=True).first() or 0
    cleared_field = conversation.cleared_field(request.user)
    read_field = conversation.read_field(request.user)
    setattr(conversation, cleared_field, latest)
    setattr(conversation, read_field, latest)
    conversation.save(update_fields=[cleared_field, read_field])
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    return redirect(f'/chat/')
