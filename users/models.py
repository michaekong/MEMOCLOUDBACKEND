# users/models.py
import logging
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from django.core.validators import RegexValidator
from .managers import CustomUserManager
from universites.models import Universite,RoleUniversite

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
# universites/models.py
import secrets, uuid
from django.utils import timezone
from cryptography.fernet import Fernet
from django.conf import settings

import secrets
import uuid
from django.conf import settings
from django.utils import timezone
from cryptography.fernet import Fernet


class InvitationCode(models.Model):
    """
    Code d’invitation unique, chiffré, à usage unique,
    avec rôle **déjà défini** par l’admin qui envoie l’invitation.
    """
    code = models.CharField(max_length=64, unique=True, db_index=True)  # version chiffrée
    universite = models.ForeignKey(
        Universite, on_delete=models.CASCADE, related_name="invitation_codes"
    )
    role = models.CharField(
        max_length=20, choices=RoleUniversite.ROLE_CHOICES, default="standard"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="codes_created"
    )
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="codes_used",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        default=timezone.now() + timezone.timedelta(days=7)
    )

    class Meta:
        ordering = ["-created_at"]

    # ------------------------------------------------------------------
    #  Chiffrement
    # ------------------------------------------------------------------
    _cipher = None

    @staticmethod
    def _get_cipher() -> Fernet:
        if InvitationCode._cipher is None:
            key = settings.INVITE_CODE_KEY  # 32 bytes base64 dans settings.py
            InvitationCode._cipher = Fernet(key)
        return InvitationCode._cipher

    @staticmethod
    def encrypt(raw: str) -> str:
        return InvitationCode._get_cipher().encrypt(raw.encode()).decode()

    @staticmethod
    def decrypt(enc: str) -> str:
        return InvitationCode._get_cipher().decrypt(enc.encode()).decode()

    # ------------------------------------------------------------------
    #  Life-cycle
    # ------------------------------------------------------------------
    def save(self, *args, **kwargs):
        if not self.code:
            raw = secrets.token_urlsafe(32)  # 256 bits
            self.code = InvitationCode.encrypt(raw)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_used(self):
        return self.used_by is not None

    def mark_used(self, user):
        self.used_by = user
        self.save(update_fields=["used_by"])
        