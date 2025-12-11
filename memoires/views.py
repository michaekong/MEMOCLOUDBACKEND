from django.shortcuts import get_object_or_404
from django.db.models import Avg, Count
from rest_framework import viewsets, permissions, status, filters, generics
from rest_framework.decorators import action

from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view
from memoires.models import Memoire, Encadrement
from memoires.serializers import (
    MemoireUniversiteListSerializer,
    MemoireUniversiteCreateSerializer,
    EncadrementAddSerializer,
    MemoireUniversiteStatsSerializer,
)
from universites.models import Universite
from universites.permissions import (
    IsMemberOfUniversite,
    IsAdminOfUniversite,
    IsAuthorOrAdminOfUniversite,
)
from universites.permissions import IsAdminOfUniversite
from django.contrib.auth import get_user_model
from django.db import transaction
User = get_user_model()
from rest_framework import generics, permissions, pagination
from interactions.models import Commentaire
from memoires.serializers import CommentaireSerializer
class CommentaireListView(generics.ListAPIView):
    """
    GET /api/universites/<univ_slug>/memoires/<memoire_id>/commentaires/
    Renvoie la liste des commentaires d’un mémoire (non modérés).
    """
    serializer_class = CommentaireSerializer
    permission_classes = [permissions.AllowAny]   # lecture publique
    pagination_class = pagination.PageNumberPagination   # optionnel

    def get_queryset(self):
        memoire_id = self.kwargs["memoire_id"]
        # on exclut les commentaires masqués (modération)
        return Commentaire.objects.filter(
            memoire_id=memoire_id, modere=False
        ).select_related("utilisateur").order_by("-date")
@extend_schema_view(
    list=extend_schema(summary="Liste des mémoires de l’université"),
    retrieve=extend_schema(summary="Détail d’un mémoire"),
    create=extend_schema(summary="Déposer un mémoire"),
    update=extend_schema(summary="Modifier un mémoire"),
    partial_update=extend_schema(summary="Mise à jour partielle"),
    destroy=extend_schema(summary="Supprimer un mémoire"),
    stats=extend_schema(summary="Statistiques mémoires université"),
)
class UniversiteMemoireViewSet(viewsets.ModelViewSet):
    """
    CRUD complet **filtré par université (slug)**.
    """

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["titre", "resume", "auteur__nom", "auteur__prenom"]
    ordering_fields = ["annee", "created_at"]

    def get_universite(self):
        return get_object_or_404(Universite, slug=self.kwargs["univ_slug"])

    def get_queryset(self):
        qs = Memoire.objects.filter(universites=self.get_universite()).distinct()
        annee = self.request.query_params.get("annee")
        domaine = self.request.query_params.get("domaine")
        if annee:
            qs = qs.filter(annee=annee)
        if domaine:
            qs = qs.filter(domaines__slug=domaine)
        return qs

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return MemoireUniversiteCreateSerializer
        return MemoireUniversiteListSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.AllowAny()]
        if self.action == "create":
            return [IsMemberOfUniversite()]
        return [IsAuthorOrAdminOfUniversite()]

    def perform_create(self, serializer):
        permission_classes = [IsAdminOfUniversite] 
        univ = self.get_universite()
        memoire = serializer.save()
        memoire.universites.add(univ)

    @extend_schema(
        summary="Statistiques mémoires de l’université",
        responses={200: MemoireUniversiteStatsSerializer},
    )
    @action(detail=False, methods=["get"], url_path="stats")
    def stats(self, request, **kwargs):
            
        univ = self.get_universite()
        qs = self.get_queryset()
        
        # Calcul des statistiques
        total_memoires = qs.count()
        total_telechargements = sum(m.nb_telechargements() for m in qs)
        note_moyenne = round(qs.aggregate(avg=Avg("notations__note"))["avg"] or 0, 2)
        
        # Total de likes et de commentaires
        total_likes = sum(m.likes.count() for m in qs)
        total_commentaires = sum(m.commentaires.count() for m in qs)

        return Response(
            MemoireUniversiteStatsSerializer(
                {
                    "universite": univ.slug,
                    "total_memoires": total_memoires,
                    "total_telechargements": total_telechargements,
                    "note_moyenne": note_moyenne,
                    "total_likes": total_likes,  # Ajout du total des likes
                    "total_commentaires": total_commentaires,  # Ajout du total des commentaires
                    "top_domaines": list(
                        qs.values("domaines__nom")
                        .annotate(nb=Count("id"))
                        .order_by("-nb")[:5]
                    ),
                }
            ).data
        )
    @action(detail=True, methods=['delete'], url_path='suppression-totale')
    def suppression_totale(self, request, *args, **kwargs):
        permission_classes = [IsAdminOfUniversite] 
        """
        Suppression complète d'un mémoire ET de toutes ses relations.
        """
        memoire = self.get_object()

        with transaction.atomic():
            # 1. Log avant suppression
            print(f"[ADMIN] Suppression totale du mémoire {memoire.id} – {memoire.titre}")

            # 2. Suppression / détachement des relations
            memoire.encadrements.all().delete()
            memoire.notations.all().delete()
            memoire.telechargements.all().delete()
            memoire.likes.all().delete()
            memoire.commentaires.all().delete()
            memoire.signalements.all().delete()

            # 3. Suppression des fichiers physiques (facultatif)
            if memoire.fichier_pdf:
                memoire.fichier_pdf.delete(save=False)
            if memoire.images:
                memoire.images.delete(save=False)

            # 4. Suppression finale
            memoire.delete()

        return Response(status=204)

class MemoireAnneesView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        annees = (
            Memoire.objects.filter(universites__slug=kwargs["univ_slug"])
            .values_list("annee", flat=True)
            .distinct()
            .order_by("-annee")
        )
        return Response({"annees": annees}) 


class MemoireEncadrementView(generics.GenericAPIView):
    """
    POST / DELETE  /api/universites/<slug>/memoires/<id>/encadrer/
    """

    permission_classes = [IsAdminOfUniversite]

    @extend_schema(
        summary="Ajouter un encadreur à un mémoire",
        request=EncadrementAddSerializer,
        responses={201: {"detail": "Encadreur ajouté."}},
    )
    def post(self, request, univ_slug, pk):
        ser = EncadrementAddSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        univ = get_object_or_404(Universite, slug=univ_slug)
        memoire = get_object_or_404(Memoire, pk=pk, universites=univ)
        encadreur = get_object_or_404(User, pk=ser.validated_data["encadreur_id"])

        enc, created = Encadrement.objects.get_or_create(
            memoire=memoire, encadreur=encadreur
        )
        if not created:
            return Response({"detail": "Déjà encadreur."}, status=status.HTTP_200_OK)
        return Response({"detail": "Encadreur ajouté."}, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Retirer un encadreur",
        request=EncadrementAddSerializer,
        responses={204: None},
    )
    def delete(self, request, univ_slug, pk):
        ser = EncadrementAddSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        univ = get_object_or_404(Universite, slug=univ_slug)
        memoire = get_object_or_404(Memoire, pk=pk, universites=univ)
        Encadrement.objects.filter(
            memoire=memoire,
            encadreur_id=ser.validated_data["encadreur_id"],
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# memoires/views.py
import fitz
from django.core.files.base import ContentFile
import os
from django.conf import settings


class MemoirePreviewImageView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        memoire = get_object_or_404(
            Memoire, pk=kwargs["pk"], universites__slug=kwargs["univ_slug"]
        )
        if not memoire.fichier_pdf:
            return Response({"detail": "Pas de PDF"}, status=404)

        # Génération 1ère page → PNG
        doc = fitz.open(memoire.fichier_pdf.path)
        page = doc.load_page(0)
        pix = page.get_pixmap()
        img_name = f"preview_{memoire.id}.png"
        img_path = os.path.join(settings.MEDIA_ROOT, "memoires/previews", img_name)
        os.makedirs(os.path.dirname(img_path), exist_ok=True)
        pix.save(img_path)
        doc.close()

        url = request.build_absolute_uri(
            settings.MEDIA_URL + "memoires/previews/" + img_name
        )
        return Response({"preview_url": url})


# memoires/views.py
class AuteurDashboardView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        print("Slug reçu :", kwargs.get("univ_slug"))
        univ = get_object_or_404(Universite, slug=kwargs["univ_slug"])
        print("Université trouvée :", univ)

        user = request.user
        print("User connecté :", user)

        memoires = user.memoires.filter(universites=univ)
        print("Memoires count :", memoires.count())

        if not memoires.exists():
            print("Aucun mémoire → on renvoie 404")
            # dashboard vide mais valide
            return Response(
                {
                    "total_memoires": 0,
                    "total_telechargements": 0,
                    "note_moyenne": 0,
                    "classement": [],
                }
            )

        return Response(
            {
                "total_memoires": memoires.count(),
                "total_telechargements": sum(m.nb_telechargements() for m in memoires),
                "note_moyenne": round(
                    sum(m.note_moyenne() for m in memoires) / max(memoires.count(), 1), 2
                ),
                "classement": list(
                    memoires.annotate(dl=Count("telechargements"))
                    .order_by("-dl")
                    .values("id", "titre", "dl")[:5]
                ),
            }
        )
