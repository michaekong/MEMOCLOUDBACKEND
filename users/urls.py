# users/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView,
    VerifyEmailView,
    LoginView,
    ProfileView,
    ChangePasswordView,
    ResetPasswordRequestView,
    ResetPasswordConfirmView,
    GetUserByEmailView,
    RoleUpdateView,
    DeactivateAccountView,
    UserViewSet,
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')  # CRUD complet

app_name = 'users'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('login/', LoginView.as_view(), name='login'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('reset-password/', ResetPasswordRequestView.as_view(), name='reset-password-request'),
    path('reset-password/confirm/', ResetPasswordConfirmView.as_view(), name='reset-password-confirm'),
    path('users/search/', GetUserByEmailView.as_view(), name='user-by-email'),
    path('users/<int:pk>/role/', RoleUpdateView.as_view(), name='user-role-update'),
    path('users/deactivate/', DeactivateAccountView.as_view(), name='user-deactivate'),

    # inclusion du router (obligatoire pour Swagger)
    path('', include(router.urls)),
]