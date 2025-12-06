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


from memoires.models import Memoire, Notation, Signalement
from interactions.permissions import IsAuthenticated, IsAdminOrModerateur


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
        return Response(
            {
                "detail": "Téléchargement enregistré",
                "pdf_url": request.build_absolute_uri(memoire.fichier_pdf.url),
            },
            status=status.HTTP_201_CREATED,
        )

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
        # ⭐ choisit le serializer adéquat
        if self.action == "create":
            return CommentaireCreateSerializer
        return CommentaireListSerializer

    def get_queryset(self):
        return (
            Commentaire.objects.filter(modere=False)
            .select_related("utilisateur")
            .order_by("-date")
        )

    def perform_create(self, serializer):
        # ⭐ on force l’utilisateur connecté + modere=False
        serializer.save(utilisateur=self.request.user, modere=False)

    @extend_schema(summary="Modérer un commentaire (staff ou modérateur)")
    @action(detail=True, methods=["patch"], url_path="moderer")
    def moderer(self, request, *args, **kwargs):
        if not IsAdminOrModerateur().has_permission(request, self):
            return Response(
                {"detail": "Réservé aux modérateurs"}, status=status.HTTP_403_FORBIDDEN
            )
        com = self.get_object()
        com.modere = not com.modere
        com.save()
        return Response({"modere": com.modere})


# --------------------------------------------------
# 4. Notation (tout user connecté)
# --------------------------------------------------
class NotationViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Noter un mémoire",
        request=NotationCreateSerializer,
    )
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
