# universites/urls.py
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
    BulkDeleteUniversitesView,
    ExportUniversitesCSVView,
    DomaineSuggestView,
    DomaineByUniversiteListView,
)

router = DefaultRouter()
router.register(r'universites', UniversiteViewSet, basename='universite')
router.register(r'domaines', DomaineViewSet, basename='domaine')
router.register(r'roles', RoleUniversiteViewSet, basename='role-universite')

app_name = 'universites'

urlpatterns = [
    path('', include(router.urls)),
    # ------- extensions sans attendre memoires -------
    path('universites/<int:pk>/stats/', UniversiteStatsView.as_view(), name='univ-stats'),
    path('universites/<int:pk>/upload-logo/', LogoUploadView.as_view(), name='univ-logo-upload'),
    path('universites/<int:pk>/delete-logo/', LogoDeleteView.as_view(), name='univ-logo-delete'),
    path('universites/<int:pk>/membres/', MembresListView.as_view(), name='univ-membres'),
    path('universites/<int:pk>/membres/<int:user_id>/role/', MembreRoleUpdateView.as_view(), name='univ-membre-role'),
    path('universites/<int:pk>/membres/<int:user_id>/', MembreRemoveView.as_view(), name='univ-membre-remove'),
    path('universites/bulk-delete/', BulkDeleteUniversitesView.as_view(), name='univ-bulk-delete'),
    path('universites/export/csv/', ExportUniversitesCSVView.as_view(), name='univ-export-csv'),
    # ------- domaines extensions -------
    path('domaines/suggest/', DomaineSuggestView.as_view(), name='domaine-suggest'),
    path('universites/<int:pk>/domaines/', DomaineByUniversiteListView.as_view(), name='univ-domaines'),
]