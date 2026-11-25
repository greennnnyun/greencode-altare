from django.urls import path

from . import views

app_name = 'contracts'

urlpatterns = [
    path('', views.contract_list, name='list'),
    path('apply/<int:listing_id>/', views.apply_rental, name='apply'),
    path('<int:pk>/', views.contract_view, name='contract'),
    path('<int:pk>/sign/', views.sign_contract, name='sign'),
]
