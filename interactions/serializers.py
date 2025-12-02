from rest_framework import serializers
from .models import Telechargement, Like, Commentaire
from memoires.models import Memoire
from users.models import CustomUser


class TelechargementSerializer(serializers.ModelSerializer):
    utilisateur_email = serializers.CharField(source='utilisateur.email', read_only=True)
    memoire_titre = serializers.CharField(source='memoire.titre', read_only=True)

    class Meta:
        model = Telechargement
        fields = ['id', 'utilisateur', 'utilisateur_email', 'memoire', 'memoire_titre', 'date', 'ip', 'user_agent']
        read_only_fields = ['date', 'ip', 'user_agent']


class LikeSerializer(serializers.ModelSerializer):
    utilisateur_email = serializers.CharField(source='utilisateur.email', read_only=True)

    class Meta:
        model = Like
        fields = ['id', 'utilisateur', 'utilisateur_email', 'memoire', 'date']
        read_only_fields = ['date']


class CommentaireSerializer(serializers.ModelSerializer):
    utilisateur_nom = serializers.CharField(source='utilisateur.get_full_name', read_only=True)
    modere = serializers.BooleanField(read_only=True)  # Seul un modérateur peut modérer

    class Meta:
        model = Commentaire
        fields = ['id', 'utilisateur', 'utilisateur_nom', 'memoire', 'contenu', 'date', 'modere']
        read_only_fields = ['date']