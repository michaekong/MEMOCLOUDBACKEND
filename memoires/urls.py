# memoires/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UniversiteMemoireViewSet,
    MemoireAnneesView,
    MemoireEncadrementView,
    AuteurDashboardView,
    CommentaireListView,
    MemoirePreviewImageView,
)

router = DefaultRouter()
router.register(r'memoires', UniversiteMemoireViewSet, basename='univ-memoire')

urlpatterns = [
    # 1️⃣ routes précises (pas de collision)
    path('universites/<slug:univ_slug>/memoires/annees/', MemoireAnneesView.as_view(), name='memoire-annees'),
    path('universites/<slug:univ_slug>/memoires/mes-stats/', AuteurDashboardView.as_view(), name='auteur-dashboard'),
    path('universites/<slug:univ_slug>/memoires/<int:pk>/preview/image/', MemoirePreviewImageView.as_view(), name='memoire-preview-image'),
    path('universites/<slug:univ_slug>/memoires/<int:pk>/encadrer/', MemoireEncadrementView.as_view(), name='memoire-encadrement'),
    path('universites/<slug:univ_slug>/', include(router.urls)),
     path('universites/<slug:univ_slug>/stats/', UniversiteMemoireViewSet.as_view({'get': 'stats'}), name='univ-memoire-stats'),
    path(
        "universites/<str:univ_slug>/memoires/<int:memoire_id>/commentaires/",
        
        CommentaireListView.as_view(),
        name="commentaire-list",
    ),
    
   ]