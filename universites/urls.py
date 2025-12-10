from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UniversiteViewSet,
    DomaineViewSet,
    RoleUniversiteViewSet,
    UniversiteStatsView,
    LogoUploadView,
    LogoDeleteView,
    MembresListView,
    MembreRoleUpdateView,
    MembreRemoveView,
    UserRoleInUniversityByIdView,
    DomaineCreateInUniversiteView,
    BulkDeleteUniversitesView,
    ExportUniversitesCSVView,
    DomaineSuggestView,
    NewsGlobalViewSet,
    NewsBySlugViewSet,
    DomaineDestroyInUniversiteView,
    DomaineByUniversiteListView,
    UserRoleInUniversityView,
)

# ----------  Routes manuelles pour News par SLUG  ----------
news_by_slug_list = NewsBySlugViewSet.as_view({
    'get': 'list',
    'post': 'create'
})
news_by_slug_detail = NewsBySlugViewSet.as_view({
    'get': 'retrieve',
    'put': 'update',
    'patch': 'partial_update',
    'delete': 'destroy'
})

# ----------  Router pour les routes globales (sans slug)  ----------
router = DefaultRouter()
router.register(r"universites", UniversiteViewSet, basename="universite")
router.register(r"domaines", DomaineViewSet, basename="domaine")
router.register(r"roles", RoleUniversiteViewSet, basename="role-universite")
router.register(r'news', NewsGlobalViewSet, basename='news-global')  # CRUD global

app_name = "universites"

urlpatterns = [
    # 1. Routes manuelles (prioritaires) : CRUD news par université
    path('universities/<slug:slug>/news/', news_by_slug_list, name='news-by-slug-list'),
    path('universities/<slug:slug>/news/<int:pk>/', news_by_slug_detail, name='news-by-slug-detail'),

    # 2. Routes globales (via router)
    path("", include(router.urls)),

    # 3. Autres routes existantes
    path("universites/<int:pk>/stats/", UniversiteStatsView.as_view(), name="univ-stats"),
    path("universites/<int:pk>/upload-logo/", LogoUploadView.as_view(), name="univ-logo-upload"),
    path("universites/<int:pk>/delete-logo/", LogoDeleteView.as_view(), name="univ-logo-delete"),
    path("universites/<int:pk>/membres/", MembresListView.as_view(), name="univ-membres"),
    path("universites/<int:pk>/membres/<int:user_id>/role/", MembreRoleUpdateView.as_view(), name="univ-membre-role"),
    path("universites/<int:pk>/membres/<int:user_id>/", MembreRemoveView.as_view(), name="univ-membre-remove"),
    path("universites/bulk-delete/", BulkDeleteUniversitesView.as_view(), name="univ-bulk-delete"),
    path("universites/export/csv/", ExportUniversitesCSVView.as_view(), name="univ-export-csv"),
       path('universites/<slug:univ_slug>/domaines/', DomaineByUniversiteListView.as_view(), name='univ-domaines'),
    path('universites/<slug:univ_slug>/domaines/create/', DomaineCreateInUniversiteView.as_view(), name='domaine-create-in-univ'),
    path('universites/<str:univ_slug>/domaines/<str:domaine_slug>/', DomaineDestroyInUniversiteView.as_view(), name='destroy_domaine_in_universite'),
    path('domaines/suggest/', DomaineSuggestView.as_view(), name='domaine-suggest'),
 path("auth/<str:univ_slug>/my-role/", UserRoleInUniversityView.as_view(), name="user-role-in-university"),
    path("auth/universities/<str:univ_slug>/user-role/<int:user_id>/", UserRoleInUniversityByIdView.as_view(), name="user-role-in-university-by-id"),
]