# admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import CustomUser


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
        (_("Personal info"), {"fields": ("nom", "prenom", "sexe", "realisation_linkedin", "photo_profil")}),
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