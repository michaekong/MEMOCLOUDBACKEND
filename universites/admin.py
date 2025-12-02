# universites/admin.py
from django.contrib import admin
from .models import Universite, Domaine, RoleUniversite


@admin.register(Universite)
class UniversiteAdmin(admin.ModelAdmin):
    list_display = ('nom', 'acronyme', 'site_web', 'created_at')
    search_fields = ('nom', 'acronyme')
    list_filter = ('created_at',)




@admin.register(RoleUniversite)
class RoleUniversiteAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'universite', 'role', 'created_at')
    list_filter = ('role', 'universite')
    search_fields = ('utilisateur__email', 'universite__nom')
    raw_id_fields = ('utilisateur', 'universite')
# universites/admin.py
@admin.register(Domaine)
class DomaineAdmin(admin.ModelAdmin):
    list_display = ('nom', 'slug', 'memoire_count', 'univ_count')
    search_fields = ('nom', 'slug')
    ordering = ('nom',)

    def memoire_count(self, obj):
        return obj.memoires.count()  # on ajoutera le related_name dans l’app mémoires
    memoire_count.short_description = 'Mémoires'

    def univ_count(self, obj):
        return obj.universites.count()
    univ_count.short_description = 'Universités'    