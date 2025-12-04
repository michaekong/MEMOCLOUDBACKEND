# admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import CustomUser, InvitationCode


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    # Affichage liste
    list_display = ("email", "nom", "prenom", "sexe", "type", "is_active", "date_joined")
    list_filter = ("type", "sexe", "is_active", "date_joined")
    search_fields = ("email", "nom", "prenom")
    ordering = ("-date_joined",)

    # Formulaire d’édition
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Personal info"),
            {"fields": ("nom", "prenom", "sexe", "realisation_linkedin", "photo_profil")},
        ),
        (_("Permissions"), {"fields": ("is_active", "is_staff", "is_superuser")}),
        (_("Important dates"), {"fields": ("date_joined",)}),
        (_("Role"), {"fields": ("type",)}),
    )

    # Formulaire de création
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "nom",
                    "prenom",
                    "sexe",
                    "type",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    # Empêche l’édition directe du mot de passe
    readonly_fields = ("date_joined",)


from django.contrib import admin


class InvitationCodeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "universite",
        "role",
        "created_by",
        "used_by",
        "created_at",
        "expires_at",
        "is_expired",
        "is_used",
    )
    readonly_fields = ("code", "created_at", "expires_at", "is_expired", "is_used")
    list_filter = ("universite", "role", "created_by", "used_by", "created_at")
    search_fields = ("code", "created_by__email", "used_by__email")

    def get_queryset(self, request):
        # Custom query set if needed
        queryset = super().get_queryset(request)
        return queryset

    def mark_used(self, request, queryset):
        """Marque les codes comme utilisés par l'utilisateur sélectionné."""
        for invitation in queryset:
            invitation.mark_used(request.user)

    mark_used.short_description = "Marquer comme utilisé"

    actions = [mark_used]


admin.site.register(InvitationCode, InvitationCodeAdmin)
