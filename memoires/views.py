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
        
        # Récupérer les universités mères et les ajouter au mémoire
        universites_meres = univ.get_universites_meres()
        for affiliation in universites_meres:
            memoire.universites.add(affiliation.universite_mere)
        
        # Les emails sont déjà envoyés dans le serializer.create()
        # grâce à l'appel de envoyer_email_creation(memoire)


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
# memoires/views.py
from django.db.models import Count, Avg, Q, Sum
from rest_framework import generics, permissions
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from universites.models import Universite
from users.models import CustomUser
from memoires.models import Memoire

class UserUniversiteStatsView(generics.GenericAPIView):
    """
    GET /api/universites/<univ_slug>/users-stats/
    
    Retourne les statistiques complètes à 360° pour chaque utilisateur 
    de l'université concerné par au moins un mémoire (auteur ou encadreur).
    """
    permission_classes = [permissions.AllowAny]  # ou IsAdminOfUniversite selon besoin

    def get(self, request, univ_slug):
        universite = get_object_or_404(Universite, slug=univ_slug)
        
        # Récupérer tous les mémoires de l'université
        memoires_univ = Memoire.objects.filter(universites=universite)
        
        # Récupérer tous les utilisateurs concernés (auteurs + encadreurs)
        users_auteurs = memoires_univ.values_list('auteur_id', flat=True).distinct()
        users_encadreurs = memoires_univ.values('encadrements__encadreur_id').distinct()
        users_encadreurs_ids = [u['encadrements__encadreur_id'] for u in users_encadreurs if u['encadrements__encadreur_id']]
        
        all_user_ids = set(users_auteurs) | set(users_encadreurs_ids)
        
        users_stats = []
        
        for user_id in all_user_ids:
            user = CustomUser.objects.get(id=user_id)
            
            # Mémoires dont l'user est auteur dans cette université
            memoires_auteur = memoires_univ.filter(auteur=user)
            
            # Mémoires dont l'user est encadreur dans cette université
            memoires_encadres = memoires_univ.filter(encadrements__encadreur=user)
            
            # Tous les mémoires liés à l'user
            memoires_lies = (memoires_auteur | memoires_encadres).distinct()
            
            # --- STATISTIQUES GLOBALES ---
            total_memoires_auteur = memoires_auteur.count()
            total_memoires_encadres = memoires_encadres.count()
            total_memoires_lies = memoires_lies.count()
            
            # --- TÉLÉCHARGEMENTS ---
            total_telechargements = sum(m.nb_telechargements() for m in memoires_lies)
            
            # --- LIKES ---
            total_likes = sum(m.likes.count() for m in memoires_lies)
            
            # --- COMMENTAIRES ---
            total_commentaires = sum(m.commentaires.filter(modere=False).count() for m in memoires_lies)
            
            # --- NOTATIONS ---
            notes = []
            for m in memoires_lies:
                note_moy = m.note_moyenne()
                if note_moy > 0:
                    notes.append(note_moy)
            
            note_moyenne_globale = round(sum(notes) / len(notes), 2) if notes else 0
            total_notations = sum(m.notations.count() for m in memoires_lies)
            
            # --- DÉTAILS PAR MÉMOIRE ---
            memoires_details = []
            for memoire in memoires_lies:
                role = []
                if memoire in memoires_auteur:
                    role.append("auteur")
                if memoire in memoires_encadres:
                    role.append("encadreur")
                
                memoires_details.append({
                    "id": memoire.id,
                    "titre": memoire.titre,
                    "pdf_url": memoire.fichier_pdf.url if memoire.fichier_pdf else None,
                    "annee": memoire.annee,
                    "role": ", ".join(role),
                    "nb_telechargements": memoire.nb_telechargements(),
                    "nb_likes": memoire.likes.count(),
                    "nb_commentaires": memoire.commentaires.filter(modere=False).count(),
                    "note_moyenne": memoire.note_moyenne(),
                    "nb_notations": memoire.notations.count(),
                })
            
            # --- STATISTIQUES PAR DOMAINE ---
            domaines_stats = {}
            for memoire in memoires_lies:
                for domaine in memoire.domaines.all():
                    if domaine.nom not in domaines_stats:
                        domaines_stats[domaine.nom] = {
                            "nb_memoires": 0,
                            "telechargements": 0,
                            "likes": 0,
                            "commentaires": 0,
                        }
                    domaines_stats[domaine.nom]["nb_memoires"] += 1
                    domaines_stats[domaine.nom]["telechargements"] += memoire.nb_telechargements()
                    domaines_stats[domaine.nom]["likes"] += memoire.likes.count()
                    domaines_stats[domaine.nom]["commentaires"] += memoire.commentaires.filter(modere=False).count()
            
            # --- STATISTIQUES PAR ANNÉE ---
            annees_stats = {}
            for memoire in memoires_lies:
                annee = memoire.annee
                if annee not in annees_stats:
                    annees_stats[annee] = {
                        "nb_memoires": 0,
                        "telechargements": 0,
                        "likes": 0,
                    }
                annees_stats[annee]["nb_memoires"] += 1
                annees_stats[annee]["telechargements"] += memoire.nb_telechargements()
                annees_stats[annee]["likes"] += memoire.likes.count()
            
            # --- TOP MÉMOIRES (par téléchargements) ---
            top_memoires = sorted(
                memoires_details, 
                key=lambda x: x["nb_telechargements"], 
                reverse=True
            )[:5]
            
            # --- ASSEMBLAGE FINAL ---
            users_stats.append({
                "utilisateur": {
                    "id": user.id,
                    "nom": user.nom,
                    "prenom": user.prenom,
                    "email": user.email,
                    "type": user.type,
                    "photo_profil": request.build_absolute_uri(user.photo_profil.url) if user.photo_profil else None,
                    "linkedin": user.realisation_linkedin,
                },
                "statistiques_globales": {
                    "total_memoires_auteur": total_memoires_auteur,
                    "total_memoires_encadres": total_memoires_encadres,
                    "total_memoires_lies": total_memoires_lies,
                    "total_telechargements": total_telechargements,
                    "total_likes": total_likes,
                    "total_commentaires": total_commentaires,
                    "total_notations": total_notations,
                    "note_moyenne_globale": note_moyenne_globale,
                },
                "memoires_details": memoires_details,
                "top_memoires": top_memoires,
                "statistiques_par_domaine": [
                    {"domaine": k, **v} for k, v in domaines_stats.items()
                ],
                "statistiques_par_annee": [
                    {"annee": k, **v} for k, v in sorted(annees_stats.items(), reverse=True)
                ],
            })
        
        # Tri des utilisateurs par nombre total de téléchargements (décroissant)
        users_stats.sort(
            key=lambda x: x["statistiques_globales"]["total_telechargements"], 
            reverse=True
        )
        
        return Response({
            "universite": {
                "slug": universite.slug,
                "nom": universite.nom,
            },
            "total_utilisateurs": len(users_stats),
            "utilisateurs_stats": users_stats,
        })        
