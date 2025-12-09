from django.contrib import admin
from django.utils.html import format_html
from .models import Universite, Domaine, RoleUniversite ,News


@admin.register(Universite)
class UniversiteAdmin(admin.ModelAdmin):
    list_display = ('nom', 'acronyme', 'site_web', 'created_at', 'slug', 'logo_preview')
    search_fields = ('nom', 'acronyme', 'slug')
    list_filter = ('created_at',)
    readonly_fields = ('slug', 'created_at', 'logo_preview')
    ordering = ('nom',)

    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" width="40" height="40" style="object-fit:cover;" />', obj.logo.url)
        return "-"
    logo_preview.short_description = "Logo"


@admin.register(Domaine)
class DomaineAdmin(admin.ModelAdmin):
    list_display = ('nom', 'slug', 'memoire_count', 'univ_count')
    search_fields = ('nom', 'slug')
    ordering = ('nom',)
    readonly_fields = ('slug',)

    def memoire_count(self, obj):
        return obj.memoires.count()  # related_name='memoires' dans Domaine
    memoire_count.short_description = "Mémoires"

    def univ_count(self, obj):
        return obj.universites.count()
    univ_count.short_description = "Universités"


@admin.register(RoleUniversite)
class RoleUniversiteAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'universite', 'role', 'created_at')
    list_filter = ('role', 'universite')
    search_fields = ('utilisateur__email', 'utilisateur__nom', 'universite__nom')
    raw_id_fields = ('utilisateur', 'universite')
    ordering = ('-created_at',)
@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    # Affichage liste
    list_display = ('title', 'publisher', 'topics', 'is_published', 'publish_at', 'created_at')
    list_filter  = ('topics', 'is_published', 'created_at')
    search_fields = ('title', 'headline', 'body')

    date_hierarchy = 'publish_at'
    ordering = ['-publish_at']

  

  