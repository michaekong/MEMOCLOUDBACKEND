from rest_framework import serializers
from memoires.models import Memoire, Encadrement, Notation
from universites.models import Domaine, Universite
from users.serializers import UserSerializer
from interactions.models import Commentaire, Telechargement
from users.models import CustomUser


# memoires/serializers.py  (ou interactions/serializers.py)


class UtilisateurSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser  # Assurez-vous d'importer votre modèle CustomUser
        fields = [
            "id",
            "nom",
            "prenom",
            "sexe",
            "email",
            "type",
            "photo_profil",
            "realisation_linkedin",
        ]


class CommentaireSerializer(serializers.ModelSerializer):
    utilisateur = UtilisateurSerializer(
        read_only=True
    )  # ou un nested serializer si tu veux plus de détails

    class Meta:
        model = Commentaire
        fields = ["id", "utilisateur", "contenu", "date", "modere"]


class TelechargementSerializer(serializers.ModelSerializer):
    utilisateur = serializers.StringRelatedField()

    class Meta:
        model = Telechargement
        fields = ["id", "utilisateur", "date", "ip", "user_agent"]


class NotationSerializer(serializers.ModelSerializer):
    utilisateur = serializers.StringRelatedField()

    class Meta:
        model = Notation
        fields = ["id", "utilisateur", "note", "created_at"]


class MemoireUniversiteListSerializer(serializers.ModelSerializer):
    auteur = serializers.SerializerMethodField()
    encadreurs = serializers.SerializerMethodField()
    note_moyenne = serializers.SerializerMethodField()
    nb_telechargements = serializers.SerializerMethodField()
    nb_likes = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    nb_commentaires = serializers.SerializerMethodField()
    domaines_list = serializers.SlugRelatedField(
        slug_field="nom", many=True, read_only=True, source="domaines"
    )
    universites_list = serializers.SlugRelatedField(
        slug_field="nom", many=True, read_only=True, source="universites"
    )
    pdf_url = serializers.SerializerMethodField()
    commentaires_list = serializers.SerializerMethodField()
    notations_list = serializers.SerializerMethodField()
    telechargements_list = serializers.SerializerMethodField()

    # ------------------------------------------------------------------
    #  NOUVEAUX CHAMPS  (ceux "de droite" qui manquaient sur mobile)
    # ------------------------------------------------------------------

    langue = serializers.CharField(source="get_langue_display", read_only=True)
    nombre_pages = serializers.IntegerField(read_only=True)
    est_confidentiel = serializers.BooleanField(read_only=True)
    fichier_taille = serializers.SerializerMethodField()  # en Mo
    derniere_modif = serializers.DateTimeField(source="updated_at", read_only=True)
    resume_detaille = serializers.CharField(source="resume", read_only=True)  # alias long

    class Meta:
        model = Memoire
        fields = [
            "id",
            "titre",
            "resume",
            "resume_detaille",
            "annee",
            "langue",
            "nombre_pages",
            "est_confidentiel",
            "fichier_taille",
            "derniere_modif",
            "auteur",
            "encadreurs",
            "note_moyenne",
            "nb_telechargements",
            "nb_likes",
            "is_liked",
            "nb_commentaires",
            "domaines_list",
            "universites_list",
            "pdf_url",
            "images",
            "created_at",
            "commentaires_list",
            "notations_list",
            "telechargements_list",
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
            for e in obj.encadrements.select_related("encadreur").all()
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
        return (
            obj.likes.filter(utilisateur=user).exists()
            if user.is_authenticated
            else False
        )

    def get_commentaires_list(self, obj):
        qs = Commentaire.objects.filter(memoire=obj, modere=False)
        return CommentaireSerializer(qs, many=True).data

    def get_notations_list(self, obj):
        return NotationSerializer(obj.notations.all(), many=True).data

    def get_telechargements_list(self, obj):
        return TelechargementSerializer(obj.telechargements.all(), many=True).data

    def get_mot_cle_list(self, obj):
        # suppose un champ keywords (TextField) avec mots séparés par virgule
        return [kw.strip() for kw in obj.keywords.split(",")] if obj.keywords else []

    def get_fichier_taille(self, obj):
        try:
            if obj.fichier_pdf and obj.fichier_pdf.name and obj.fichier_pdf.size:
                return round(obj.fichier_pdf.size / 1024 / 1024, 2)  # Mo
        except (FileNotFoundError, OSError):
            pass
        return None

    def get_pdf_url(self, obj):
        request = self.context.get("request")
        if obj.fichier_pdf:
            return (
                request.build_absolute_uri(obj.fichier_pdf.url)
                if request
                else obj.fichier_pdf.url
            )
        return None

    def build_url(self, field):
        if not field:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(field.url) if request else field.url


from django.db import transaction


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
    auteur_id = serializers.IntegerField(write_only=True, required=True)
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
            "auteur_id",
        ]

    def create(self, validated_data):
        with transaction.atomic():
            # 1. on retire **une seule fois** et on **garde**
            domaines_slugs    = validated_data.pop("domaines_slugs", [])
            universites_slugs = validated_data.pop("universites_slugs", [])
            encadreurs_ids    = validated_data.pop("encadreurs_ids", [])
            auteur_id         = validated_data.pop("auteur_id")

            memoire = Memoire.objects.create(
                auteur=CustomUser.objects.get(id=auteur_id), **validated_data
            )

            # 2. relations
            if domaines_slugs:
                memoire.domaines.set(Domaine.objects.filter(slug__in=domaines_slugs))
            if universites_slugs:
                memoire.universites.set(Universite.objects.filter(slug__in=universites_slugs))
            if encadreurs_ids:
                existing = set(
                    Encadrement.objects.filter(
                        memoire=memoire, encadreur_id__in=encadreurs_ids
                    ).values_list("encadreur_id", flat=True)
                )
                to_create = [uid for uid in encadreurs_ids if uid not in existing]
                Encadrement.objects.bulk_create(
                    [Encadrement(memoire=memoire, encadreur_id=uid) for uid in to_create],
                    ignore_conflicts=True
                )

            return memoire

    def update(self, instance, validated_data, **kwargs):
        domaines_slugs = validated_data.pop("domaines_slugs", None)
        encadreurs_ids = validated_data.pop("encadreurs_ids", None)

        # champs simples
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        with transaction.atomic():
            # 1. domaines
            if domaines_slugs is not None:
                instance.domaines.set(Domaine.objects.filter(slug__in=domaines_slugs))

            # 2. encadreurs : on remplace **tout** sans doublon
            if encadreurs_ids is not None:
                # a. on supprime les anciens
                instance.encadrements.all().delete()
                # b. on crée **en bulk** en ignorant les doublons (sécurité)
                encadrements = [
                    Encadrement(memoire=instance, encadreur_id=uid)
                    for uid in set(encadreurs_ids)  # set = pas de doublons
                ]
                Encadrement.objects.bulk_create(encadrements, ignore_conflicts=True)

        return instance


class EncadrementAddSerializer(serializers.Serializer):
    encadreur_id = serializers.IntegerField(
        help_text="ID utilisateur à ajouter comme encadreur"
    )


class MemoireUniversiteStatsSerializer(serializers.Serializer):
    universite = serializers.CharField()
    total_memoires = serializers.IntegerField()
    total_telechargements = serializers.IntegerField()
    note_moyenne = serializers.FloatField()
    total_likes = serializers.IntegerField()  # Ajout
    total_commentaires = serializers.IntegerField()  # Ajout
    top_domaines = serializers.ListField(child=serializers.DictField())
