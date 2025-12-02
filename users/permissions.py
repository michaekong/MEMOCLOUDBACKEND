# memoires/permissions.py
from rest_framework import permissions
from django.contrib.auth import get_user_model

User = get_user_model()


# ------------------------------------------------------------------
# 1. Rôle dans au moins une université liée au mémoire
# ------------------------------------------------------------------
class HasRoleInUniversite(permissions.BasePermission):
    """
    Autorise si l’utilisateur a l’un des rôles listés
    dans AU MOINS une des universités du mémoire.
    """
    role_list = ['admin', 'superadmin', 'bigboss', 'professeur']

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # obj = mémoire
        return obj.universites.filter(
            roles__utilisateur=request.user,
            roles__role__in=self.role_list
        ).exists()


# ------------------------------------------------------------------
# 2. Admin (ou plus) d’au moins une université liée
# ------------------------------------------------------------------
class IsAdminInUniversite(permissions.BasePermission):
    role_list = ['admin', 'superadmin', 'bigboss']

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return obj.universites.filter(
            roles__utilisateur=request.user,
            roles__role__in=self.role_list
        ).exists()


# ------------------------------------------------------------------
# 3. Auteur du mémoire OU admin
# ------------------------------------------------------------------
class IsAuteurOrAdminInUniversite(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):
        # Écriture : auteur OU admin d’une univ liée
        if request.method in permissions.SAFE_METHODS:
            return True
        if obj.auteur == request.user:
            return True
        return obj.universites.filter(
            roles__utilisateur=request.user,
            roles__role__in=['admin', 'superadmin', 'bigboss']
        ).exists()