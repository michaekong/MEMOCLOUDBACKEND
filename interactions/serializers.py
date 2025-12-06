# These classes define serializers for various interactions and actions related to user interactions
# with memories in a Django REST framework application.
from rest_framework import serializers
from users.models import  CustomUser
from interactions.models import Telechargement, Like, Commentaire
from memoires.models import Notation, Signalement

# ---------- LISTE ----------
class TelechargementListSerializer(serializers.ModelSerializer):
    utilisateur_nom = serializers.CharField(source='utilisateur.get_full_name', read_only=True)
    memoire_titre = serializers.CharField(source='memoire.titre', read_only=True)

    class Meta:
        model = Telechargement
        fields = ['id', 'utilisateur', 'utilisateur_nom', 'memoire', 'memoire_titre', 'date']


class LikeListSerializer(serializers.ModelSerializer):
    utilisateur_nom = serializers.CharField(source='utilisateur.get_full_name', read_only=True)
    memoire_titre = serializers.CharField(source='memoire.titre', read_only=True)

    class Meta:
        model = Like
        fields = ['id', 'utilisateur', 'utilisateur_nom', 'memoire', 'memoire_titre', 'date']


from rest_framework import serializers
from .models import Commentaire

class UtilisateurSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser  # Assurez-vous d'importer votre modèle CustomUser
        fields = ['nom', 'prenom', 'sexe', 'email', 'type', 'photo_profil','realisation_linkedin']

class CommentaireListSerializer(serializers.ModelSerializer):
    utilisateur = UtilisateurSerializer(read_only=True)  # Utilisateur représenté comme un objet

    modere = serializers.BooleanField(read_only=True)

    class Meta:
        model = Commentaire
        fields = ['id', 'utilisateur', 'contenu', 'date', 'modere']

class NotationListSerializer(serializers.ModelSerializer):
    utilisateur_nom = serializers.CharField(source='utilisateur.get_full_name', read_only=True)

    class Meta:
        model = Notation
        fields = ['id', 'utilisateur', 'utilisateur_nom', 'memoire', 'note', 'created_at']


class SignalementListSerializer(serializers.ModelSerializer):
    utilisateur_nom = serializers.CharField(source='utilisateur.get_full_name', read_only=True)
    memoire_titre = serializers.CharField(source='memoire.titre', read_only=True)
    traite = serializers.BooleanField(read_only=True)
    class Meta:
        model = Signalement
        fields = ['id', 'utilisateur', 'utilisateur_nom', 'memoire', 'memoire_titre', 'motif', 'commentaire', 'traite', 'created_at']


# ---------- ACTIONS (body) ----------
class TelechargementCreateSerializer(serializers.Serializer):
    memoire = serializers.IntegerField(help_text="ID du mémoire à télécharger")


class LikeToggleSerializer(serializers.Serializer):
    memoire_id = serializers.IntegerField(help_text="ID du mémoire à liker")


# interactions/serializers.py
class CommentaireCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Commentaire
        fields = ['memoire', 'contenu']   # seuls champs attendus côté front

class NotationCreateSerializer(serializers.ModelSerializer):
    memoire_id = serializers.IntegerField()  # Vérifiez que c'est bien déclaré ici

    class Meta:
        model = Notation
        fields = ['memoire_id', 'note']

    def validate_note(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("La note doit être entre 1 et 5.")
        return value

class SignalementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Signalement
        fields = ['memoire', 'motif', 'commentaire']