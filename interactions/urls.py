# interactions/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TelechargementOpenViewSet,
    LikeOpenViewSet,
    CommentaireOpenViewSet,
    UniversiteTelechargementListView,
    UniversiteLikeListView,
    UniversiteCommentaireListView,
    UniversiteNotationListView,
    UniversiteSignalementListView,
    UniversiteInteractionsStatsView,
)

router = DefaultRouter()
router.register(
    r"telechargements", TelechargementOpenViewSet, basename="open-telechargements"
)
router.register(r"likes", LikeOpenViewSet, basename="open-likes")
router.register(r"commentaires", CommentaireOpenViewSet, basename="open-commentaires")
from .views import NotationViewSet, SignalementModerationViewSet


router.register(r"notations", NotationViewSet, basename="univ-notation")
router.register(r"moderation", SignalementModerationViewSet, basename="univ-moderation")
urlpatterns = [
    path(
        "universites/<slug:univ_slug>/interactions/telechargements/",
        UniversiteTelechargementListView.as_view(),
        name="univ-telechargements-list",
    ),
    path(
        "universites/<slug:univ_slug>/interactions/likes/",
        UniversiteLikeListView.as_view(),
        name="univ-likes-list",
    ),
    path(
        "universites/<slug:univ_slug>/interactions/commentaires/",
        UniversiteCommentaireListView.as_view(),
        name="univ-commentaires-list",
    ),
    path(
        "universites/<slug:univ_slug>/interactions/notations/",
        UniversiteNotationListView.as_view(),
        name="univ-notations-list",
    ),
    path(
        "universites/<slug:univ_slug>/interactions/signalements/",
        UniversiteSignalementListView.as_view(),
        name="univ-signalements-list",
    ),
    path(
        "universites/<slug:univ_slug>/interactions/stats/",
        UniversiteInteractionsStatsView.as_view(),
        name="univ-interactions-stats",
    ),
       path('interactions/notations/', NotationViewSet.as_view({'get': 'list', 'post': 'create'}), name='notation-list'),
    path('interactions/notations/par-memoire/<int:memoire_id>/', NotationViewSet.as_view({'get': 'par_memoire'}), name='notation-by-memoire'),
   
    path("", include(router.urls)),
]
