# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

# Router global (vide pour l'instant, prêt à accueillir des ViewSets)
router = DefaultRouter()

urlpatterns = [
    # Accueil → redirige vers Swagger
    path('', RedirectView.as_view(url='/api/docs/swagger/', permanent=False)),

    # Admin Django
    path('admin/', admin.site.urls),

    # Apps métiers
    path('api/auth/', include('users.urls')),
    path('api/docs/', include('api.urls')),          # Swagger / ReDoc
    path('api/universites/', include('universites.urls')),
    path('api/memoires/', include('memoires.urls')),
    path('api/interactions/', include('interactions.urls')),

    # Router global (facultatif, à activer quand tu auras des ViewSets racine)
    # path('api/', include(router.urls)),
]

# Media & Static (uniquement en développement)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)