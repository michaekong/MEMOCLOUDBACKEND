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
    RegisterViaUniversiteView,
    UniversiteUsersListView,
    UniversiteUserAddView,
    UniversiteInviteUserView,
    JoinWithCodeView,
    UniversiteUserRemoveView,
    UniversiteUserRoleUpdateView,
    UniversiteUsersExportCSVView,
    UniversiteTopContribView,
    UniversiteUserSearchView,
    UniversiteAnnuaireView,
    CurrentUserView,
    UniversiteUsersStatsView,
    UniversiteBulkCodesView,
    UserProfileView,
)

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")  # CRUD complet

app_name = "users"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-email/", VerifyEmailView.as_view(), name="verify-email"),
    path("login/", LoginView.as_view(), name="login"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path(
        "reset-password/",
        ResetPasswordRequestView.as_view(),
        name="reset-password-request",
    ),
    path(
        "reset-password/confirm/",
        ResetPasswordConfirmView.as_view(),
        name="reset-password-confirm",
    ),
    path("users/search/", GetUserByEmailView.as_view(), name="user-by-email"),
    path("users/<int:pk>/role/", RoleUpdateView.as_view(), name="user-role-update"),
    path("users/deactivate/", DeactivateAccountView.as_view(), name="user-deactivate"),
    path(
        "<slug:univ_slug>/register/",
        RegisterViaUniversiteView.as_view(),
        name="register_via_univ",
    ),
    # 1.  Liste paginée des membres
    path(
        "<slug:univ_slug>/users/",
        UniversiteUsersListView.as_view(),
        name="univ-users-list",
    ),
    # 2.  Ajouter un compte EXISTANT
    path(
        "<slug:univ_slug>/users/add/",
        UniversiteUserAddView.as_view(),
        name="univ-user-add",
    ),
        path('<slug:univ_slug>/users/profile/<int:pk>/', UserProfileView.as_view(), name='user-profile'),

    # 3.  Inviter un nouvel utilisateur (code chiffré + rôle prédéfini)
    path(
        "<slug:univ_slug>/users/invite/",
        UniversiteInviteUserView.as_view(),
        name="univ-user-invite",
    ),
    # 4.  Rejoindre avec le code (public)
    path("join-with-code/", JoinWithCodeView.as_view(), name="join-with-code"),
    # 5.  Retirer / bannir un membre
    path(
        "<slug:univ_slug>/users/<int:user_id>/",
        UniversiteUserRemoveView.as_view(),
        name="univ-user-remove",
    ),
    # 6.  Changer le rôle d’un membre
    path(
        "<slug:univ_slug>/users/<int:user_id>/role/",
        UniversiteUserRoleUpdateView.as_view(),
        name="univ-user-role-update",
    ),
    # 7.  Exporter CSV
    path(
        "<slug:univ_slug>/users/export/csv/",
        UniversiteUsersExportCSVView.as_view(),
        name="univ-users-export-csv",
    ),
    # 8.  Top contributeurs
    path(
        "<slug:univ_slug>/users/top-contrib/",
        UniversiteTopContribView.as_view(),
        name="univ-top-contrib",
    ),
    # 9.  Recherche rapide
    path(
        "<slug:univ_slug>/users/search/",
        UniversiteUserSearchView.as_view(),
        name="univ-user-search",
    ),
    # 10. Annuaire public (cards)
    path(
        "<slug:univ_slug>/users/annuaire/",
        UniversiteAnnuaireView.as_view(),
        name="univ-annuaire",
    ),
    # inclusion du router (obligatoire pour Swagger)
    path("", include(router.urls)),
    path(
        "<slug:univ_slug>/users/stats/",
        UniversiteUsersStatsView.as_view(),
        name="univ-users-stats",
    ),
    path(
        "<slug:univ_slug>/users/bulk-codes/",
        UniversiteBulkCodesView.as_view(),
        name="univ-bulk-codes",
    ),
    path('me/', CurrentUserView.as_view(), name='current-user'),
]
