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



# users/admin.py
from django.contrib import admin
from .models import CustomUser, AuditLog, InvitationCode


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = [
        'created_at', 
        'action_badge',
        'severity_badge',
        'user_email',
        'university',
        'target_short',
        'ip_address',
    ]
    list_filter = [
        'action', 
        'severity',
        'created_at', 
        'university',
        'target_type'
    ]
    search_fields = [
        'user_email',
        'target_repr',
        'description',
        'target_id',
        'ip_address',
    ]
    readonly_fields = [
        'created_at',
        'user_id',
        'user_email',
        'user_role',
        'action',
        'severity',
        'university',
        'target_type',
        'target_id',
        'target_repr',
        'previous_data_pretty',
        'new_data_pretty',
        'ip_address',
        'user_agent',
        'request_path',
        'request_method',
        'description',
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Informations générales', {
            'fields': (
                'created_at',
                ('action', 'severity'),
                'description',
            )
        }),
        ('Utilisateur', {
            'fields': (
                ('user_id', 'user_email', 'user_role'),
            )
        }),
        ('Cible', {
            'fields': (
                'university',
                ('target_type', 'target_id'),
                'target_repr',
            )
        }),
        ('Données', {
            'fields': (
                'previous_data_pretty',
                'new_data_pretty',
            ),
            'classes': ('collapse',)
        }),
        ('Requête', {
            'fields': (
                ('ip_address', 'request_method'),
                'request_path',
                'user_agent',
            ),
            'classes': ('collapse',)
        }),
    )
    
    def action_badge(self, obj):
        from django.utils.html import format_html
        colors = {
            'MEMOIRE_CREATE': 'green',
            'MEMOIRE_UPDATE': 'blue',
            'MEMOIRE_DELETE': 'orange',
            'MEMOIRE_DELETE_TOTAL': 'red',
            'USER_ROLE_UPDATE': 'purple',
            'USER_REMOVE': 'red',
            'COMMENT_MODERATE': 'orange',
            'UNIV_BULK_DELETE': 'red',
        }
        color = colors.get(obj.action, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_action_display()
        )
    action_badge.short_description = 'Action'
    
    def severity_badge(self, obj):
        from django.utils.html import format_html
        colors = {
            'LOW': '#28a745',
            'MEDIUM': '#ffc107',
            'HIGH': '#fd7e14',
            'CRITICAL': '#dc3545',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8em;">{}</span>',
            colors.get(obj.severity, 'gray'),
            obj.get_severity_display()
        )
    severity_badge.short_description = 'Sévérité'
    
    def target_short(self, obj):
        if len(obj.target_repr) > 50:
            return obj.target_repr[:50] + '...'
        return obj.target_repr or '-'
    target_short.short_description = 'Cible'
    
    def previous_data_pretty(self, obj):
        import json
        from django.utils.html import format_html
        if not obj.previous_data:
            return '-'
        return format_html('<pre>{}</pre>', 
                         json.dumps(obj.previous_data, indent=2, ensure_ascii=False))
    previous_data_pretty.short_description = 'Données précédentes'
    
    def new_data_pretty(self, obj):
        import json
        from django.utils.html import format_html
        if not obj.new_data:
            return '-'
        return format_html('<pre>{}</pre>', 
                         json.dumps(obj.new_data, indent=2, ensure_ascii=False))
    new_data_pretty.short_description = 'Nouvelles données'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(InvitationCode)
class InvitationCodeAdmin(admin.ModelAdmin):
    # CORRECTION : utiliser les nouveaux noms de champs
    list_display = [
        'code',
        'universite',
        'role',
        'created_by_email',  # ✅ créé_by_email au lieu de created_by
        'used_by_email',     # ✅ used_by_email au lieu de used_by
        'created_at',
        'expires_at',
        'is_expired_display',  # ✅ méthode au lieu de propriété
        'is_used_display',     # ✅ méthode au lieu de propriété
    ]
    list_filter = [
        'role',
        'universite',
        'created_at',
        # ❌ Supprimé 'created_by' et 'used_by' qui n'existent plus
    ]
    search_fields = [
        'code',
        'created_by_email',  # ✅
        'used_by_email',     # ✅
    ]
    readonly_fields = [
        'code',
        'created_at',
        'created_by_id',     # ✅
        'created_by_email',  # ✅
        'used_by_id',        # ✅
        'used_by_email',     # ✅
        'is_expired_display', # ✅
        'is_used_display',    # ✅
    ]
    
    fieldsets = (
        ('Informations', {
            'fields': ('code', 'role', 'universite')
        }),
        ('Création', {
            'fields': ('created_by_id', 'created_by_email', 'created_at', 'expires_at')
        }),
        ('Utilisation', {
            'fields': ('used_by_id', 'used_by_email', 'is_used_display', 'is_expired_display')
        }),
    )
    
    # ✅ Méthodes pour remplacer les propriétés manquantes
    def is_expired_display(self, obj):
        from django.utils import timezone
        return timezone.now() > obj.expires_at
    is_expired_display.boolean = True
    is_expired_display.short_description = 'Expiré ?'
    
    def is_used_display(self, obj):
        return obj.used_by_id is not None
    is_used_display.boolean = True
    is_used_display.short_description = 'Utilisé ?'
    
    def has_add_permission(self, request):
        return False  # Les codes se créent via API

