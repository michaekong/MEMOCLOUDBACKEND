# memoires/models.py
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from simple_history.models import HistoricalRecords
from universites.models import Domaine, Universite


# ------------------------------------------------------------------
# 1. Mémoire
# ------------------------------------------------------------------
class Memoire(models.Model):
    titre = models.CharField(max_length=250)
    resume = models.TextField()
    annee = models.PositiveIntegerField()
    fichier_pdf = models.FileField(upload_to="memoires/pdfs/")
    images = models.ImageField(upload_to="memoires/images/", blank=True, null=True)
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memoires"
    )
    domaines = models.ManyToManyField(Domaine, related_name="memoires", blank=True)
    universites = models.ManyToManyField(Universite, related_name="memoires", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Historique des modifications
    history = HistoricalRecords()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.titre

    def note_moyenne(self):
        notes = self.notations.values_list("note", flat=True)
        return round(sum(notes) / len(notes), 2) if notes else 0

    def nb_telechargements(self):
        return self.telechargements.count()

    def clean(self):
        # Empêche la suppression si le mémoire est signalé en attente
        if self.pk and self.signalements.filter(traite=False).exists():
            raise ValidationError("Ce mémoire est en cours de modération.")

    def delete(self, *args, **kwargs):
        # Protection : on interdit la suppression si des données liées existent
        if (
            
            self.encadrements.exists()
            or self.notations.exists()
            or self.telechargements.exists()
        ):
            print(self.Encadrements)
            
            raise ValidationError("Impossible de supprimer : mémoire lié à des données.")
        super().delete(*args, **kwargs)


# ------------------------------------------------------------------
# 2. Encadrement
# ------------------------------------------------------------------
class Encadrement(models.Model):
    memoire = models.ForeignKey(
        Memoire, on_delete=models.CASCADE, related_name="encadrements"
    )
    encadreur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="encadrements_memoires",
    )

    class Meta:
        unique_together = ("memoire", "encadreur")

    def __str__(self):
        return f"{self.encadreur} sur {self.memoire}"


# ------------------------------------------------------------------
# 3. Signalement (modération)
# ------------------------------------------------------------------
class Signalement(models.Model):
    MOTIF_CHOICES = [
        ("spam", "Spam"),
        ("inaproprié", "Inapproprié"),
        ("erreur", "Erreur de contenu"),
        ("copyright", "Violation de copyright"),
    ]
    memoire = models.ForeignKey(
        Memoire, on_delete=models.CASCADE, related_name="signalements"
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="signalements_emis",
    )
    motif = models.CharField(max_length=50, choices=MOTIF_CHOICES)
    commentaire = models.TextField(blank=True)
    traite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("memoire", "utilisateur")  # 1 signalement par user/mémoire

    def __str__(self):
        return f"{self.utilisateur} → {self.memoire} ({self.motif})"


# ------------------------------------------------------------------
# 4. Notation (note /5)
# ------------------------------------------------------------------
class Notation(models.Model):
    memoire = models.ForeignKey(
        Memoire, on_delete=models.CASCADE, related_name="notations"
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notations"
    )
    note = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("memoire", "utilisateur")  # 1 note par user/mémoire
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.utilisateur} → {self.memoire} : {self.note}/5"
