from rest_framework import serializers
from memoires.models import Memoire, Encadrement, Notation
from universites.models import Domaine, Universite
from users.serializers import UserSerializer
from interactions.models import Commentaire, Telechargement


# memoires/serializers.py  (ou interactions/serializers.py)



class CommentaireSerializer(serializers.ModelSerializer):
    utilisateur = serializers.StringRelatedField()  # ou un nested serializer si tu veux plus de détails

    class Meta:
        model = Commentaire
        fields = ['id', 'utilisateur', 'contenu', 'date', 'modere']


class TelechargementSerializer(serializers.ModelSerializer):
    utilisateur = serializers.StringRelatedField()

    class Meta:
        model = Telechargement
        fields = ['id', 'utilisateur', 'date', 'ip', 'user_agent']


class NotationSerializer(serializers.ModelSerializer):
    utilisateur = serializers.StringRelatedField()

    class Meta:
        model = Notation
        fields = ['id', 'utilisateur', 'note', 'created_at']

class MemoireUniversiteListSerializer(serializers.ModelSerializer):
    auteur               = serializers.SerializerMethodField()
    encadreurs           = serializers.SerializerMethodField()
    note_moyenne         = serializers.SerializerMethodField()
    nb_telechargements   = serializers.SerializerMethodField()
    nb_likes             = serializers.SerializerMethodField()
    is_liked             = serializers.SerializerMethodField()
    nb_commentaires      = serializers.SerializerMethodField()
    domaines_list        = serializers.SlugRelatedField(slug_field='nom', many=True, read_only=True, source='domaines')
    universites_list     = serializers.SlugRelatedField(slug_field='nom', many=True, read_only=True, source='universites')
    pdf_url              = serializers.SerializerMethodField()
    commentaires_list    = serializers.SerializerMethodField()
    notations_list       = serializers.SerializerMethodField()
    telechargements_list = serializers.SerializerMethodField()

    # ------------------------------------------------------------------
    #  NOUVEAUX CHAMPS  (ceux "de droite" qui manquaient sur mobile)
    # ------------------------------------------------------------------
  
    langue               = serializers.CharField(source='get_langue_display', read_only=True)
    nombre_pages         = serializers.IntegerField(read_only=True)
    est_confidentiel     = serializers.BooleanField(read_only=True)
    fichier_taille       = serializers.SerializerMethodField()  # en Mo
    derniere_modif       = serializers.DateTimeField(source='updated_at', read_only=True)
    resume_detaille      = serializers.CharField(source='resume', read_only=True)  # alias long

    class Meta:
        model = Memoire
        fields = [
            'id', 'titre', 'resume', 'resume_detaille', 'annee', 'langue',
            'nombre_pages', 'est_confidentiel', 'fichier_taille', 'derniere_modif',
            'auteur', 'encadreurs', 'note_moyenne', 'nb_telechargements',
            'nb_likes', 'is_liked', 'nb_commentaires', 
            'domaines_list', 'universites_list', 'pdf_url', 'images',
            'created_at', 'commentaires_list', 'notations_list', 'telechargements_list',
        ]

    def get_auteur(self, obj):
        return {
            "id": obj.auteur.id,
            "nom": obj.auteur.get_full_name(),
            "email": obj.auteur.email,
            "linkedin": obj.auteur.realisation_linkedin,
            "photo_profil": self.build_url(obj.auteur.photo_profil),
        }

    def get_encadreurs(self, obj):
        return [
            {
                "id": e.encadreur.id,
                "nom": e.encadreur.get_full_name(),
                "email": e.encadreur.email,
                "linkedin": e.encadreur.realisation_linkedin,
                "photo_profil": self.build_url(e.encadreur.photo_profil),
            }
            for e in obj.encadrements.select_related('encadreur').all()
        ]

    def get_note_moyenne(self, obj):
        return obj.note_moyenne()
    def get_nb_commentaires(self, obj):        
        return obj.commentaires.count()
    def get_nb_telechargements(self, obj):
        return obj.nb_telechargements()

    def get_nb_likes(self, obj):
        return obj.likes.count()

    def get_is_liked(self, obj):
        user = self.context["request"].user
        return obj.likes.filter(utilisateur=user).exists() if user.is_authenticated else False

    def get_commentaires_list(self, obj):
        qs = Commentaire.objects.filter(memoire=obj, modere=False)
        return CommentaireSerializer(qs, many=True).data

    def get_notations_list(self, obj):
        return NotationSerializer(obj.notations.all(), many=True).data

    def get_telechargements_list(self, obj):
        return TelechargementSerializer(obj.telechargements.all(), many=True).data

    def get_mot_cle_list(self, obj):
        # suppose un champ keywords (TextField) avec mots séparés par virgule
        return [kw.strip() for kw in obj.keywords.split(',')] if obj.keywords else []

    def get_fichier_taille(self, obj):
        # taille en Mo, arrondie
        if obj.fichier_pdf and obj.fichier_pdf.size:
            return round(obj.fichier_pdf.size / 1024 / 1024, 2)
        return None
    def get_pdf_url(self, obj):
        request = self.context.get('request')
        if obj.fichier_pdf:
            return request.build_absolute_uri(obj.fichier_pdf.url) if request else obj.fichier_pdf.url
        return None
    def build_url(self, field):
        if not field:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(field.url) if request else field.url
class MemoireUniversiteCreateSerializer(serializers.ModelSerializer):
    domaines_slugs = serializers.ListField(
        child=serializers.SlugField(), write_only=True, required=False
    )
    universites_slugs = serializers.ListField(
        child=serializers.SlugField(), write_only=True, required=False
    )
    encadreurs_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    fichier_pdf = serializers.FileField(write_only=True)
    images = serializers.ImageField(write_only=True, required=False)

    class Meta:
        model = Memoire
        fields = [
            "titre",
            "resume",
            "annee",
            "fichier_pdf",
            "images",
            "domaines_slugs",
            "universites_slugs",
            "encadreurs_ids",
        ]

    def create(self, validated_data):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        domaines_slugs = validated_data.pop("domaines_slugs", [])
        universites_slugs = validated_data.pop("universites_slugs", [])
        encadreurs_ids = validated_data.pop("encadreurs_ids", [])
        memoire = Memoire.objects.create(
            auteur=self.context["request"].user, **validated_data
        )
        if domaines_slugs:
            memoire.domaines.set(Domaine.objects.filter(slug__in=domaines_slugs))
        if universites_slugs:
            memoire.universites.set(Universite.objects.filter(slug__in=universites_slugs))
        if encadreurs_ids:
            for uid in encadreurs_ids:
                Encadrement.objects.create(memoire=memoire, encadreur_id=uid)
        return memoire


class EncadrementAddSerializer(serializers.Serializer):
    encadreur_id = serializers.IntegerField(
        help_text="ID utilisateur à ajouter comme encadreur"
    )


class MemoireUniversiteStatsSerializer(serializers.Serializer):
    universite = serializers.CharField()
    total_memoires = serializers.IntegerField()
    total_telechargements = serializers.IntegerField()
    note_moyenne = serializers.FloatField()
    top_domaines = serializers.ListField(child=serializers.DictField())
