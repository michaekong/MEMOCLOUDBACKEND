from django.contrib import admin
from django.utils.html import format_html
from .models import Memoire, Encadrement, Signalement


@admin.register(Memoire)
class MemoireAdmin(admin.ModelAdmin):
    list_display = (
        "titre",
        "auteur",
        "annee",
        "note_moyenne",
        "nb_telechargements",
        "created_at",
        "apercu_pdf",
    )
    list_filter = (
        "annee",
        "domaines",
        "universites",
        "created_at",
    )
    search_fields = (
        "titre",
        "resume",
        "auteur__email",
        "auteur__nom",
        "auteur__prenom",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "note_moyenne",
        "nb_telechargements",
        "apercu_pdf",
    )
    filter_horizontal = ("domaines", "universites")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    def apercu_pdf(self, obj):
        if obj.fichier_pdf:
            return format_html(
                '<a href="{}" target="_blank">📄 Voir PDF</a>', obj.fichier_pdf.url
            )
        return "—"

    apercu_pdf.short_description = "Aperçu PDF"

    def note_moyenne(self, obj):
        return obj.note_moyenne()

    note_moyenne.short_description = "Note moyenne"

    def nb_telechargements(self, obj):
        return obj.nb_telechargements()

    nb_telechargements.short_description = "Téléchargements"


@admin.register(Encadrement)
class EncadrementAdmin(admin.ModelAdmin):
    list_display = ("encadreur", "memoire", "created_link")
    list_filter = ("memoire__universites", "memoire__domaines")
    search_fields = (
        "encadreur__email",
        "memoire__titre",
    )
    readonly_fields = ("created_link",)
    ordering = ("-id",)

    def created_link(self, obj):
        return format_html(
            '<a href="/admin/memoires/memoire/{}/change/">Voir mémoire</a>',
            obj.memoire.id,
        )

    created_link.short_description = "Lien mémoire"


@admin.register(Signalement)
class SignalementAdmin(admin.ModelAdmin):
    list_display = (
        "utilisateur",
        "memoire",
        "motif",
        "traite",
        "created_at",
        "commentaire_short",
    )
    list_filter = (
        "traite",
        "motif",
        "created_at",
        "memoire__universites",
    )
    search_fields = (
        "utilisateur__email",
        "memoire__titre",
        "commentaire",
    )
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
    actions = ["marquer_traites", "marquer_non_traites"]

    def commentaire_short(self, obj):
        return (
            obj.commentaire[:50] + "…" if len(obj.commentaire) > 50 else obj.commentaire
        )

    commentaire_short.short_description = "Commentaire"

    def marquer_traites(self, request, queryset):
        queryset.update(traite=True)
        self.message_user(
            request, f"{queryset.count()} signalement(s) marqué(s) comme traité(s)."
        )

    marquer_traites.short_description = "Marquer comme traité"

    def marquer_non_traites(self, request, queryset):
        queryset.update(traite=False)
        self.message_user(
            request, f"{queryset.count()} signalement(s) marqué(s) comme non traité(s)."
        )

    marquer_non_traites.short_description = "Marquer comme non traité"
# memoires/admin.py (ajout)
from .models import Notation

@admin.register(Notation)
class NotationAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'memoire', 'note', 'created_at')
    list_filter = ('note', 'created_at', 'memoire__universites', 'memoire__domaines')
    search_fields = ('utilisateur__email', 'memoire__titre')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)