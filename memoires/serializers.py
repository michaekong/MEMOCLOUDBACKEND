# memoires/serializers.py
import csv
import io
import os
import uuid
import requests
import unicodedata
from django.conf import settings
from django.core.files import File
from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Memoire, Encadrement,Signalement
from universites.models import Domaine, Universite
from users.serializers import UserSerializer

User = get_user_model()


# ------------------------------------------------------------------
# 1. Liste / détail (read-only + champs calculés)
# ------------------------------------------------------------------
class MemoireListSerializer(serializers.ModelSerializer):
    auteur = UserSerializer(read_only=True)
    domaines = serializers.SerializerMethodField()
    universites = serializers.SerializerMethodField()
    note_moyenne = serializers.SerializerMethodField()
    nb_telechargements = serializers.SerializerMethodField()

    class Meta:
        model = Memoire
        fields = [
            'id',
            'titre',
            'resume',
            'annee',
            'auteur',
            'domaines',
            'universites',
            'note_moyenne',
            'nb_telechargements',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'note_moyenne', 'nb_telechargements']

    def get_note_moyenne(self, obj):
        return obj.note_moyenne()

    def get_nb_telechargements(self, obj):
        return obj.nb_telechargements()

    def get_domaines(self, obj):
        from universites.serializers import DomaineSerializer
        return DomaineSerializer(obj.domaines.all(), many=True, context=self.context).data

    def get_universites(self, obj):
        from universites.serializers import UniversiteSerializer
        return UniversiteSerializer(obj.universites.all(), many=True, context=self.context).data


# ------------------------------------------------------------------
# 2. Création / édition (write-only IDs)
# ------------------------------------------------------------------
class MemoireCreateSerializer(serializers.ModelSerializer):
    domaines = serializers.PrimaryKeyRelatedField(
        queryset=Domaine.objects.all(), many=True, required=False
    )
    universites = serializers.PrimaryKeyRelatedField(
        queryset=Universite.objects.all(), many=True, required=False
    )
    encadreurs = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), many=True, required=False, write_only=True
    )

    class Meta:
        model = Memoire
        fields = [
            'titre',
            'resume',
            'annee',
            'fichier_pdf',
            'images',
            'domaines',
            'universites',
            'encadreurs',
        ]

    def create(self, validated_data):
        encadreurs = validated_data.pop('encadreurs', [])
        domaines = validated_data.pop('domaines', [])
        universites = validated_data.pop('universites', [])
        memoire = Memoire.objects.create(**validated_data)
        memoire.domaines.set(domaines)
        memoire.universites.set(universites)
        for enc in encadreurs:
            Encadrement.objects.create(memoire=memoire, encadreur=enc)
        return memoire


# ------------------------------------------------------------------
# 3. Encadrement
# ------------------------------------------------------------------
class EncadrementSerializer(serializers.ModelSerializer):
    encadreur = UserSerializer(read_only=True)

    class Meta:
        model = Encadrement
        fields = ['id', 'encadreur', 'memoire']
        read_only_fields = ['id']


# ------------------------------------------------------------------
# 4. BATCH CSV – upload en masse
# ------------------------------------------------------------------
class MemoireBulkCSVSerializer(serializers.Serializer):
    csv_file = serializers.FileField()

    def validate_csv_file(self, value):
        if not value.name.lower().endswith('.csv'):
            raise serializers.ValidationError("Le fichier doit être au format CSV.")
        return value

    def save(self, **kwargs):
        """
        Traite le CSV ligne par ligne :
        - télécharge le PDF (ou copie locale)
        - crée le mémoire
        - attache domaines, univ, encadreurs
        Retourne un dict : {created:int, errors:list[dict]}
        """
        import csv
        import io
        import os
        import uuid
        import requests
        import unicodedata
        from django.core.files import File
        from django.contrib.auth import get_user_model

        User = get_user_model()
        csv_file = self.validated_data['csv_file']
        decoded_file = csv_file.read().decode('utf-8')
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)

        created = 0
        errors = []

        for row_num, row in enumerate(reader, start=1):
            try:
                # Champs obligatoires
                titre = row.get('titre', '').strip()
                resume = row.get('resume', '').strip()
                annee_str = row.get('annee', '').strip()
                annee = int(annee_str) if annee_str.isdigit() else None
                if not (titre and resume and annee):
                    raise ValueError("titre, resume ou annee manquant")

                # Auteur = user connecté
                auteur = self.context['request'].user

                # Domaines
                domaines_ids = [int(x) for x in row.get('domaines_ids', '').split(',') if x.isdigit()]
                domaines = Domaine.objects.filter(id__in=domaines_ids)

                # Universités
                univ_ids = [int(x) for x in row.get('universites_ids', '').split(',') if x.isdigit()]
                universites = Universite.objects.filter(id__in=univ_ids)

                # Encadreurs
                enc_ids = [int(x) for x in row.get('encadreurs_ids', '').split(',') if x.isdigit()]
                encadreurs = User.objects.filter(id__in=enc_ids)

                # PDF
                pdf_url = row.get('fichier_pdf_url', '').strip()
                if not pdf_url:
                    raise ValueError("fichier_pdf_url manquant")

                # Téléchargement du PDF
                local_name = f"batch_{uuid.uuid4().hex}.pdf"
                local_path = os.path.join(settings.MEDIA_ROOT, 'memoires', 'batch', local_name)
                os.makedirs(os.path.dirname(local_path), exist_ok=True)

                r = requests.get(pdf_url, stream=True, timeout=30)
                r.raise_for_status()
                with open(local_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

                # Création du mémoire
                memoire = Memoire.objects.create(
                    titre=titre,
                    resume=resume,
                    annee=annee,
                    auteur=auteur,
                )
                # On attache le fichier
                with open(local_path, 'rb') as f:
                    memoire.fichier_pdf.save(local_name, File(f), save=True)

                memoire.domaines.set(domaines)
                memoire.universites.set(universites)

                # Encadrements
                for enc in encadreurs:
                    Encadrement.objects.create(memoire=memoire, encadreur=enc)

                created += 1

            except Exception as e:
                errors.append({"ligne": row_num, "erreur": str(e), "data": row})

        return {"created": created, "errors": errors}

# ------------------------------------------------------------------
# 12. Batch ZIP – upload en masse
# ------------------------------------------------------------------
class BatchUploadSerializer(serializers.Serializer):
    zip_file = serializers.FileField()
    annee = serializers.IntegerField(required=False, help_text="Année par défaut pour tous les mémoires")
    domaines_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, help_text="IDs des domaines à attribuer"
    )
    universites_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, help_text="IDs des universités à attribuer"
    )
    encadreurs_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, help_text="IDs des encadreurs à attribuer"
    )

    def validate_zip_file(self, value):
        if not value.name.lower().endswith('.zip'):
            raise serializers.ValidationError("Le fichier doit être au format ZIP.")
        return value

    def save(self, **kwargs):
        """
        Traite le ZIP :
        - extrait chaque PDF
        - crée un mémoire par fichier
        - attache domaines, univ, encadreurs
        - retourne nb créés
        """
        from zipfile import ZipFile
        import os
        from django.core.files import File

        request = self.context['request']
        zip_file = self.validated_data['zip_file']
        annee = self.validated_data.get('annee', 2024)
        domaines = Domaine.objects.filter(id__in=self.validated_data.get('domaines_ids', []))
        universites = Universite.objects.filter(id__in=self.validated_data.get('universites_ids', []))
        encadreurs = User.objects.filter(id__in=self.validated_data.get('encadreurs_ids', []))

        created = 0
        errors = []

        with ZipFile(zip_file) as z:
            for info in z.infolist():
                if info.is_dir() or not info.filename.lower().endswith('.pdf'):
                    continue
                try:
                    # Nom du fichier sans extension
                    titre = os.path.splitext(os.path.basename(info.filename))[0]
                    # Extraction temporaire
                    with z.open(info) as f:
                        local_name = f"batch_zip_{uuid.uuid4().hex}.pdf"
                        local_path = os.path.join(settings.MEDIA_ROOT, 'memoires', 'batch_zip', local_name)
                        os.makedirs(os.path.dirname(local_path), exist_ok=True)
                        with open(local_path, 'wb') as tmp:
                            tmp.write(f.read())

                    # Création du mémoire
                    memoire = Memoire.objects.create(
                        titre=titre,
                        resume=f"Mémoire extrait du ZIP : {titre}",
                        annee=annee,
                        auteur=request.user,
                    )
                    # Attachement du fichier
                    with open(local_path, 'rb') as f:
                        memoire.fichier_pdf.save(local_name, File(f), save=True)

                    # Relations many-to-many
                    memoire.domaines.set(domaines)
                    memoire.universites.set(universites)
                    for enc in encadreurs:
                        Encadrement.objects.create(memoire=memoire, encadreur=enc)

                    created += 1

                except Exception as e:
                    errors.append({"fichier": info.filename, "erreur": str(e)})

        return {"created": created, "errors": errors}    
# memoires/serializers.py  (ajout à la fin)

class SignalementSerializer(serializers.ModelSerializer):
    # Champs en lecture seule
    utilisateur = serializers.HiddenField(default=serializers.CurrentUserDefault())
    memoire_titre = serializers.CharField(source='memoire.titre', read_only=True)

    class Meta:
        model = Signalement
        fields = [
            'id',
            'memoire',
            'memoire_titre',
            'utilisateur',
            'motif',
            'commentaire',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'memoire_titre', 'utilisateur']    
# memoires/serializers.py  (ajout à la fin)

class HistoricalMemoireSerializer(serializers.ModelSerializer):
    # On expose l’historique complet
    auteur_email = serializers.CharField(source='auteur.email', read_only=True)
    domaines_noms = serializers.SerializerMethodField()
    universites_noms = serializers.SerializerMethodField()
    history_date = serializers.DateTimeField(read_only=True)
    history_type = serializers.CharField(read_only=True)
    history_user = serializers.CharField(source='history_user.email', read_only=True)
    class Meta:
        model = Memoire.history.model  # historical model
        fields = [
            'id',
            'titre',
            'resume',
            'annee',
            'auteur_email',
            'domaines_noms',
            'universites_noms',
            'history_date',
            'history_type',
            'history_user',
        ]

    def get_domaines_noms(self, obj):
        return list(obj.domaines.values_list('nom', flat=True))

    def get_universites_noms(self, obj):
        return list(obj.universites.values_list('nom', flat=True))     
from rest_framework import serializers
from .models import Notation

class NotationSerializer(serializers.ModelSerializer):
    utilisateur_email = serializers.CharField(source='utilisateur.email', read_only=True)
    memoire_titre = serializers.CharField(source='memoire.titre', read_only=True)

    class Meta:
        model = Notation
        fields = ['id', 'utilisateur', 'utilisateur_email', 'memoire', 'memoire_titre', 'note', 'created_at']
        read_only_fields = ['created_at']       
    