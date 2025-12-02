# users/models.py
import logging
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from django.core.validators import RegexValidator
from .managers import CustomUserManager

logger = logging.getLogger(__name__)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    # Constantes : plus facile à ré-utiliser
    class Sexe(models.TextChoices):
        M = 'M', 'Masculin'
        F = 'F', 'Féminin'
        A = 'A', 'Autre'

    class Type(models.TextChoices):
        STANDARD = 'standard', 'Standard'
        ADMIN = 'admin', 'Administrateur'
        SUPERADMIN = 'superadmin', 'Super Administrateur'
        BIGBOSS = 'bigboss', 'BIGBOSS'

    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    sexe = models.CharField(max_length=1, choices=Sexe.choices)
    email = models.EmailField(unique=True, db_index=True)
    type = models.CharField(
        max_length=10,
        choices=Type.choices,
        default=Type.STANDARD,
        validators=[RegexValidator(
            regex=r'^(standard|admin|superadmin|bigboss)$',
            message="Rôle inconnu."
        )]
    )
    realisation_linkedin = models.URLField(max_length=200, blank=True, null=True)
    photo_profil = models.ImageField(upload_to='photos_profil/', blank=True, null=True)

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nom', 'prenom', 'sexe']

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        indexes = [models.Index(fields=['email'])]

    def save(self, *args, **kwargs):
        if not self.password.startswith('pbkdf2_'):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.prenom} {self.nom}"

    # ---------------- utilitaires -----------------
    def has_role(self, role):
        return self.type == role

    def promote(self, new_role):
        if new_role not in self.Type.values:
            raise ValueError("Rôle inconnu")
        old = self.type
        self.type = new_role
        self.save(update_fields=['type'])
        logger.info(f"Role changed for {self.email} : {old} → {new_role}")
        return self.type

    def get_full_name(self):
        return f"{self.prenom} {self.nom}".strip()

    def get_short_name(self):
        return self.prenom