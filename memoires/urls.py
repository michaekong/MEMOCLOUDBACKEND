# memoires/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    MemoireViewSet,
    EncadrementViewSet,
    MemoireBulkCSVView,
    MemoireSearchView,
    TopDownloadedView,
    TopRatedView,
    AuteurDashboardView,
    UniversiteDashboardView,
    ExportMemoiresCSVView,
    SignalementView,
    MemoireHistoryView,
    MemoirePreviewView,
    BatchUploadView,
    MemoireCreateInUniversiteView,
    GlobalStatsView,
    NotationViewSet,
)

router = DefaultRouter()
router.register(r'memoires', MemoireViewSet, basename='memoire')
router.register(r'encadrements', EncadrementViewSet, basename='encadrement')
router.register(r'notations', NotationViewSet, basename='notation')
app_name = 'memoires'

urlpatterns = [
    path('', include(router.urls)),

    # 1. Batch CSV
    path('batch-csv/', MemoireBulkCSVView.as_view(), name='memoire-batch-csv'),

    # 2. Recherche full-text
    path('search/', MemoireSearchView.as_view(), name='memoire-search'),
 path('<slug:univ_slug>/memoires/', MemoireCreateInUniversiteView.as_view(), name='memoire-create-in-univ'),
    # 3. Top mémoires
    path('top-downloaded/', TopDownloadedView.as_view(), name='memoire-top-downloaded'),
    path('top-rated/', TopRatedView.as_view(), name='memoire-top-rated'),

    # 4. Tableaux de bord
    path('dashboard/mes-memoires/', AuteurDashboardView.as_view(), name='auteur-dashboard'),
    path('dashboard/universite/<int:pk>/', UniversiteDashboardView.as_view(), name='univ-dashboard'),

    # 5. Export CSV
    path('export/csv/', ExportMemoiresCSVView.as_view(), name='memoire_export_csv'),

    # 6. Signalement
    path('<int:pk>/signaler/', SignalementView.as_view(), name='memoire-signaler'),
    # 7. Historique
    path('<int:pk>/history/', MemoireHistoryView.as_view(), name='memoire-history'),

    # 8. Prévisualisation PDF
    path('<int:pk>/preview/', MemoirePreviewView.as_view(), name='memoire-preview'),

    # 9. Batch ZIP upload
    path('batch-zip/', BatchUploadView.as_view(), name='memoire-batch-zip'),

    # 10. Stats globales
    path('stats/global/', GlobalStatsView.as_view(), name='memoire-global-stats'),
]