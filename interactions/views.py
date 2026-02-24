# interactions/open_interactions_views.py
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status, viewsets, serializers
from rest_framework.decorators import action
from django.db.models import Avg, Count
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiTypes
from interactions.models import Telechargement, Like, Commentaire
from interactions.serializers import (
    LikeToggleSerializer,
    CommentaireCreateSerializer,
    CommentaireListSerializer,
    TelechargementListSerializer,
    LikeListSerializer,
    SignalementCreateSerializer,
    NotationCreateSerializer,
    NotationListSerializer,
    SignalementListSerializer,
    LikeToggleSerializer,
    TelechargementListSerializer,
    TelechargementCreateSerializer,
    LikeToggleSerializer,
    LikeListSerializer,
    CommentaireCreateSerializer,
    CommentaireListSerializer,
    NotationCreateSerializer,
    NotationListSerializer,
    SignalementCreateSerializer,
    SignalementListSerializer,
)
from rest_framework import viewsets, status

from rest_framework.exceptions import PermissionDenied  # ← Import manquant

# Import de vos utilitaires existants
from users.utils import create_audit_log, AuditLog, get_client_ip


from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from django.conf import settings
from django.utils import timezone
import logging
# Import de vos utilitaires existants
from users.utils import create_audit_log, AuditLog, get_client_ip


logger = logging.getLogger(__name__)

from memoires.models import Memoire, Notation, Signalement
from interactions.permissions import IsAuthenticated, IsAdminOrModerateur

from universites.permissions import IsAdminOfUniversite
# --------------------------------------------------
# 1. Téléchargement (tout user connecté)
# --------------------------------------------------
@extend_schema_view(
    list=extend_schema(
        summary="Mes téléchargements",
        responses={200: TelechargementListSerializer(many=True)},
    ),
)
class TelechargementOpenViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Télécharger un mémoire",
        request=TelechargementCreateSerializer,
    )
    @action(detail=False, methods=["post"], url_path="telecharger")
    def telecharger(self, request):
        memoire = get_object_or_404(Memoire, pk=request.data.get("memoire"))
        
        # Vérifier si c'est la première fois que cet utilisateur télécharge ce mémoire
        telechargement, created = Telechargement.objects.get_or_create(
            utilisateur=request.user,
            memoire=memoire,
            defaults={
                "ip": request.META.get("REMOTE_ADDR"),
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:500],
            },
        )
        
        if not created:
            return Response({"detail": "Déjà téléchargé"}, status=status.HTTP_200_OK)
        
        # Envoyer l'email à l'auteur et aux encadreurs uniquement lors du premier téléchargement
        self.envoyer_email_notification(memoire, request.user)
        
        return Response(
            {
                "detail": "Téléchargement enregistré",
                "pdf_url": request.build_absolute_uri(memoire.fichier_pdf.url),
            },
            status=status.HTTP_201_CREATED,
        )

    def envoyer_email_notification(self, memoire, telechargeur):
        """Envoie un email à l'auteur et aux encadreurs du mémoire pour les informer du téléchargement."""
        try:
            # Préparer les données communes
            telechargeur_nom = f"{telechargeur.prenom} {telechargeur.nom}" if telechargeur.prenom and telechargeur.nom else telechargeur.email
            
            context = {
                "memoire_titre": memoire.titre,
                "telechargeur_nom": telechargeur_nom,
                "telechargeur_email": telechargeur.email,
                "date_telechargement": timezone.now().strftime("%d/%m/%Y à %H:%M"),
                "nombre_total_telechargements": memoire.nb_telechargements(),
                "frontend_url": settings.FRONTEND_URL,
            }
            
            # 1. Envoyer à l'auteur
            auteur = memoire.auteur
            context_auteur = {
                **context,
                "destinataire_type": "auteur",
                "destinataire_nom": f"{auteur.prenom} {auteur.nom}" if auteur.prenom and auteur.nom else auteur.email,
            }
            
            self.envoyer_email_destinataire(
                auteur.email, 
                context_auteur, 
                "Votre mémoire vient d'être téléchargé 📚"
            )
            
            # 2. Envoyer aux encadreurs
            encadrements = memoire.encadrements.select_related('encadreur').all()
            for encadrement in encadrements:
                encadreur = encadrement.encadreur
                context_encadreur = {
                    **context,
                    "destinataire_type": "encadreur",
                    "destinataire_nom": f"{encadreur.prenom} {encadreur.nom}" if encadreur.prenom and encadreur.nom else encadreur.email,
                    "auteur_nom": f"{auteur.prenom} {auteur.nom}" if auteur.prenom and auteur.nom else auteur.email,
                }
                
                self.envoyer_email_destinataire(
                    encadreur.email,
                    context_encadreur,
                    "Un mémoire que vous encadrez vient d'être téléchargé 📖"
                )
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi des emails de notification: {str(e)}")
            # Ne pas bloquer le téléchargement en cas d'erreur d'email

    def envoyer_email_destinataire(self, email_destinataire, context, sujet):
        """Envoie un email individuel à un destinataire."""
        try:
            # Rendu du template HTML
            html_content = render_to_string(
                "emails/memoire_telecharge.html", 
                context
            )
            
            # Création et envoi de l'email
            email = EmailMessage(
                subject=sujet,
                body=html_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email_destinataire],
            )
            email.content_subtype = "html"
            email.send(fail_silently=False)
            
            logger.info(f"Email de notification envoyé à {email_destinataire} ({context['destinataire_type']}) pour le téléchargement du mémoire {context['memoire_titre']}")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de l'email à {email_destinataire}: {str(e)}")

    @extend_schema(responses={200: TelechargementListSerializer(many=True)})
    @action(detail=False, methods=["get"], url_path="mes-telechargements")
    def mes_telechargements(self, request):
        qs = Telechargement.objects.filter(utilisateur=request.user).select_related(
            "memoire"
        )
        serializer = TelechargementListSerializer(qs, many=True)
        return Response(serializer.data)

    @extend_schema(responses={200: TelechargementListSerializer(many=True)})
    @action(detail=False, methods=["get"], url_path="mes-telechargements")
    def mes_telechargements(self, request):
        qs = Telechargement.objects.filter(utilisateur=request.user).select_related(
            "memoire"
        )
        serializer = TelechargementListSerializer(qs, many=True)
        return Response(serializer.data)
    @extend_schema(responses={200: TelechargementListSerializer(many=True)})
    @action(detail=False, methods=["get"], url_path="mes-telechargements")
    def mes_telechargements(self, request):
        qs = Telechargement.objects.filter(utilisateur=request.user).select_related(
            "memoire"
        )
        serializer = TelechargementListSerializer(qs, many=True)
        return Response(serializer.data)


# --------------------------------------------------
# 2. Like (tout user connecté)
# --------------------------------------------------
class LikeOpenViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Liké / unliké un mémoire",
        request=LikeToggleSerializer,
    )  # ✅
    @action(detail=False, methods=["post"], url_path="toggle")
    def toggle(self, request):
        ser = LikeToggleSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        memoire = get_object_or_404(Memoire, pk=ser.validated_data["memoire_id"])
        like, created = Like.objects.get_or_create(
            utilisateur=request.user, memoire=memoire
        )
        if not created:
            like.delete()
            return Response(
                {"liked": False, "count": memoire.likes.count()},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"liked": True, "count": memoire.likes.count()},
            status=status.HTTP_201_CREATED,
        )


# --------------------------------------------------
# 3. Commentaires (tout user connecté)
# --------------------------------------------------
@extend_schema_view(
    list=extend_schema(
        summary="Commentaires publics",
        responses={200: CommentaireListSerializer(many=True)},
    ),
    create=extend_schema(
        summary="Publier un commentaire",
        request=CommentaireCreateSerializer,
        responses={201: CommentaireListSerializer},
    ),
)


class CommentaireOpenViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return CommentaireCreateSerializer
        return CommentaireListSerializer

    def get_queryset(self):
        return (
            Commentaire.objects.filter(modere=False)
            .select_related("utilisateur", "memoire")
            .order_by("-date")
        )

    def perform_create(self, serializer):
        commentaire = serializer.save(utilisateur=self.request.user, modere=False)
        
        # LOG: Création de commentaire (optionnel, basse sévérité)
        create_audit_log(
            action=AuditLog.ActionType.COMMENT_CREATE,
            severity=AuditLog.Severity.LOW,
            user=self.request.user,
            target=commentaire,
            target_type='Commentaire',
            target_repr=f"Commentaire de {self.request.user.email} sur mémoire ID:{commentaire.memoire.id if commentaire.memoire else 'N/A'}",
            new_data={
                'contenu': commentaire.contenu[:200],
                'memoire_id': str(commentaire.memoire.id) if commentaire.memoire else None,
                'modere': commentaire.modere,
            },
            description=f"Nouveau commentaire créé par {self.request.user.email}",
            request=self.request
        )
        
        return commentaire

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        print('[BACK] Serialisé :', serializer.data[:2])
        return Response(serializer.data)

    @extend_schema(summary="Modérer un commentaire (staff ou modérateur)")
    @action(detail=True, methods=["patch"], url_path="moderer")
    def moderer(self, request, *args, **kwargs):
        # Vérification des permissions
        if not IsAdminOrModerateur().has_permission(request, self):
            # LOG: Tentative échouée
            create_audit_log(
                action=AuditLog.ActionType.COMMENT_MODERATE,
                severity=AuditLog.Severity.HIGH,
                user=request.user,
                target_type='Commentaire',
                target_id=str(kwargs.get('pk')),
                target_repr=f"Tentative modération commentaire ID:{kwargs.get('pk')}",
                description=f"TENTATIVE ÉCHOUÉE de modération par {request.user.email} - Permissions insuffisantes",
                request=request
            )
            
            return Response(
                {"detail": "Réservé aux modérateurs"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        com = self.get_object()
        memoire = com.memoire
        
        # Sauvegarder l'état avant
        previous_state = {
            'modere': com.modere,
            'contenu': com.contenu[:200],
            'date': com.date.isoformat() if com.date else None,
        }
        
        # Toggle du statut de modération
        com.modere = not com.modere
        com.save()
        
        # LOG: Modération réussie
        create_audit_log(
            action=AuditLog.ActionType.COMMENT_MODERATE,
            severity=AuditLog.Severity.MEDIUM,
            user=request.user,
            university=memoire.universites.first() if memoire else None,
            target=com,
            target_type='Commentaire',
            target_repr=f"Commentaire ID:{com.id} sur '{memoire.titre[:50]}...'" if memoire else f"Commentaire ID:{com.id}",
            previous_data=previous_state,
            new_data={
                'modere': com.modere,
                'moderated_by': request.user.email,
                'moderated_at': str(com.date),
            },
            description=f"Modération {'activée' if com.modere else 'désactivée'} par {request.user.email}",
            request=request
        )
        
        return Response({
            "modere": com.modere, 
            "action": "modéré" if com.modere else "démodéré"
        })

    @extend_schema(summary="Supprimer un commentaire (avec traçabilité)")
    @action(detail=True, methods=["delete"], url_path="supprimer")
    def supprimer(self, request, *args, **kwargs):
        """
        Suppression d'un commentaire avec traçabilité complète.
        """
        # Vérification des permissions
        if not IsAdminOrModerateur().has_permission(request, self):
            # LOG: Tentative échouée (CRITICAL car tentative de suppression)
            create_audit_log(
                action=AuditLog.ActionType.COMMENT_DELETE,
                severity=AuditLog.Severity.CRITICAL,
                user=request.user,
                target_type='Commentaire',
                target_id=str(kwargs.get('pk')),
                target_repr=f"Tentative suppression commentaire ID:{kwargs.get('pk')}",
                description=f"TENTATIVE ÉCHOUÉE de suppression par {request.user.email} - Permissions insuffisantes",
                request=request
            )
            
            return Response(
                {"detail": "Réservé aux modérateurs"}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        com = self.get_object()
        memoire = com.memoire
        
        # Préparation des données complètes avant suppression
        deletion_data = {
            'commentaire': {
                'id': com.id,
                'contenu': com.contenu,
                'date': com.date.isoformat() if com.date else None,
                'modere': com.modere,
                'created_at': com.created_at.isoformat() if hasattr(com, 'created_at') and com.created_at else None,
            },
            'auteur': {
                'id': com.utilisateur.id,
                'email': com.utilisateur.email,
                'nom': f"{getattr(com.utilisateur, 'prenom', '')} {getattr(com.utilisateur, 'nom', '')}".strip() or str(com.utilisateur),
            },
            'memoire': {
                'id': memoire.id if memoire else None,
                'titre': memoire.titre if memoire else None,
                'universite': memoire.universites.first().nom if memoire and memoire.universites.first() else None,
                'universite_slug': memoire.universites.first().slug if memoire and memoire.universites.first() else None,
            } if memoire else None,
            'raison': request.data.get('raison', 'Non spécifiée'),
        }
        
        commentaire_id = com.id
        commentaire_resume = com.contenu[:100] if com.contenu else "Sans contenu"
        
        with transaction.atomic():
            # LOG avant suppression (CRITICAL car action destructive)
            create_audit_log(
                action=AuditLog.ActionType.COMMENT_DELETE,
                severity=AuditLog.Severity.CRITICAL,
                user=request.user,
                university=memoire.universites.first() if memoire else None,
                target=com,
                target_type='Commentaire',
                target_repr=f"Commentaire ID:{com.id} par {com.utilisateur.email}",
                previous_data=deletion_data,
                description=f"Suppression définitive du commentaire ID:{commentaire_id} par {request.user.email}. Raison: {deletion_data['raison']}",
                request=request
            )
            
            # Suppression effective
            com.delete()
        
        return Response(
            {
                "detail": "Commentaire supprimé avec succès",
                "id": commentaire_id,
                "resume": commentaire_resume,
                "supprime_par": request.user.email,
                "timestamp": deletion_data['commentaire']['date'],
            },
            status=status.HTTP_200_OK
        )

    def perform_destroy(self, instance):
        """
        Surcharge de la suppression standard (DELETE sur /commentaires/{id}/)
        avec traçabilité.
        """
        user = self.request.user
        memoire = instance.memoire
        
        # Vérification des permissions - Utiliser IsAdminOrModerateur comme les autres méthodes
        if not IsAdminOrModerateur().has_permission(self.request, self):
            # LOG tentative échouée
            create_audit_log(
                action=AuditLog.ActionType.COMMENT_DELETE,
                severity=AuditLog.Severity.CRITICAL,
                user=user,
                target_type='Commentaire',
                target_id=str(instance.id),
                target_repr=f"Tentative suppression directe commentaire ID:{instance.id}",
                description=f"TENTATIVE ÉCHOUÉE de suppression directe par {user.email}",
                request=self.request
            )
            # ← CORRECTION ICI : Utiliser PermissionDenied de DRF, pas PermissionError
            raise PermissionDenied("Réservé aux modérateurs")
        
        # Préparation des données
        deletion_data = {
            'id': instance.id,
            'contenu': instance.contenu,
            'date': instance.date.isoformat() if instance.date else None,
            'auteur_email': instance.utilisateur.email,
            'memoire_titre': memoire.titre if memoire else None,
            'method': 'perform_destroy (DELETE standard)',
        }
        
        # LOG avant suppression
        create_audit_log(
            action=AuditLog.ActionType.COMMENT_DELETE,
            severity=AuditLog.Severity.CRITICAL,
            user=user,
            university=memoire.universites.first() if memoire else None,
            target=instance,
            target_type='Commentaire',
            target_repr=f"Commentaire ID:{instance.id} par {instance.utilisateur.email}",
            previous_data=deletion_data,
            description=f"Suppression directe (DELETE) du commentaire par {user.email}",
            request=self.request
        )
        
        instance.delete()

from rest_framework import serializers

# serializers.py
from rest_framework import serializers

class CommentaireListSerializer(serializers.ModelSerializer):
    # ⭐ on override le champ pour forcer l’objet complet
    utilisateur = serializers.SerializerMethodField()

    class Meta:
        model = Commentaire
        fields = ['id', 'utilisateur', 'contenu', 'date', 'modere']

    def get_utilisateur(self, obj):
        user = obj.utilisateur
        return {
            'id': user.id,
            'nom': user.nom,
            'prenom': user.prenom,
            'photo_profil': str(user.photo_profil) if user.photo_profil else None,
        }
# --------------------------------------------------
# 4. Notation (tout user connecté)
# --------------------------------------------------
class NotationViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Noter un mémoire",
        request=NotationCreateSerializer,
    )
    def destroy(self, request, pk=None):
        notation = get_object_or_404(
            Notation, pk=pk
        )
        notation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    @action(detail=False, methods=["post"], url_path="noter")
    def noter(self, request, ser):
        memoire = get_object_or_404(Memoire, pk=ser.validated_data["memoire_id"])

        # Tentez de récupérer l'annotation existante
        notation = Notation.objects.filter(
            utilisateur=request.user, memoire=memoire
        ).first()

        if notation:
            # Si la notation existe, mettez à jour la note
            notation.note = ser.validated_data["note"]
            notation.save()
            return Response(
                {"detail": "Note mise à jour", "note": notation.note},
                status=status.HTTP_200_OK,
            )
        else:
            # Si la notation n'existe pas, créez-en une nouvelle
            notation = Notation.objects.create(
                utilisateur=request.user,
                memoire=memoire,
                note=ser.validated_data["note"],
            )
            return Response(
                {"detail": "Note enregistrée", "note": notation.note},
                status=status.HTTP_201_CREATED,
            )

    @extend_schema(
        summary="Liste des notes d’un mémoire",
        responses={200: NotationListSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="par-memoire/<int:memoire_id>")
    def par_memoire(self, request, memoire_id):
        memoire = get_object_or_404(Memoire, pk=memoire_id)
        notations = Notation.objects.filter(memoire=memoire).select_related("utilisateur")
        serializer = NotationListSerializer(notations, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Stats de notation d’un mémoire",
    )
    @action(detail=False, methods=["get"], url_path="stats/<int:memoire_id>")
    def stats(self, request, *args, **kwargs):
        memoire = get_object_or_404(Memoire, pk=kwargs["memoire_id"])
        stats = Notation.objects.filter(memoire=memoire).aggregate(
            avg_note=Avg("note"), count=Count("id")
        )
        return Response(
            {
                "memoire": memoire.titre,
                "note_moyenne": round(stats["avg_note"] or 0, 2),
                "total_notes": stats["count"],
            }
        )

    def list(self, request):
        notations = (
            Notation.objects.all()
        )  # Vous pourriez souhaiter filtrer par utilisateur ou autres critères
        serializer = NotationListSerializer(
            notations, many=True
        )  # Assurez-vous de créer ce serializer
        return Response(serializer.data)

    def create(self, request):
        ser = NotationCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        print(
            "Données validées :", ser.validated_data
        )  # Cela affichera les données validées
        return self.noter(request, ser)


# --------------------------------------------------
# 5. Signalement (admin uniquement)
# --------------------------------------------------
class SignalementModerationViewSet(viewsets.ViewSet):
    permission_classes = [
        IsAuthenticated
    ]  # ou IsAdminOfUniversite si tu veux restreindre

    @extend_schema(
        summary="Liste des signalements non traités",
        responses={200: SignalementListSerializer(many=True)},
    )
    @action(detail=False, methods=["get"], url_path="signalements-en-attente")
    def signalements_en_attente(self, request, *args, **kwargs):
        qs = Signalement.objects.filter(
            memoire__universites__slug=kwargs["univ_slug"], traite=False
        ).select_related("utilisateur", "memoire")
        serializer = SignalementListSerializer(qs, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="Marquer un signalement comme traité",
        responses={200: {"detail": "Signalement marqué comme traité"}},
    )
    @action(detail=True, methods=["patch"], url_path="marquer-traite/<int:pk>")
    def marquer_traite(self, request, *args, **kwargs):
        signalement = get_object_or_404(
            Signalement, pk=kwargs["pk"], memoire__universites__slug=kwargs["univ_slug"]
        )
        signalement.traite = True
        signalement.save()
        return Response({"detail": "Signalement marqué comme traité."})


# --------------------------------------------------
# 1. Téléchargements
# --------------------------------------------------
class UniversiteTelechargementListView(generics.ListAPIView):
    """
    Liste des téléchargements des mémoires d’une université.
    """

    serializer_class = TelechargementListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        univ_slug = self.kwargs["univ_slug"]
        return (
            Telechargement.objects.filter(memoire__universites__slug=univ_slug)
            .select_related("utilisateur", "memoire")
            .order_by("-date")
        )


# --------------------------------------------------
# 2. Likes
# --------------------------------------------------
class UniversiteLikeListView(generics.ListAPIView):
    serializer_class = LikeListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        univ_slug = self.kwargs["univ_slug"]
        return (
            Like.objects.filter(memoire__universites__slug=univ_slug)
            .select_related("utilisateur", "memoire")
            .order_by("-date")
        )


# --------------------------------------------------
# 3. Commentaires
# --------------------------------------------------
class UniversiteCommentaireListView(generics.ListAPIView):
    serializer_class = CommentaireListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        univ_slug = self.kwargs["univ_slug"]
        return (
            Commentaire.objects.filter(memoire__universites__slug=univ_slug, modere=False)
            .select_related("utilisateur")
            .order_by("-date")
        )


# --------------------------------------------------
# 4. Notations
# --------------------------------------------------
class UniversiteNotationListView(generics.ListAPIView):
    serializer_class = NotationListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        univ_slug = self.kwargs["univ_slug"]
        return (
            Notation.objects.filter(memoire__universites__slug=univ_slug)
            .select_related("utilisateur", "memoire")
            .order_by("-created_at")
        )


# --------------------------------------------------
# 5. Signalements (admin uniquement)
# --------------------------------------------------
class UniversiteSignalementListView(generics.ListAPIView):
    serializer_class = SignalementListSerializer
    permission_classes = [permissions.IsAuthenticated]  # on peut restreindre plus tard

    def get_queryset(self):
        univ_slug = self.kwargs["univ_slug"]
        return (
            Signalement.objects.filter(memoire__universites__slug=univ_slug)
            .select_related("utilisateur", "memoire")
            .order_by("-created_at")
        )


# --------------------------------------------------
# 6. Stats globales interactions (tout public)
# --------------------------------------------------
class UniversiteInteractionsStatsView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(summary="Stats interactions d’une université")
    def get(self, request, *args, **kwargs):
        univ_slug = kwargs["univ_slug"]
        memoires_qs = Memoire.objects.filter(universites__slug=univ_slug)

        return Response(
            {
                "universite": univ_slug,
                "total_memoires":Memoire.objects.filter(
                    universites__slug=univ_slug
                ).count(),
                "total_telechargements": Telechargement.objects.filter(
                    memoire__universites__slug=univ_slug
                ).count(),
                "total_likes": Like.objects.filter(
                    memoire__universites__slug=univ_slug
                ).count(),
                "total_commentaires": Commentaire.objects.filter(
                    memoire__universites__slug=univ_slug, modere=False
                ).count(),
                "total_notations": Notation.objects.filter(
                    memoire__universites__slug=univ_slug
                ).count(),
                "note_moyenne": round(
                    Notation.objects.filter(
                        memoire__universites__slug=univ_slug
                    ).aggregate(avg=Avg("note"))["avg"]
                    or 0,
                    2,
                ),
                "total_signalements": Signalement.objects.filter(
                    memoire__universites__slug=univ_slug
                ).count(),
                "top_memoires_telecharges": list(
                    memoires_qs.annotate(dl=Count("telechargements"))
                    .order_by("-dl")
                    .values("id", "titre", "dl")[:5]
                ),
                "top_memoires_notes": list(
                    memoires_qs.annotate(avg_note=Avg("notations__note"))
                    .order_by("-avg_note")
                    .values("id", "titre", "avg_note")[:5]
                ),
            }
        )
