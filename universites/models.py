from django.db import models
from django.conf import settings
from django.utils.text import slugify
import unicodedata
from django.core.exceptions import ValidationError

class Universite(models.Model):
    nom = models.CharField(max_length=200, unique=True)
    acronyme = models.CharField(max_length=20, unique=True)
    slogan = models.TextField(blank=True)
    logo = models.ImageField(upload_to="universites/logos/", blank=True, null=True)
    site_web = models.URLField(blank=True, null=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return f"{self.nom} ({self.acronyme})"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(
                unicodedata.normalize('NFKD', self.nom)
                .encode('ASCII', 'ignore')
                .decode('ASCII')
            ) or slugify(self.nom)

            self.slug = base
            counter = 1
            while Universite.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base}-{counter}"
                counter += 1
        super().save(*args, **kwargs)


class Domaine(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    universites = models.ManyToManyField(
        'Universite', related_name='domaines', blank=True
    )

    class Meta:
        ordering = ['nom']

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        # Normalise le nom
        cleaned = self.normalize_nom(self.nom)
        self.slug = cleaned
        super().save(*args, **kwargs)

    @staticmethod
    def normalize_nom(nom: str) -> str:
        return slugify(unicodedata.normalize('NFKD', nom).encode('ASCII', 'ignore').decode('ASCII'))

    def clean(self):
        # Empêche la suppression si encore lié à des mémoires
        if self.pk and self.memoires.exists():  # Assurez-vous que `memoires` est un attribut valide
            raise ValidationError("Ce domaine est utilisé par des mémoires. Vous ne pouvez pas le supprimer.")

    @classmethod
    def get_or_create_normalized(cls, nom: str):
        """
        Récupère ou crée un domaine à partir d’un nom brut.
        Exemple : get_or_create_normalized("  MEdecine  ")
        → renvoie le domaine « Médecine » (slug=medecine)
        """
        cleaned = unicodedata.normalize('NFKD', nom.strip()).encode('ASCII', 'ignore').decode('ASCII')
        slug = cls.normalize_nom(cleaned)
        return cls.objects.get_or_create(slug=slug, defaults={'nom': nom.strip()})


class RoleUniversite(models.Model):
    ROLE_CHOICES = [
        ("standard", "Standard"),
        ("professeur", "Professeur"),
        ("admin", "Administrateur"),
        ("superadmin", "Super Administrateur"),
        ("bigboss", "BIGBOSS"),
    ]
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="roles_univ"
    )
    universite = models.ForeignKey(
        Universite, on_delete=models.CASCADE, related_name="roles"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="standard")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("utilisateur", "universite")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.utilisateur} – {self.universite} ({self.role})"
# news/models.py
class NewsTopic(models.TextChoices):
    GENERAL  = 'general', 'Général'
    EVENT    = 'event', 'Événement'
    AWARD    = 'award', 'Récompense'
    RESEARCH = 'research', 'Recherche'
    ALUMNI   = 'alumni', 'Alumni'
class News(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    headline = models.TextField(blank=True)
    body = models.TextField()
    cover = models.ImageField(upload_to='news_covers/', blank=True, null=True)
    topics = models.CharField(max_length=50, default='general')
    is_published = models.BooleanField(default=True)
    publish_at = models.DateTimeField()
    publisher = models.ForeignKey('universites.Universite', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        # ✅ Auto-génération du slug si vide
        if not self.slug:
            self.slug = slugify(self.title)
            # Gestion des doublons
            original_slug = self.slug
            counter = 1
            while News.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)