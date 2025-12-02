# interactions/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TelechargementViewSet,
    LikeViewSet,
    CommentaireViewSet,
    InteractionsGlobalStatsView,
)

router = DefaultRouter()
router.register(r'telechargements', TelechargementViewSet, basename='telechargement')
router.register(r'likes', LikeViewSet, basename='like')
router.register(r'commentaires', CommentaireViewSet, basename='commentaire')

urlpatterns = [
    path('', include(router.urls)),
    path('stats/global/', InteractionsGlobalStatsView.as_view(), name='interactions-global-stats'),
]