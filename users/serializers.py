# users/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


# -------------------- Utilisateur (profil, CRUD) --------------------
class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    role_display = serializers.CharField(source='get_type_display', read_only=True)

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
        # Masquer l'email aux autres utilisateurs (RGPD)
        request = self.context.get("request")
        if request and request.user != instance:
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
            raise serializers.ValidationError({"password2": "Les mots de passe ne correspondent pas."})
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
        user = authenticate(request=self.context.get("request"), email=email, password=password)
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        attrs["user"] = user
        return attrs


# -------------------- Changement de mot de passe --------------------
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])


# -------------------- Réinitialisation --------------------
class ResetPasswordRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class ResetPasswordConfirmSerializer(serializers.Serializer):
    uidb64 = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])


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