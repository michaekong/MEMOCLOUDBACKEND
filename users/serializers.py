# users/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _

User = get_user_model()


# -------------------- Utilisateur (profil, CRUD) --------------------
class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    role_display = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "nom",
            "prenom",
            "full_name",
            "sexe",
            "type",
            "role_display",
            "realisation_linkedin",
            "photo_profil",
            "is_active",
            "date_joined",
        ]
        read_only_fields = ["id", "is_active", "date_joined", "type"]

    def get_full_name(self, obj):
        return obj.get_full_name()

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        request = self.context.get("request")
        if request and request.user != instance:
            # garder l'email visible aux membres de la même université
            same_univ = instance.roles_univ.filter(
                universite__slug=request.user.roles_univ.first().universite.slug
            ).exists()
            if not same_univ:
                rep.pop("email", None)
        return rep


# -------------------- Inscription (double password) --------------------
class RegisterSerializer(serializers.ModelSerializer):
    password1 = serializers.CharField(
        write_only=True,
        label="Mot de passe",
        style={"input_type": "password"},
        validators=[validate_password],
    )
    password2 = serializers.CharField(
        write_only=True,
        label="Confirmer le mot de passe",
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = [
            "email",
            "nom",
            "prenom",
            "sexe",
            "type",
            "realisation_linkedin",
            "photo_profil",
            "password1",
            "password2",
        ]

    def validate(self, attrs):
        if attrs["password1"] != attrs["password2"]:
            raise serializers.ValidationError(
                {"password2": "Les mots de passe ne correspondent pas."}
            )
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password1")
        validated_data.pop("password2")
        user = User(**validated_data)
        user.set_password(password)
        user.is_active = False  # jusqu’à vérification
        user.save()
        return user


# -------------------- Connexion (JWT) --------------------
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")
        user = authenticate(
            request=self.context.get("request"), email=email, password=password
        )
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        attrs["user"] = user
        return attrs


# -------------------- Changement de mot de passe --------------------
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])


# -------------------- Vérification d’e-mail (POST) --------------------
class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.CharField()


# -------------------- Admin : changement de rôle --------------------
class RoleUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["type"]

    def validate_type(self, value):
        if value not in User.Type.values:
            raise serializers.ValidationError("Rôle inconnu.")
        return value

    def update(self, instance, validated_data):
        instance.promote(validated_data["type"])
        return instance


# -------------------- Désactivation sécurisée (soft-delete) --------------------
class UserDeactivateSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["password"]):
            raise serializers.ValidationError("Mot de passe incorrect.")
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        user.is_active = False
        user.save(update_fields=["is_active"])
        return user


from rest_framework import serializers
from django.contrib.auth import get_user_model
from universites.models import Universite, RoleUniversite

User = get_user_model()


class RegisterViaUniversiteSerializer(serializers.ModelSerializer):
    password1 = serializers.CharField(write_only=True, style={"input_type": "password"})
    password2 = serializers.CharField(write_only=True, style={"input_type": "password"})
    role = serializers.ChoiceField(
        choices=RoleUniversite.ROLE_CHOICES, default="standard"
    )
    universite_slug = serializers.SlugField(write_only=True)
    realisation_linkedin = serializers.URLField(required=False, allow_blank=True)
    photo_profil = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            "email",
            "nom",
            "prenom",
            "sexe",
            "password1",
            "password2",
            "role",
            "universite_slug",
            "realisation_linkedin",
            "photo_profil",
        ]

    def validate(self, attrs):
        if attrs["password1"] != attrs["password2"]:
            raise serializers.ValidationError(
                {"password2": "Les mots de passe ne correspondent pas."}
            )
        if not Universite.objects.filter(slug=attrs["universite_slug"]).exists():
            raise serializers.ValidationError({"universite_slug": "Université inconnue."})
        return attrs
    def validate_photo_profil(self, value):
        # Vérifier que le fichier est bien une image
        if value:
            if not value.name.endswith(('.png', '.jpg', '.jpeg')):
                raise ValidationError(_("Le fichier doit être au format PNG, JPG ou JPEG."))
            if value.size > 2 * 1024 * 1024:  # Limite de 2 Mo
                raise ValidationError(_("La taille du fichier ne doit pas dépasser 2 Mo."))
        return value
    def create(self, validated_data):
        user_data = {
            "email": validated_data["email"],
            "nom": validated_data["nom"],
            "prenom": validated_data["prenom"],
            "sexe": validated_data["sexe"],
            "realisation_linkedin": validated_data.get("realisation_linkedin"),
            "photo_profil": validated_data.get("photo_profil"),
        }
        user = User(**user_data)
        user.set_password(validated_data["password1"])
        user.is_active = False  # jusqu’à vérification
        user.save()

        univ = Universite.objects.get(slug=validated_data["universite_slug"])
        RoleUniversite.objects.create(
            utilisateur=user, universite=univ, role=validated_data["role"]
        )
        # 4. Récupérer les universités mères et créer des rôles pour chacune d'elles
        universites_meres = univ.get_universites_meres()
        role = validated_data.pop("role")  # Assurez-vous que le rôle est récupéré une seule fois
        for affiliation in universites_meres:
            RoleUniversite.objects.create(
                utilisateur=user,
                universite=affiliation.universite_mere,
                role=role
            )

        return user


class UserRoleSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=RoleUniversite.ROLE_CHOICES, required=False, default="standard"
    )


class RoleSerializer(serializers.Serializer):

    role = serializers.ChoiceField(
        choices=RoleUniversite.ROLE_CHOICES, required=False, default="standard"
    )


class RoleUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=RoleUniversite.ROLE_CHOICES)


class InviteUserSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=RoleUniversite.ROLE_CHOICES, required=False, default="standard"
    )


class JoinWithCodeSerializer(serializers.Serializer):
    code = serializers.CharField(
        required=True, help_text="Le code d'invitation à utiliser."
    )


class ResetPasswordRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    new_password1 = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )
    new_password2 = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )

    def validate(self, attrs):
        if attrs["new_password1"] != attrs["new_password2"]:
            raise serializers.ValidationError(
                {"new_password2": "Les mots de passe ne correspondent pas."}
            )
        return attrs


class ResetPasswordConfirmSerializer(serializers.Serializer):
    uidb64 = serializers.CharField(required=True)
    token = serializers.CharField(required=True)
    new_password1 = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )
    new_password2 = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )

    def validate(self, attrs):
        if attrs["new_password1"] != attrs["new_password2"]:
            raise serializers.ValidationError(
                {"new_password2": "Les mots de passe ne correspondent pas."}
            )
        return attrs

# dans la même app que UserSerializer
class RegisterViaUniversiteSerializer2(RegisterSerializer):
    universite_slug = serializers.SlugField(write_only=True)
    role            = serializers.ChoiceField(choices=RoleUniversite.ROLE_CHOICES, default="standard")
    photo_profil    = serializers.ImageField(required=False, write_only=True)   # <-- nouveau

    class Meta(RegisterSerializer.Meta):
        fields = list(RegisterSerializer.Meta.fields) + [
            "universite_slug", "role", "photo_profil"
        ]

    def create(self, validated_data):
        univ_slug = validated_data.pop("universite_slug")
        role      = validated_data.pop("role")
        photo     = validated_data.pop("photo_profil", None)   # <-- récupération

        # 1. création user
        user = super().create(validated_data)

        # 2. rôle universitaire
        universite = Universite.objects.get(slug=univ_slug)
        RoleUniversite.objects.create(utilisateur=user, universite=universite, role=role)

        # 3. photo si fournie
        if photo:
            user.photo_profil = photo
            user.save(update_fields=["photo_profil"])

        return user
from .models import AuditLog
 
class AuditLogSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    user_name = serializers.SerializerMethodField()
    university_name = serializers.CharField(source='university.nom', read_only=True, default=None)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'created_at', 'action', 'action_display',
            'severity', 'severity_display', 'user_email', 'user_name',
            'user_role', 'university_name', 'target_type', 'target_id',
            'target_repr', 'description', 'ip_address', 'request_method',
            'previous_data', 'new_data'
        ]
        read_only_fields = fields
    
    def get_user_name(self, obj):
        if obj.user:
            return f"{obj.user.prenom} {obj.user.nom}"
        return None


class AuditLogStatsSerializer(serializers.Serializer):
    total_logs = serializers.IntegerField()
    today_logs = serializers.IntegerField()
    critical_actions = serializers.IntegerField()
    actions_distribution = serializers.ListField()
    top_users = serializers.ListField()
    recent_critical = serializers.ListField(child=AuditLogSerializer())    
# users/serializers.py
from rest_framework import serializers
from .models import AuditLog, CustomUser


# ============ SERIALIZERS AUDIT LOG ============

class AuditLogListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des logs (léger)."""
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    user_name = serializers.SerializerMethodField()
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'created_at',
            'action', 'action_display',
            'severity', 'severity_display',
            'user_email', 'user_name', 'user_role',
            'target_type', 'target_id', 'target_repr',
            'description',
            'ip_address',
        ]
        read_only_fields = fields
    
    def get_user_name(self, obj):
        if obj.user:
            return f"{obj.user.prenom} {obj.user.nom}"
        return None


class AuditLogDetailSerializer(serializers.ModelSerializer):
    """Serializer pour le détail complet d'un log."""
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    user_name = serializers.SerializerMethodField()
    university_name = serializers.CharField(source='university.nom', read_only=True, default=None)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'created_at',
            'action', 'action_display',
            'severity', 'severity_display',
            'user', 'user_email', 'user_name', 'user_role',
            'university', 'university_name',
            'target_type', 'target_id', 'target_repr',
            'previous_data', 'new_data',
            'description',
            'ip_address', 'user_agent', 'request_path', 'request_method',
        ]
        read_only_fields = fields
    
    def get_user_name(self, obj):
        if obj.user:
            return f"{obj.user.prenom} {obj.user.nom}"
        return None


class AuditLogStatsSerializer(serializers.Serializer):
    """Serializer pour les statistiques du dashboard."""
    # Stats globales
    total_logs = serializers.IntegerField()
    today_logs = serializers.IntegerField()
    this_week_logs = serializers.IntegerField()
    this_month_logs = serializers.IntegerField()
    critical_logs = serializers.IntegerField()
    
    # Distributions
    actions_distribution = serializers.ListField(
        child=serializers.DictField()
    )
    severity_distribution = serializers.ListField(
        child=serializers.DictField()
    )
    daily_evolution = serializers.ListField(
        child=serializers.DictField()
    )
    
    # Utilisateurs
    top_active_users = serializers.ListField(
        child=serializers.DictField()
    )
    
    # Actions récentes
    recent_critical = AuditLogListSerializer(many=True)


class AuditLogActionsChoicesSerializer(serializers.Serializer):
    """Serializer pour les choix d'actions et sévérités."""
    actions = serializers.ListField(
        child=serializers.DictField()
    )
    severities = serializers.ListField(
        child=serializers.DictField()
    )
    action_counts = serializers.DictField(
        child=serializers.IntegerField()
    )    