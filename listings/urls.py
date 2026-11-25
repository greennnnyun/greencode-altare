from django.urls import path

from . import views

app_name = 'listings'

urlpatterns = [
    path('', views.home, name='home'),
    path('listings/regions/', views.region_options, name='region_options'),
    path('favorites/', views.my_favorites, name='my_favorites'),
    path('listings/<int:pk>/', views.listing_detail, name='detail'),
    path('listings/<int:pk>/favorite/', views.favorite_toggle, name='favorite'),
    path('landlord/listings/', views.landlord_listings, name='landlord_listings'),
    path('landlord/listings/new/', views.listing_create, name='listing_create'),
    path('landlord/listings/<int:pk>/edit/', views.listing_edit, name='listing_edit'),
    path('landlord/listings/<int:pk>/delete/', views.listing_delete, name='listing_delete'),
    path('landlord/listings/<int:pk>/status/', views.listing_status, name='listing_status'),
]
