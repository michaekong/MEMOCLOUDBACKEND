# managers.py
from django.contrib.auth.models import BaseUserManager
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    """
    Manager personnalisé pour le modèle CustomUser (AbstractBaseUser)
    """

    def create_user(self, email, nom, prenom, sexe, password=None, **extra_fields):
        """
        Crée et sauvegarde un utilisateur avec l'email et les champs requis.
        """
        if not email:
            raise ValueError("L'email est obligatoire")
        email = self.normalize_email(email)
        user = self.model(
            email=email,
            nom=nom,
            prenom=prenom,
            sexe=sexe,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, nom, prenom, sexe, password=None, **extra_fields):
        """
        Crée et sauvegarde un superutilisateur avec tous les droits.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get('is_superuser') is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, nom, prenom, sexe, password, **extra_fields)