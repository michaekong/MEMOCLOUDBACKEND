# users/models.py
import logging
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from django.core.validators import RegexValidator
from .managers import CustomUserManager

logger = logging.getLogger(__name__)


# ========== CUSTOM USER ==========

class CustomUser(AbstractBaseUser, PermissionsMixin):
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

    def save(self, *args, **kwargs):
        if not self.password.startswith('pbkdf2_'):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)
    def get_full_name(self):
        return f"{self.prenom} {self.nom}" 

    def __str__(self):
        return f"{self.prenom} {self.nom}"


# ========== AUDIT LOG (défini APRÈS CustomUser, utilise lazy reference) ==========

class AuditLog(models.Model):
    class ActionType(models.TextChoices):
        MEMOIRE_CREATE = 'MEMOIRE_CREATE', 'Création de mémoire'
        MEMOIRE_UPDATE = 'MEMOIRE_UPDATE', 'Modification de mémoire'
        MEMOIRE_DELETE = 'MEMOIRE_DELETE', 'Suppression de mémoire'
        MEMOIRE_DELETE_TOTAL = 'MEMOIRE_DELETE_TOTAL', 'Suppression totale de mémoire'
        USER_ROLE_UPDATE = 'USER_ROLE_UPDATE', 'Modification de rôle utilisateur'
        USER_REMOVE = 'USER_REMOVE', 'Retrait utilisateur université'
        USER_DEACTIVATE = 'USER_DEACTIVATE', 'Désactivation compte'
        USER_BULK_INVITE = 'USER_BULK_INVITE', 'Invitation en masse'
        COMMENT_MODERATE = 'COMMENT_MODERATE', 'Modération commentaire'
        COMMENT_DELETE = 'COMMENT_DELETE', 'Suppression commentaire'
        SIGNALEMENT_TRAITE = 'SIGNALEMENT_TRAITE', 'Signalement traité'
        UNIV_LOGO_UPDATE = 'UNIV_LOGO_UPDATE', 'Mise à jour logo'
        UNIV_LOGO_DELETE = 'UNIV_LOGO_DELETE', 'Suppression logo'
        UNIV_BULK_DELETE = 'UNIV_BULK_DELETE', 'Suppression multiple universités'
        UNIV_AFFILIATION_CREATE = 'UNIV_AFFILIATION_CREATE', 'Création affiliation'
        DOMAINE_CREATE = 'DOMAINE_CREATE', 'Création domaine'
        DOMAINE_UPDATE = 'DOMAINE_UPDATE', 'Modification domaine'
        DOMAINE_DELETE = 'DOMAINE_DELETE', 'Suppression domaine'
        NEWS_CREATE = 'NEWS_CREATE', 'Création news'
        NEWS_DELETE = 'NEWS_DELETE', 'Suppression news'
        NEWS_DISSOCIATE = 'NEWS_DISSOCIATE', 'Dissociation news'
        OLDSTUDENT_CREATE = 'OLDSTUDENT_CREATE', 'Création ancien étudiant'
        OLDSTUDENT_DELETE = 'OLDSTUDENT_DELETE', 'Suppression ancien étudiant'
        OLDSTUDENT_DISSOCIATE = 'OLDSTUDENT_DISSOCIATE', 'Dissociation ancien étudiant'
        ENCADREMENT_ADD = 'ENCADREMENT_ADD', 'Ajout encadreur'
        ENCADREMENT_REMOVE = 'ENCADREMENT_REMOVE', 'Retrait encadreur'
        LOGIN = 'LOGIN', 'Connexion'
        LOGIN_FAILED = 'LOGIN_FAILED', 'Échec connexion'
        PASSWORD_RESET = 'PASSWORD_RESET', 'Réinitialisation mot de passe'
      
    
    class Severity(models.TextChoices):
        LOW = 'LOW', 'Faible'
        MEDIUM = 'MEDIUM', 'Moyenne'
        HIGH = 'HIGH', 'Élevée'
        CRITICAL = 'CRITICAL', 'Critique'

    # Solution : Pas de ForeignKey vers User ici !
    # On stocke juste les infos en dur
    user_id = models.IntegerField(null=True, blank=True, verbose_name='ID Utilisateur')
    user_email = models.EmailField(blank=True, verbose_name='Email utilisateur')
    user_role = models.CharField(max_length=20, blank=True, verbose_name='Rôle utilisateur')
    
    action = models.CharField(max_length=30, choices=ActionType.choices, verbose_name='Type d\'action')
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MEDIUM, verbose_name='Sévérité')
    
    university = models.ForeignKey(
        'universites.Universite',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name='Université concernée'
    )
    
    target_type = models.CharField(max_length=50, blank=True, verbose_name='Type de cible')
    target_id = models.CharField(max_length=50, blank=True, verbose_name='ID cible')
    target_repr = models.TextField(blank=True, verbose_name='Représentation cible')
    
    previous_data = models.JSONField(null=True, blank=True, verbose_name='Données avant action')
    new_data = models.JSONField(null=True, blank=True, verbose_name='Données après action')
    
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='Adresse IP')
    user_agent = models.TextField(blank=True, verbose_name='User Agent')
    request_path = models.TextField(blank=True, verbose_name='Chemin de la requête')
    request_method = models.CharField(max_length=10, blank=True, verbose_name='Méthode HTTP')
    description = models.TextField(blank=True, verbose_name='Description détaillée')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Date de l\'action')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Log d\'audit'
        verbose_name_plural = 'Logs d\'audit'
        indexes = [
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['user_id', 'created_at']),
            models.Index(fields=['university', 'created_at']),
            models.Index(fields=['severity', 'created_at']),
            models.Index(fields=['target_type', 'target_id']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"[{self.get_severity_display()}] {self.get_action_display()} par {self.user_email or 'Système'} le {self.created_at:%d/%m/%Y %H:%M}"
    
    def get_user(self):
        """Récupère l'utilisateur si existe encore."""
        try:
            return CustomUser.objects.get(id=self.user_id)
        except CustomUser.DoesNotExist:
            return None


# ========== INVITATION CODE (même principe, sans FK vers CustomUser) ==========

class InvitationCode(models.Model):
    code = models.CharField(max_length=64, unique=True, db_index=True)
    universite = models.ForeignKey(
        'universites.Universite', 
        on_delete=models.CASCADE, 
        related_name="invitation_codes"
    )
    role = models.CharField(
        max_length=20, 
        choices=[
            ("standard", "Standard"),
            ("professeur", "Professeur"),
            ("admin", "Administrateur"),
            ("superadmin", "Super Administrateur"),
            ("bigboss", "BIGBOSS"),
        ], 
        default="standard"
    )
    # Solution : stocker l'ID au lieu de la FK
    created_by_id = models.IntegerField(verbose_name='Créé par (ID)')
    created_by_email = models.EmailField(verbose_name='Créé par (email)')
    used_by_id = models.IntegerField(null=True, blank=True, verbose_name='Utilisé par (ID)')
    used_by_email = models.EmailField(blank=True, verbose_name='Utilisé par (email)')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=timezone.now() + timezone.timedelta(days=7))

    class Meta:
        ordering = ["-created_at"]

    def get_created_by(self):
        try:
            return CustomUser.objects.get(id=self.created_by_id)
        except CustomUser.DoesNotExist:
            return None

    def get_used_by(self):
        if not self.used_by_id:
            return None
        try:
            return CustomUser.objects.get(id=self.used_by_id)
        except CustomUser.DoesNotExist:
            return None