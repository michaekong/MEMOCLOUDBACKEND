# users/views.py
import logging
import json
from django.utils.encoding import force_str 
import urllib.parse
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.conf import settings
from django.core.mail import send_mail, EmailMessage
from django.template.loader import render_to_string
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.vary import vary_on_cookie
from universites.models import Universite, RoleUniversite
from users.models import InvitationCode
from users.permissions import IsAdminInUniversite
from django.http import HttpResponse
from django.db.models import Count, Q
import csv
from rest_framework import generics, status, permissions, filters, viewsets
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from memoires.models import Memoire
from .serializers import (
    RegisterSerializer,
    UserSerializer,
    LoginSerializer,
    ChangePasswordSerializer,
    RegisterViaUniversiteSerializer2,
    ResetPasswordRequestSerializer,
    InviteUserSerializer,
    JoinWithCodeSerializer,
    ResetPasswordConfirmSerializer,
    UserRoleSerializer,
    RegisterViaUniversiteSerializer,
    VerifyEmailSerializer,
    RoleUpdateSerializer,
    UserDeactivateSerializer,
    RoleSerializer,
    RoleUpdateSerializer,
)
from users.tokens import make_email_token, verify_email_token
from urllib.parse import urljoin
User = get_user_model()
logger = logging.getLogger(__name__)


# -------------------- Inscription (double password) --------------------
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        token = make_email_token(user.id)
        verify_url = f"{settings.FRONTEND_URL}/verify-email.html?token={token}"

        html_content = render_to_string(
            "emails/verify_email.html", {"verification_url": verify_url}
        )
        email = EmailMessage(
            subject="Verify your email",
            body=html_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email.content_subtype = "html"
        email.send(fail_silently=False)
        logger.info(f"Verification email sent to {user.email}")


class RegisterViaUniversiteView(generics.CreateAPIView):
    """
    POST /api/auth/<univ_slug>/register/
    Crée un compte et l’ajoute immédiatement à l’université <univ_slug>.
    """

    serializer_class = RegisterViaUniversiteSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        # envoi du mail de vérification
        token = make_email_token(user.id)
        verify_url = f"{settings.FRONTEND_URL}/verify-email.html?token={token}"

        html_content = render_to_string(
            "emails/verify_email.html", {"verification_url": verify_url}
        )
        email = EmailMessage(
            subject="Vérifiez votre adresse email",
            body=html_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email.content_subtype = "html"
        email.send(fail_silently=False)
        logger.info(f"Email de vérification envoyé à {user.email}")


# -------------------- Vérification e-mail (POST) --------------------
@method_decorator(never_cache, name="dispatch")
class VerifyEmailView(GenericAPIView):
    serializer_class = VerifyEmailSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]
        uid = verify_email_token(token)
        if not uid:
            logger.warning(f"Invalid verification token : {token}")
            return Response(
                {"detail": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = get_object_or_404(User, pk=uid)
        if user.is_active:
            return Response({"detail": "Email already verified."})
        user.is_active = True
        user.save(update_fields=["is_active"])
        logger.info(f"Email verified for user {user.email}")
        return Response({"detail": "Email verified. You can now log in."})

class CurrentUserView(generics.RetrieveAPIView):
    """
    GET /api/auth/me/
    Renvoie l’utilisateur connecté à partir du JWT.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
import ipaddress    
# -------------------- Connexion (JWT) + anti-brute --------------------
@method_decorator(vary_on_cookie, name="dispatch")
class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]

    def get_client_ip(self, request):
        """
        Récupère l'IP client de manière sécurisée.
        Version sans proxy : utilise uniquement REMOTE_ADDR.
        """
        ip = request.META.get("REMOTE_ADDR")
        
        if not ip:
            return None
        
        try:
            # Valide IPv4 ou IPv6
            ipaddress.ip_address(ip)
            return ip
        except (ValueError, TypeError):
            return None

    def post(self, request, *args, **kwargs):
        ip = self.get_client_ip(request)
        
        # Protection si IP invalide
        if ip is None:
            logger.error("Unable to determine client IP")
            return Response(
                {"detail": "Security error."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Rate limiting
        cache_key = f"login_attempt_{ip}"
        attempts = cache.get(cache_key, 0)
        
        if attempts >= 5:
            logger.warning(f"Too many login attempts from {ip}")
            return Response(
                {"detail": f"Too many attempts, please try again {ip} later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Validation credentials
        serializer = self.get_serializer(data=request.data)
        
        if not serializer.is_valid():
            # Incrémente le compteur SEULEMENT en cas d'échec
            cache.set(cache_key, attempts + 1, timeout=300)  # 5 minutes
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.validated_data["user"]
        
        # Succès : reset du compteur
        cache.delete(cache_key)
        
        # Génération JWT
        refresh = RefreshToken.for_user(user)
        logger.info(f"Successful login for {user.email} from {ip}")

        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": UserSerializer(user).data,
        })

# -------------------- Profil personnel --------------------
class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch"]

    def get_object(self):
        return self.request.user


# -------------------- Changement de mot de passe --------------------
class ChangePasswordView(GenericAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not user.check_password(serializer.validated_data["old_password"]):
            logger.warning(f"Wrong old password for user {user.email}")
            return Response(
                {"old_password": ["Incorrect password."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        logger.info(f"Password changed for user {user.email}")
        return Response({"detail": "Password changed successfully."})


class ResetPasswordRequestView(GenericAPIView):
    serializer_class = ResetPasswordRequestSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data["email"]
        new_password = serializer.validated_data["new_password1"]
        
        user = User.objects.filter(email=email).first()
        if not user:
            logger.info(f"Password reset requested for non-existent email {email}")
            return Response(
                {"detail": "If the address exists, you will receive a confirmation email."}
            )

        token = PasswordResetTokenGenerator().make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        print("uuid",   uid)
        params = {
            'uidb64': uid,
            'token': token,
            'new_password': new_password
        }

        # Convertir en JSON et encoder
        params_json = json.dumps(params)
        encoded_params = urllib.parse.quote(params_json)
        reset_link = f"{settings.FRONTEND_URL}/confirm-reset-password.html?params={encoded_params}"

        logger.debug(f"Reset link: {reset_link}")

        html_content = render_to_string(
            "emails/reset_password_confirmation_email.html", 
            {
                "reset_password_url": reset_link,
                "user_name": user.get_full_name(),
                "user_email": user.email
            }
        )
        
        email_message = EmailMessage(
            subject="Confirm your password reset",
            body=html_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email_message.content_subtype = "html"
        email_message.send(fail_silently=False)

        logger.info(f"Password reset confirmation email sent to {user.email}")
        return Response({"detail": "If the address exists, you will receive a confirmation email."})

# -------------------- Confirmation réinitialisation --------------------
class ResetPasswordConfirmView(GenericAPIView):
    permission_classes = [permissions.AllowAny]
    http_method_names = ['get']

    def get(self, request):
        params_encoded = request.GET.get('params')
        
        if not params_encoded:
            return Response({'detail': 'Paramètres manquants.'}, status=400)

        # Décodage et désérialisation JSON
        try:
            params_encoded = urllib.parse.unquote(params_encoded)
            logger.debug(f"Decoded params: {params_encoded}")
            params = json.loads(params_encoded)

            uidb64 = params['uidb64']
            token = params['token']
            new_password = params['new_password']
        except json.JSONDecodeError:
            logger.error('Erreur de désérialisation JSON pour les paramètres')
            return Response({'detail': 'Paramètres mal formés.'}, status=400)
        except KeyError as e:
            logger.error(f'Paramètre manquant: {e}')
            return Response({'detail': 'Paramètre manquant.'}, status=400)

        # Vérification utilisateur + token
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            
            user = User.objects.get(pk=uid)
        except (ValueError, OverflowError, User.DoesNotExist):
            return Response({'detail': 'Lien invalide.'}, status=400)

        if not PasswordResetTokenGenerator().check_token(user, token):
            logger.error(f"Token validation failed for {user.email} with token {token}")
            return Response({'detail': 'Lien invalide ou expiré.'}, status=400)
        print(uid)
        # Réinitialisation
        user.set_password(new_password)
        user.save()
        return Response({'detail': 'Mot de passe réinitialisé.'})
class GetUserByEmailView(GenericAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        email = request.query_params.get("email")
        if not email:
            return Response(
                {"detail": "Email parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = get_object_or_404(User, email=email)
        serializer = self.get_serializer(user)
        return Response(serializer.data)

class UserProfileView(generics.RetrieveAPIView):
    """
    API View pour récupérer le profil d'un utilisateur, y compris ses informations 
    d'université et de rôle, basé sur le slug de l'université.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, univ_slug, *args, **kwargs):
        # Récupérer l'université par son slug
        universite = get_object_or_404(Universite, slug=univ_slug)

        # Obtenir les informations de l'utilisateur
        user_id = kwargs.get('pk')
        user = get_object_or_404(User, pk=user_id)

        # Vérifier le rôle de l'utilisateur dans l'université
        role = get_object_or_404(RoleUniversite, utilisateur=user, universite=universite)

        # Préparer les données à renvoyer
        user_data = {
            'id': user.id,
            'email': user.email,
            'prenom': user.prenom,
            'nom': user.nom,
            'sexe': user.sexe,
            'type': user.type,
            'realisation_linkedin': user.realisation_linkedin,
            'photo_profil': request.build_absolute_uri(user.photo_profil.url) if user.photo_profil else None,
            'universite': universite.nom,
            'role': role.role,
        }

        return Response(user_data)


# -------------------- Admin : changement de rôle --------------------
class RoleUpdateView(GenericAPIView):
    serializer_class = RoleUpdateSerializer
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, *args, **kwargs):
        user = get_object_or_404(User, pk=kwargs["pk"])
        serializer = self.get_serializer(user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Rôle mis à jour.", "new_role": user.type})


# -------------------- Désactivation sécurisée (soft-delete) --------------------
class DeactivateAccountView(GenericAPIView):
    serializer_class = UserDeactivateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Compte désactivé."})


# -------------------- CRUD complet (admin) --------------------
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ["email", "prenom", "nom"]

    def get_permissions(self):
        if self.action in ["update", "partial_update", "destroy"]:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]


# users/views.py
from django_filters import rest_framework as df_filters
from django_filters.filters import CharFilter

class UserFilter(df_filters.FilterSet):
    role = CharFilter(field_name="roles_univ__role", lookup_expr="iexact")

    class Meta:
        model = User
        fields = ["roles_univ__role"]

class UniversiteUsersListView(generics.ListAPIView):
    serializer_class = UserSerializer   # tu peux garder le tien
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [
        filters.SearchFilter,
        filters.OrderingFilter,
        df_filters.DjangoFilterBackend,   # <-- ajout
    ]
    filterset_class = UserFilter         # <-- ajout
    search_fields = ["nom", "prenom", "email"]
    ordering_fields = ["date_joined", "nom"]

    def get_queryset(self):
        univ = get_object_or_404(Universite, slug=self.kwargs["univ_slug"])
        return User.objects.filter(roles_univ__universite=univ).distinct()

class UniversiteUserAddView(GenericAPIView):
    permission_classes = [IsAdminInUniversite]  # Vérifie que l'utilisateur est admin
    serializer_class = UserRoleSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        role = serializer.validated_data.get("role", "standard")

        user = get_object_or_404(User, email=email)
        univ = get_object_or_404(Universite, slug=kwargs["univ_slug"])

        # Vérifie que l'utilisateur requérant le changement a bien le rôle admin dans cette université
        if not univ.roles.filter(utilisateur=request.user, role__in=['admin', 'superadmin', 'bigboss']).exists():
            return Response({"detail": "Vous n'avez pas les droits nécessaires."}, status=status.HTTP_403_FORBIDDEN)

        obj, created = RoleUniversite.objects.get_or_create(
            utilisateur=user, universite=univ, defaults={"role": role}
        )

        if not created:
            return Response({"detail": "Déjà membre."}, status=status.HTTP_200_OK)

        return Response({"detail": "Membre ajouté."}, status=status.HTTP_201_CREATED)


# users/views.py
class UniversiteInviteUserView(GenericAPIView):
    permission_classes = [IsAdminInUniversite]  # Vérifie que l'utilisateur est admin
    serializer_class = InviteUserSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        role = serializer.validated_data.get("role", "standard")
        univ = get_object_or_404(Universite, slug=kwargs["univ_slug"])

        # Vérifie que l'utilisateur requérant l'invitation a bien le rôle admin dans cette université
        if not univ.roles.filter(utilisateur=request.user, role__in=['admin', 'superadmin', 'bigboss']).exists():
            return Response({"detail": "Vous n'avez pas les droits nécessaires."}, status=status.HTTP_403_FORBIDDEN)

        # Créez le code d'invitation
        code_obj = InvitationCode.objects.create(
            universite=univ, role=role, created_by=request.user
        )

        # Envoyer un e-mail d'invitation
        invite_url = f"{settings.FRONTEND_URL}/join-with-code/?code={code_obj.code}"
        html = render_to_string(
            "emails/invite_user_preset_role.html",
            {
                "invite_url": invite_url,
                "univ": univ,
                "role": role,
            },
        )
        email_message = EmailMessage(
            subject=f"Invitation à rejoindre {univ.nom}",
            body=html,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        email_message.content_subtype = "html"

        email_message.send(fail_silently=False)
        logger.info(f"Invitation email sent to {email}")
        
        return Response({"detail": "Invitation envoyée.", "email": email}, status=status.HTTP_201_CREATED)


# users/views.py
class JoinWithCodeView(GenericAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = JoinWithCodeSerializer  # Ajout du sérialiseur

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)  # Validation des données entrantes

        raw_code = serializer.validated_data["code"]  # Obtention du code validé

        
        code_obj = get_object_or_404(InvitationCode, code=raw_code)

        # Vérification si le code est expiré ou déjà utilisé
        if code_obj.is_expired or code_obj.used_by:
            return Response(
                {"detail": "Code invalide ou déjà utilisé."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    
        user = request.user if request.user.is_authenticated else None
        if not user:
            return Response(
                {"detail": "Connectez-vous ou créez un compte avant de rejoindre."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Rôle forcé depuis le code d'invitation
        RoleUniversite.objects.get_or_create(
            utilisateur=user,
            universite=code_obj.universite,
            defaults={"role": code_obj.role},
        )

        # Marquer le code comme utilisé
        code_obj.used_by = user
        code_obj.save()

        return Response(
            {
                "detail": f"Bienvenue dans {code_obj.universite.nom} en tant que {code_obj.get_role_display()} !"
            }
        )
    def get(self, request, *args, **kwargs):
        code = request.query_params.get("code")  # Obtention du code via les paramètres de l'URL

        if not code:
            return Response(
                {"detail": "Code d'invitation manquant."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code_obj = get_object_or_404(InvitationCode, code=code)

        # Vérification si le code est expiré ou déjà utilisé
        if code_obj.is_expired or code_obj.used_by:
            return Response(
                {"detail": "Code invalide ou déjà utilisé."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user if request.user.is_authenticated else None
        if not user:
            # Ici, vous pouvez créer le compte utilisateur ou rediriger vers la page d'inscription,
            # ou toute autre logique que vous souhaitez.
            return Response(
                {"detail": "Code reçu ! Veuillez vous connecter ou créer un compte."},
                status=status.HTTP_200_OK,  # Répondez sans erreur
            )

        # Rôle forcé depuis le code d'invitation
        RoleUniversite.objects.get_or_create(
            utilisateur=user,
            universite=code_obj.universite,
            defaults={"role": code_obj.role},
        )

        # Marquer le code comme utilisé
        code_obj.used_by = user
        code_obj.save()

        return Response(
            {
                "detail": f"Bienvenue dans {code_obj.universite.nom} en tant que {code_obj.get_role_display()} !"
            },
            status=status.HTTP_200_OK,
        )
class UniversiteUserRemoveView(GenericAPIView):
    permission_classes = [IsAdminInUniversite]

    def delete(self, request, *args, **kwargs):
        user_id = kwargs["user_id"]
        univ = get_object_or_404(Universite, slug=kwargs["univ_slug"])
        role_obj = get_object_or_404(
            RoleUniversite, utilisateur_id=user_id, universite=univ
        )
        role_obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UniversiteUserRoleUpdateView(GenericAPIView):
    permission_classes = [IsAdminInUniversite]
    serializer_class = RoleUpdateSerializer

    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_role = serializer.validated_data["role"]
        univ = get_object_or_404(Universite, slug=kwargs["univ_slug"])
        role_obj = get_object_or_404(
            RoleUniversite, utilisateur_id=kwargs["user_id"], universite=univ
        )

        # Met à jour le rôle
        role_obj.role = new_role
        role_obj.save()

        return Response({"detail": "Rôle mis à jour."}, status=status.HTTP_200_OK)


class UniversiteUsersExportCSVView(generics.GenericAPIView):
    permission_classes = [IsAdminInUniversite]
    serializer_class = RoleSerializer

    def get(self, request, *args, **kwargs):
        univ = get_object_or_404(Universite, slug=kwargs["univ_slug"])
        users = User.objects.filter(roles_univ__universite=univ).distinct()
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="{univ.slug}_membres.csv"'
        )
        writer = csv.writer(response)
        writer.writerow(["Nom", "Prénom", "Email", "Rôle", "Date d’arrivée"])
        for u in users:
            role = u.roles_univ.filter(universite=univ).first()
            writer.writerow(
                [
                    u.nom,
                    u.prenom,
                    u.email,
                    role.role if role else "",
                    role.created_at.date() if role else "",
                ]
            )
        return response


class UniversiteTopContribView(generics.GenericAPIView):
    permission_classes =[permissions.AllowAny]
    def get(self, request, *args, **kwargs):
        from interactions.models import Telechargement

        univ = get_object_or_404(Universite, slug=kwargs["univ_slug"])
        data = (
            User.objects.filter(memoires__universites=univ)
            .annotate(
                nb_memoires=Count("memoires", distinct=True),
                nb_telechargements=Count("memoires__telechargements", distinct=True),
            )
            .order_by("-nb_memoires", "-nb_telechargements")[:10]
            .values("id", "nom", "prenom", "nb_memoires", "nb_telechargements")
        )
        return Response(data)


class UniversiteUserSearchView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        univ = get_object_or_404(Universite, slug=self.kwargs["univ_slug"])
        q = self.request.GET.get("q", "")
        if len(q) < 2:
            return User.objects.none()
        return (
            User.objects.filter(roles_univ__universite=univ)
            .filter(Q(nom__icontains=q) | Q(prenom__icontains=q) | Q(email__icontains=q))
            .distinct()[:20]
        )


class UniversiteAnnuaireView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        univ = get_object_or_404(Universite, slug=self.kwargs["univ_slug"])
        return User.objects.filter(roles_univ__universite=univ, is_active=True).distinct()


from django.db.models import Count, Q
from django.utils import timezone
from dateutil.relativedelta import relativedelta


class UniversiteUsersStatsView(generics.GenericAPIView):
    permission_classes =  [permissions.AllowAny] 

    def get(self, request, *args, **kwargs):
        univ = get_object_or_404(Universite, slug=kwargs["univ_slug"])

        # 1. répartition par rôle
        role_counts = (
            RoleUniversite.objects.filter(universite=univ)
            .values("role")
            .annotate(total=Count("id"))
            .order_by("-total")
        )

        # 2. évolution mensuelle (12 derniers mois)
        monthly = []
        today = timezone.now().date()
        for i in range(12):
            start = today - relativedelta(months=i + 1)
            end = today - relativedelta(months=i)
            count = RoleUniversite.objects.filter(
                universite=univ, created_at__date__gte=start, created_at__date__lt=end
            ).count()
            monthly.append({"month": start.strftime("%Y-%m"), "new_members": count})

        # 3. actif / inactif
        members = User.objects.filter(roles_univ__universite=univ).distinct()
        active_count = members.filter(is_active=True).count()
        inactive_count = members.filter(is_active=False).count()
        memoires=Memoire.objects.filter(universites=univ).distinct()

        return Response(
            {
                "universite": univ.nom,
                "total_membres": members.count(),
                "actif": active_count,
                "inactif": inactive_count,
                "total_memoires": memoires.count(),
                "repartition_roles": {r["role"]: r["total"] for r in role_counts},
                "evolution_mensuelle": list(
                    reversed(monthly)
                ),  # du plus ancien au plus récent
            }
        )


# users/views.py
import secrets
from rest_framework import serializers


class BulkCodesSerializer(serializers.Serializer):
    nb = serializers.IntegerField(min_value=1, max_value=500)
    role = serializers.ChoiceField(
        choices=RoleUniversite.ROLE_CHOICES, default="standard"
    )


class UniversiteBulkCodesView(generics.CreateAPIView):
    permission_classes = [IsAdminInUniversite]
    serializer_class = BulkCodesSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        nb = serializer.validated_data["nb"]
        role = serializer.validated_data["role"]
        univ = get_object_or_404(Universite, slug=kwargs["univ_slug"])

        codes_clear = []  # versions claires pour l’admin
        for _ in range(nb):
            raw = secrets.token_urlsafe(32)
            InvitationCode.objects.create(
                code=InvitationCode.encrypt(raw),
                universite=univ,
                role=role,
                created_by=request.user,
            )
            codes_clear.append(raw)

        # on renvoie les codes à l’admin (à copier ou à intégrer dans un CSV)
        return Response(
            {
                "detail": f"{nb} codes générés.",
                "role": role,
                "codes": codes_clear,  # ⚠️ à ne **jamais** renvoyer au public
            },
            status=status.HTTP_201_CREATED,
        )



class UpdateRoleView(generics.UpdateAPIView):
    """
    PATCH /api/auth/<slug:univ_slug>/users/<int:pk>/role/
    Modifie uniquement le rôle d’un utilisateur dans l’université.
    """
    serializer_class = serializers.Serializer   # on n’a pas besoin de serializer compliqué
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'pk'
    queryset = User.objects.all()

    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        new_role = request.data.get('role')

        if new_role not in dict(RoleUniversite.ROLE_CHOICES):
            return Response({'detail': 'Rôle invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        role_obj, created = RoleUniversite.objects.get_or_create(
            utilisateur=user,
            universite__slug=kwargs['univ_slug'],
            defaults={'role': new_role, 'universite_id': kwargs['univ_slug']}
        )
        if not created:
            role_obj.role = new_role
            role_obj.save()

        return Response({'detail': 'Rôle mis à jour.'}, status=status.HTTP_200_OK)