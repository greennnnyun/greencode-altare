from django.db.models import Q

from .models import Conversation


def conversations_for(user):
    """该用户可见的会话列表：清空过、且清空之后没有新消息的会话不返回。"""
    queryset = (
        Conversation.objects.filter(Q(tenant=user) | Q(landlord=user))
        .select_related('listing', 'tenant', 'tenant__profile', 'landlord', 'landlord__profile')
        .order_by('-created_at')
    )
    return [conversation for conversation in queryset if conversation.has_visible_content(user)]


def total_unread(user):
    return sum(conversation.unread_for(user) for conversation in conversations_for(user))


def unread_counter(request):
    if not request.user.is_authenticated:
        return {'nav_unread': 0}
    return {'nav_unread': total_unread(request.user)}
