from django.contrib import admin
from django.utils.html import format_html
from .models import Universite, Domaine, RoleUniversite ,News,OldStudent


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
    list_display = ('title', 'get_publishers', 'topics', 'is_published', 'publish_at', 'created_at')
    list_filter  = ('topics', 'is_published', 'publishers', 'created_at')  # Ajoutez publishers ici
    search_fields = ('title', 'headline', 'body')
    
    date_hierarchy = 'publish_at'
    ordering = ['-publish_at']

    # Méthode pour afficher les publishers de manière lisible
    def get_publishers(self, obj):
        return ", ".join(str(p) for p in obj.publishers.all())
    get_publishers.short_description = 'Universités'  # Titre pour l'affichage

@admin.register(OldStudent)
class OldStudentAdmin(admin.ModelAdmin):  # Renommez pour suivre la convention
    list_display = ('title', 'get_publishers', 'created_at')
    list_filter  = ('created_at', 'publishers')  # Ajoutez publishers ici
    search_fields = ('title', 'body')
    
    # Méthode pour afficher les publishers de manière lisible
    def get_publishers(self, obj):
        return ", ".join(str(p) for p in obj.publishers.all())
    get_publishers.short_description = 'Universités'  # Titre pour l'affichage

    
    
from .models import Affiliation
class AffiliationAdmin(admin.ModelAdmin):
    list_display = ('universite_mere', 'universite_affiliee', 'date_debut', 'date_fin')
    list_filter = ('universite_mere', 'date_debut', 'date_fin')
    search_fields = ('universite_mere__nom', 'universite_affiliee__nom')
    ordering = ('date_debut',)
    # Ajoutez d'autres options si nécessaire

admin.site.register(Affiliation, AffiliationAdmin)