from rest_framework import permissions
from universites.models import RoleUniversite
from django.contrib.auth import get_user_model
User = get_user_model()

class IsAuthenticated(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsMemberOfUniversite(permissions.BasePermission):
    """Au moins un rôle (quel qu’il soit) dans l’université slug."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        slug = view.kwargs.get('univ_slug')
        return RoleUniversite.objects.filter(
            utilisateur=request.user,
            universite__slug=slug
        ).exists()


class IsAdminOfUniversite(permissions.BasePermission):
    admin_roles = {'admin', 'superadmin', 'bigboss'}
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        slug = view.kwargs.get('univ_slug')
        return RoleUniversite.objects.filter(
            utilisateur=request.user,
            universite__slug=slug,
            role__in=self.admin_roles
        ).exists()
    def has_object_permission(self, request, view, obj):
        slug = view.kwargs.get('univ_slug')
        return obj.universites.filter(
            slug=slug,
            roles__utilisateur=request.user,
            roles__role__in=self.admin_roles
        ).exists()


class IsAuthorOrAdminOfUniversite(permissions.BasePermission):
    admin_roles = {'admin', 'superadmin', 'bigboss'}
    def has_object_permission(self, request, view, obj):
        if obj.auteur == request.user:
            return True
        slug = view.kwargs.get('univ_slug')
        return obj.universites.filter(
            slug=slug,
            roles__utilisateur=request.user,
            roles__role__in=self.admin_roles
        ).exists()