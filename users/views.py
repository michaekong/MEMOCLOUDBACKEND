# users/views.py
import logging
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

from rest_framework import generics, status, permissions, filters, viewsets
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    RegisterSerializer,
    UserSerializer,
    LoginSerializer,
    ChangePasswordSerializer,
    ResetPasswordRequestSerializer,
    ResetPasswordConfirmSerializer,
    VerifyEmailSerializer,
    RoleUpdateSerializer,
    UserDeactivateSerializer,
)
from .tokens import make_email_token, verify_email_token

User = get_user_model()
logger = logging.getLogger(__name__)


# -------------------- Inscription (double password) --------------------
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        token = make_email_token(user.id)
        verify_url = f"{settings.FRONTEND_URL}/verify-email/?token={token}"

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


# -------------------- Connexion (JWT) + anti-brute --------------------
@method_decorator(vary_on_cookie, name="dispatch")
class LoginView(GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        ip = self.get_client_ip(request)
        cache_key = f"login_attempt_{ip}"
        attempts = cache.get(cache_key, 0)
        if attempts >= 5:
            logger.warning(f"Too many login attempts from {ip}")
            return Response(
                {"detail": "Too many attempts, please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        cache.delete(cache_key)
        refresh = RefreshToken.for_user(user)
        logger.info(f"Successful login for {user.email}")
        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": UserSerializer(user).data,
            }
        )

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip


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


# -------------------- Demande réinitialisation --------------------
class ResetPasswordRequestView(GenericAPIView):
    serializer_class = ResetPasswordRequestSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user = User.objects.filter(email=email).first()
        if not user:
            logger.info(f"Password reset requested for non-existent email {email}")
            return Response({"detail": "If the address exists, you will receive an email."})

        token = PasswordResetTokenGenerator().make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        reset_link = f"{settings.FRONTEND_URL}/reset-password/?uid={uid}&token={token}"
        send_mail(
            subject="Password reset",
            message=f"Reset: {reset_link}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(f"Password reset email sent to {user.email}")
        return Response({"detail": "If the address exists, you will receive an email."})


# -------------------- Confirmation réinitialisation --------------------
class ResetPasswordConfirmView(GenericAPIView):
    serializer_class = ResetPasswordConfirmSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uidb64 = serializer.validated_data["uidb64"]
        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except Exception:
            logger.warning(f"Invalid uid or user during password reset")
            return Response(
                {"detail": "Invalid link."}, status=status.HTTP_400_BAD_REQUEST
            )

        if not PasswordResetTokenGenerator().check_token(user, token):
            logger.warning(f"Invalid or expired token for user {user.email}")
            return Response(
                {"detail": "Invalid token or expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save()
        logger.info(f"Password reset confirmed for user {user.email}")
        return Response({"detail": "Password successfully reset."})


# -------------------- Recherche utilisateur par e-mail --------------------
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