from django.urls import path

from . import views

app_name = 'bookings'

urlpatterns = [
    path('create/<int:listing_id>/', views.create_viewing, name='create'),
    path('mine/', views.my_viewings, name='mine'),
    path('manage/', views.manage_viewings, name='manage'),
    path('<int:pk>/cancel/', views.cancel_viewing, name='cancel'),
    path('<int:pk>/update/', views.update_viewing, name='update'),
]
