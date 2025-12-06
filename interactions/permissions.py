# interactions/permissions.py
from rest_framework import permissions


class IsAuthenticated(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsAdminOrModerateur(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_staff or request.user.groups.filter(name='moderateur').exists()
class IsAdminOfUniversite(permissions.BasePermission):
    admin_roles = {'admin', 'superadmin', 'bigboss'}

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        slug = view.kwargs.get('univ_slug')
        return permissions.models.RoleUniversite.objects.filter(
            utilisateur=request.user,
            universite__slug=slug,
            role__in=self.admin_roles
        ).exists()    