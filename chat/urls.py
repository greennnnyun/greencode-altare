from django.urls import path

from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('start/<int:listing_id>/', views.start_conversation, name='start'),
    path('<int:conversation_id>/send/', views.send_message, name='send'),
    path('<int:conversation_id>/clear/', views.clear_conversation, name='clear'),
    path('<int:conversation_id>/poll/', views.poll_messages, name='poll'),
]
