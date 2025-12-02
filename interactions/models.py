from django.db import models
from django.conf import settings
from memoires.models import Memoire


class Telechargement(models.Model):
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='telechargements'
    )
    memoire = models.ForeignKey(
        Memoire,
        on_delete=models.CASCADE,
        related_name='telechargements'
    )
    date = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('utilisateur', 'memoire')  # 1 seul téléchargement par utilisateur/mémoire
        ordering = ['-date']

    def __str__(self):
        return f"{self.utilisateur} → {self.memoire} ({self.date:%d-%m-%Y %H:%M})"


class Like(models.Model):
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='likes'
    )
    memoire = models.ForeignKey(
        Memoire,
        on_delete=models.CASCADE,
        related_name='likes'
    )
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('utilisateur', 'memoire')  # 1 like par utilisateur/mémoire
        ordering = ['-date']

    def __str__(self):
        return f"{self.utilisateur} ❤️ {self.memoire}"


class Commentaire(models.Model):
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='commentaires'
    )
    memoire = models.ForeignKey(
        Memoire,
        on_delete=models.CASCADE,
        related_name='commentaires'
    )
    contenu = models.TextField()
    date = models.DateTimeField(auto_now_add=True)
    modere = models.BooleanField(default=False)  # Soft delete / modération

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.utilisateur} sur {self.memoire} : {self.contenu[:50]}..."