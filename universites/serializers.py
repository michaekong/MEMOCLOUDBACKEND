# universites/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from .models import Universite, Domaine, RoleUniversite, News
import unicodedata
from users.serializers import RegisterSerializer
User = get_user_model()


# ------------------------------------------------------------------
# 1. Université
# ------------------------------------------------------------------
class UniversiteSerializer(serializers.ModelSerializer):
    total_membres = serializers.SerializerMethodField()
    total_domaines = serializers.SerializerMethodField()
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Universite
        fields = [
            'id',
            'nom',
            'acronyme',
            'slogan',
            'logo',
            'logo_url',
            'site_web',
            'slug',
            'created_at',
            'total_membres',
            'total_domaines',
        ]
        read_only_fields = ['id', 'created_at', 'slug', 'total_membres', 'total_domaines', 'logo_url']

    def get_total_membres(self, obj):
        return obj.roles.count()  # related_name='roles' dans RoleUniversite.universite

    def get_total_domaines(self, obj):
        return obj.domaines.count()  # related_name='domaines' dans Domaine.universites

    def get_logo_url(self, obj):
        request = self.context.get('request')
        if obj.logo and request:
            return request.build_absolute_uri(obj.logo.url)
        return None


# ------------------------------------------------------------------
# 2. Domaine
# ------------------------------------------------------------------
class DomaineSerializer(serializers.ModelSerializer):
    # On expose aussi la liste des universités rattachées (lecture seule)
    universites = UniversiteSerializer(many=True, read_only=True)

    class Meta:
        model = Domaine
        fields = ['id', 'nom', 'slug', 'universites']
        read_only_fields = ['id', 'slug']

    # On surcharge create pour forcer la normalisation du slug
    def create(self, validated_data):
        nom = validated_data.get('nom')
        cleaned = unicodedata.normalize('NFKD', nom).encode('ASCII', 'ignore').decode('ASCII')
        slug = slugify(cleaned) or slugify(nom)
        validated_data['slug'] = slug
        return super().create(validated_data)


# ------------------------------------------------------------------
# 3. Rôle par université
# ------------------------------------------------------------------
class RoleUniversiteSerializer(serializers.ModelSerializer):
    # Champs lisibles (read-only)
    utilisateur_email = serializers.CharField(source='utilisateur.email', read_only=True)
    utilisateur_full_name = serializers.SerializerMethodField()
    universite_nom = serializers.CharField(source='universite.nom', read_only=True)

    class Meta:
        model = RoleUniversite
        fields = [
            'id',
            'utilisateur',
            'utilisateur_email',
            'utilisateur_full_name',
            'universite',
            'universite_nom',
            'role',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'utilisateur_email', 'utilisateur_full_name', 'universite_nom']

    def get_utilisateur_full_name(self, obj):
        return obj.utilisateur.get_full_name()


# ------------------------------------------------------------------
# 4. Stats rapides (utilisé par UniversiteStatsView)
# ------------------------------------------------------------------
class UniversiteStatsSerializer(serializers.Serializer):
    # Serializer simple pour la vue stats (pas lié à un modèle)
    universite = serializers.CharField()
    acronyme = serializers.CharField()
    created_at = serializers.DateTimeField()
    total_membres = serializers.IntegerField()
    membres_par_role = serializers.DictField(child=serializers.IntegerField())
    total_domaines = serializers.IntegerField()
class RegisterViaUniversiteSerializer(RegisterSerializer):
    """
    Hérite de RegisterSerializer (double password, validation, etc.)
    On ajoute uniquement les champs université + rôle
    """
    universite_id = serializers.IntegerField(write_only=True)
    role = serializers.ChoiceField(
        choices=RoleUniversite.ROLE_CHOICES,
        default="standard"
    )

    class Meta(RegisterSerializer.Meta):
        # on garde tous les champs du parent + les 2 nouveaux
        fields = RegisterSerializer.Meta.fields + ["universite_id", "role"]

    def validate(self, attrs):
        attrs = super().validate(attrs)  # validation mots de passe
        if not Universite.objects.filter(id=attrs["universite_id"]).exists():
            raise serializers.ValidationError({"universite_id": "Université inconnue."})
        return attrs

    def create(self, validated_data):
        # 1. créer le user via le parent
        user = super().create(validated_data)  # is_active=False déjà mis

        # 2. rattacher à l’université
        univ = Universite.objects.get(id=validated_data.pop("universite_id"))
        RoleUniversite.objects.create(
            utilisateur=user,
            universite=univ,
            role=validated_data.pop("role")
        )
        return user    
class UserRoleSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    universite = serializers.CharField(source='universite.nom', read_only=True)

    class Meta:
        model = RoleUniversite
        fields = ['role', 'role_display', 'universite', 'created_at']    

class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoleUniversite
        fields = ['utilisateur', 'universite', 'role']  # Adjust fields as necessary

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['utilisateur'] = instance.utilisateur.email  # Example to include user's email
        representation['universite'] = instance.universite.nom  # Example to include university name
        return representation        
# news/serializers.py
class NewsSerializer(serializers.ModelSerializer):
    cover_url = serializers.SerializerMethodField()
    publisher_slug = serializers.CharField(source='publisher.slug', read_only=True)
    
    class Meta:
        model = News
        fields = ['id', 'title', 'slug', 'headline', 'body', 'cover',
                  'cover_url', 'topics', 'is_published', 'publish_at',
                  'created_at', 'publisher_slug']
        read_only_fields = ('id', 'slug', 'created_at', 'updated_at')  # ✅ slug en read-only
    
    def get_cover_url(self, obj):
        request = self.context.get('request')
        if obj.cover and request:
            return request.build_absolute_uri(obj.cover.url)
        return None
    
    def create(self, validated_data):
        # ✅ Le publisher est automatiquement assigné
        if 'publisher' not in validated_data:
            validated_data['publisher'] = self.context['request'].user.roles_universite.first().universite
        return super().create(validated_data)