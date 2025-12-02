from django.contrib import admin
from .models import Telechargement, Like, Commentaire


@admin.register(Telechargement)
class TelechargementAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'memoire', 'date', 'ip')
    list_filter = ('date', 'memoire__universites', 'memoire__domaines')
    search_fields = ('utilisateur__email', 'memoire__titre')
    readonly_fields = ('date', 'ip', 'user_agent')
    ordering = ('-date',)


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'memoire', 'date')
    list_filter = ('date', 'memoire__universites', 'memoire__domaines')
    search_fields = ('utilisateur__email', 'memoire__titre')
    readonly_fields = ('date',)
    ordering = ('-date',)


@admin.register(Commentaire)
class CommentaireAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'memoire', 'contenu_short', 'date', 'modere')
    list_filter = ('modere', 'date', 'memoire__universites', 'memoire__domaines')
    search_fields = ('utilisateur__email', 'memoire__titre', 'contenu')
    readonly_fields = ('date',)
    ordering = ('-date',)
    actions = ['mask_comments', 'unmask_comments']

    def contenu_short(self, obj):
        return obj.contenu[:50] + "…" if len(obj.contenu) > 50 else obj.contenu
    contenu_short.short_description = "Contenu"

    def mask_comments(self, request, queryset):
        queryset.update(modere=True)
        self.message_user(request, f"{queryset.count()} commentaire(s) masqué(s).")
    mask_comments.short_description = "Masquer les commentaires sélectionnés"

    def unmask_comments(self, request, queryset):
        queryset.update(modere=False)
        self.message_user(request, f"{queryset.count()} commentaire(s) affiché(s).")
    unmask_comments.short_description = "Afficher les commentaires sélectionnés"