from rest_framework import permissions
from django.contrib.auth import get_user_model

User = get_user_model()


# ------------------------------------------------------------------
# 1. Rôle dans une université spécifique liée au mémoire
# ------------------------------------------------------------------
class HasRoleInUniversite(permissions.BasePermission):
    """
    Autorise si l’utilisateur a l’un des rôles listés
    dans l'université spécifiée.
    """

    role_list = ["admin", "superadmin", "bigboss", "professeur"]

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        universite_id = view.kwargs.get(
            "universite_id"
        )  # Récupération de l'ID de l'université
        if universite_id:
            return obj.universites.filter(
                id=universite_id,
                roles__utilisateur=request.user,
                roles__role__in=self.role_list,
            ).exists()
        return False


# ------------------------------------------------------------------
# 2. Admin d’une université spécifique liée
# ------------------------------------------------------------------
class IsAdminInUniversite(permissions.BasePermission):
    role_list = ["admin", "superadmin", "bigboss"]

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        universite_id = view.kwargs.get("universite_id")
        if universite_id:
            return obj.universites.filter(
                id=universite_id,
                roles__utilisateur=request.user,
                roles__role__in=self.role_list,
            ).exists()
        return False


# ------------------------------------------------------------------
# 3. Super Admin d’une université spécifique liée
# ------------------------------------------------------------------
class IsSuperAdminInUniversite(permissions.BasePermission):
    role_list = ["superadmin", "bigboss"]

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        universite_id = view.kwargs.get("universite_id")
        if universite_id:
            return obj.universites.filter(
                id=universite_id,
                roles__utilisateur=request.user,
                roles__role__in=self.role_list,
            ).exists()
        return False


# ------------------------------------------------------------------
# 4. Auteur du mémoire OU admin d'une université spécifique
# ------------------------------------------------------------------
class IsAuteurOrAdminInUniversite(permissions.BasePermission):

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        universite_id = view.kwargs.get("universite_id")
        if universite_id:
            # Écriture : auteur OU admin d'une université liée
            if request.method in permissions.SAFE_METHODS:
                return True
            if obj.auteur == request.user:
                return True
            return obj.universites.filter(
                id=universite_id,
                roles__utilisateur=request.user,
                roles__role__in=["admin", "superadmin", "bigboss"],
            ).exists()
        return False
class IsAdminInUniversite(permissions.BasePermission):
    """
    Autorise l'accès uniquement aux administrateurs d'une université spécifiée.
    """
    def has_permission(self, request, view):
        # Vérifie si l'utilisateur est authentifié
        
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        universite_slug = view.kwargs.get('univ_slug')
        if universite_slug:
            # Vérifie que l'utilisateur a le rôle admin pour cette université
            return obj.universites.filter(
                slug=universite_slug,
                roles__utilisateur=request.user,
                roles__role__in=['admin', 'superadmin', 'bigboss']
            ).exists()
            
        return False