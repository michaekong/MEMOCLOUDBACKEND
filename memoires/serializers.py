from rest_framework import serializers
from memoires.models import Memoire, Encadrement
from universites.models import Domaine, Universite
from users.serializers import UserSerializer

class MemoireUniversiteListSerializer(serializers.ModelSerializer):
    auteur = serializers.SerializerMethodField()
    encadreurs = serializers.SerializerMethodField()
    note_moyenne = serializers.SerializerMethodField()
    nb_telechargements = serializers.SerializerMethodField()
    nb_likes = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    nb_commentaires = serializers.SerializerMethodField()  # Nouveau champ pour le nombre de commentaires
    domaines_list = serializers.SlugRelatedField(slug_field='nom', many=True, read_only=True, source='domaines')
    universites_list = serializers.SlugRelatedField(slug_field='nom', many=True, read_only=True, source='universites')
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = Memoire
        fields = [
            'id', 'titre', 'resume', 'annee', 'auteur',
            'encadreurs', 'note_moyenne', 'nb_telechargements', 'nb_likes', 
            'is_liked', 'nb_commentaires',  # Ajout du champ ici
            'domaines_list', 'universites_list', 'pdf_url', 'images', 'created_at'
        ]

    def get_auteur(self, obj):
        return {
            'nom': obj.auteur.get_full_name(),
            'email': obj.auteur.email,
            'linkedin': obj.auteur.realisation_linkedin,
            'photo_profil': obj.auteur.photo_profil.url if obj.auteur.photo_profil else None
        }

    def get_encadreurs(self, obj):
        return [
            {
                'nom': encadreur.encadreur.get_full_name(),
                'email': encadreur.encadreur.email,
                'linkedin': encadreur.encadreur.realisation_linkedin,
                'photo_profil': encadreur.encadreur.photo_profil.url if encadreur.encadreur.photo_profil else None
            }
            for encadreur in obj.encadrements.all()
        ]

    def get_note_moyenne(self, obj):
        return obj.note_moyenne()

    def get_nb_telechargements(self, obj):
        return obj.nb_telechargements()

    def get_nb_likes(self, obj):
        return obj.likes.count()

    def get_is_liked(self, obj):
        user = self.context['request'].user
        return obj.likes.filter(utilisateur=user).exists() if user.is_authenticated else False

    def get_nb_commentaires(self, obj):  # Méthode pour obtenir le nombre de commentaires
        return obj.commentaires.count()  # Compte le nombre de commentaires associés au mémoire

    def get_pdf_url(self, obj):
        request = self.context['request']
        return request.build_absolute_uri(obj.fichier_pdf.url) if obj.fichier_pdf else None
class MemoireUniversiteCreateSerializer(serializers.ModelSerializer):
    domaines_slugs = serializers.ListField(child=serializers.SlugField(), write_only=True, required=False)
    universites_slugs = serializers.ListField(child=serializers.SlugField(), write_only=True, required=False)
    encadreurs_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)
    fichier_pdf = serializers.FileField(write_only=True)
    images = serializers.ImageField(write_only=True, required=False)

    class Meta:
        model = Memoire
        fields = ['titre','resume','annee','fichier_pdf','images','domaines_slugs','universites_slugs','encadreurs_ids']

    def create(self, validated_data):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        domaines_slugs = validated_data.pop('domaines_slugs', [])
        universites_slugs = validated_data.pop('universites_slugs', [])
        encadreurs_ids = validated_data.pop('encadreurs_ids', [])
        memoire = Memoire.objects.create(auteur=self.context['request'].user, **validated_data)
        if domaines_slugs:
            memoire.domaines.set(Domaine.objects.filter(slug__in=domaines_slugs))
        if universites_slugs:
            memoire.universites.set(Universite.objects.filter(slug__in=universites_slugs))
        if encadreurs_ids:
            for uid in encadreurs_ids:
                Encadrement.objects.create(memoire=memoire, encadreur_id=uid)
        return memoire


class EncadrementAddSerializer(serializers.Serializer):
    encadreur_id = serializers.IntegerField(help_text="ID utilisateur à ajouter comme encadreur")


class MemoireUniversiteStatsSerializer(serializers.Serializer):
    universite = serializers.CharField()
    total_memoires = serializers.IntegerField()
    total_telechargements = serializers.IntegerField()
    note_moyenne = serializers.FloatField()
    top_domaines = serializers.ListField(child=serializers.DictField())