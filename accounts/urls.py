from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('resend-otp/', views.resend_otp_view, name='resend_otp'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('password-reset/', views.password_reset_view, name='password_reset'),
    path('password-reset/verify/', views.password_reset_verify_view, name='reset_password_verify'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/update/', views.profile_update_view, name='profile_update'),
    path('profile/id-card/', views.id_card_update_view, name='id_card_update'),
    path('profile/change-password/', views.change_password_view, name='change_password'),
    path('id-card/<str:side>/', views.id_card_view, name='id_card'),
    path('id-card/<int:profile_id>/<str:side>/', views.id_card_view, name='id_card_admin'),
]
