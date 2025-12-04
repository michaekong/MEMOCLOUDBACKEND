# memoires/views.py
import csv
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.db.models import Count, Avg
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from rest_framework import viewsets, permissions, filters, generics, status
from rest_framework.response import Response
from rest_framework.generics import CreateAPIView
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings

from .models import Memoire, Encadrement, Signalement
from .serializers import (
    MemoireListSerializer,
    MemoireCreateSerializer,
    EncadrementSerializer,
    MemoireBulkCSVSerializer,
    SignalementSerializer,
    HistoricalMemoireSerializer,
    BatchUploadSerializer,
)
from universites.models import Universite, Domaine

User = get_user_model()


# ------------------------------------------------------------------
# 1. CRUD mémoires & encadrements
# ------------------------------------------------------------------
class MemoireViewSet(viewsets.ModelViewSet):
    queryset = Memoire.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['titre', 'resume', 'auteur__nom', 'auteur__prenom']
    ordering_fields = ['annee', 'created_at']

    def get_serializer_class(self):
        
        if self.action in ['create', 'update', 'partial_update']:
            return MemoireCreateSerializer
        return MemoireListSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.IsAuthenticated()]
        if self.action in ['list', 'retrieve', 'search', 'preview']:
            return [permissions.AllowAny()]
     
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        univ_id = self.request.query_params.get('universite')
        domaine_id = self.request.query_params.get('domaine')
        annee = self.request.query_params.get('annee')
        if univ_id:
            qs = qs.filter(universites__id=univ_id)
        if domaine_id:
            qs = qs.filter(domaines__id=domaine_id)
        if annee:
            qs = qs.filter(annee=annee)
        return qs.distinct()

    def perform_create(self, serializer):
        serializer.save(auteur=self.request.user)

    def perform_destroy(self, instance):
        if instance.encadrements.exists() or instance.notations.exists() or instance.telechargements.exists():
            raise ValidationError("Impossible de supprimer : mémoire lié à des données.")
        super().perform_destroy(instance)


class EncadrementViewSet(viewsets.ModelViewSet):
    queryset = Encadrement.objects.all()
    serializer_class = EncadrementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        memoire_id = self.request.query_params.get('memoire')
        if memoire_id:
            qs = qs.filter(memoire_id=memoire_id)
        return qs

    def perform_create(self, serializer):
        memoire = serializer.validated_data['memoire']
        if not memoire.universites.filter(
            roles__utilisateur=self.request.user,
            roles__role__in=['admin', 'superadmin', 'bigboss']
        ).exists():
            raise ValidationError("Vous n’êtes pas administrateur d’une université liée à ce mémoire.")
        serializer.save()


# ------------------------------------------------------------------
# 2. Batch CSV
# ------------------------------------------------------------------
class MemoireBulkCSVView(CreateAPIView):
    """
    POST /api/memoires/batch-csv/
    Form-data : csv_file
    """
    serializer_class = MemoireBulkCSVSerializer
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_201_CREATED)


# ------------------------------------------------------------------
# 3. Recherche & filtres
# ------------------------------------------------------------------
class MemoireSearchView(generics.ListAPIView):
    serializer_class = MemoireListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        q = self.request.GET.get('q', '')
        if len(q) < 3:
            return Memoire.objects.none()
        search_vector = SearchVector('titre', 'resume')
        search_query = SearchQuery(q)
        return (
            Memoire.objects.annotate(
                search=search_vector,
                rank=SearchRank(search_vector, search_query)
            )
            .filter(search=search_query)
            .order_by('-rank')
        )


class MemoireFilterView(generics.ListAPIView):
    serializer_class = MemoireListSerializer

    def get_queryset(self):
        qs = Memoire.objects.all()
        annee_min = self.request.GET.get('annee_min')
        annee_max = self.request.GET.get('annee_max')
        note_min = self.request.GET.get('note_min')
        dl_min = self.request.GET.get('dl_min')

        if annee_min:
            qs = qs.filter(annee__gte=annee_min)
        if annee_max:
            qs = qs.filter(annee__lte=annee_max)
        if note_min:
            qs = qs.filter(notations__note__gte=note_min).distinct()
        if dl_min:
            qs = qs.annotate(dl_count=Count('telechargements')).filter(dl_count__gte=dl_min)
        return qs


# ------------------------------------------------------------------
# 4. Top mémoires
# ------------------------------------------------------------------
class TopDownloadedView(generics.ListAPIView):
    serializer_class = MemoireListSerializer

    def get_queryset(self):
        return Memoire.objects.annotate(dl=Count('telechargements')).order_by('-dl')[:10]


class TopRatedView(generics.ListAPIView):
    serializer_class = MemoireListSerializer

    def get_queryset(self):
        return Memoire.objects.annotate(avg=Avg('notations__note')).order_by('-avg')[:10]


# ------------------------------------------------------------------
# 5. Dashboards
# ------------------------------------------------------------------
class AuteurDashboardView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        memoires = user.memoires.all()
        return Response({
            "total_memoires": memoires.count(),
            "total_telechargements": sum(m.nb_telechargements() for m in memoires),
            "note_moyenne": round(
                sum(m.note_moyenne() for m in memoires) / max(memoires.count(), 1), 2
            ),
            "annees": list(memoires.values_list('annee', flat=True).distinct()),
        })


class UniversiteDashboardView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        univ = get_object_or_404(Universite, pk=pk)
        if not univ.roles.filter(utilisateur=request.user, role__in=['admin', 'superadmin', 'bigboss']).exists():
            return Response({"detail": "Non autorisé."}, status=status.HTTP_403_FORBIDDEN)
        memoires = Memoire.objects.filter(universites=univ)
        return Response({
            "nom": univ.nom,
            "total_memoires": memoires.count(),
            "total_telechargements": sum(m.nb_telechargements() for m in memoires),
            "top_domaines": list(
                memoires.values('domaines__nom')
                .annotate(nb=Count('id'))
                .order_by('-nb')[:5]
            ),
        })


# ------------------------------------------------------------------
# 6. Export CSV
# ------------------------------------------------------------------
class ExportMemoiresCSVView(generics.GenericAPIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="memoires.csv"'
        writer = csv.writer(response)
        writer.writerow(['Titre', 'Auteur', 'Année', 'Note moy.', 'Téléchargements'])
        for m in Memoire.objects.all():
            writer.writerow([m.titre, m.auteur.get_full_name(), m.annee, m.note_moyenne(), m.nb_telechargements()])
        return response


# ------------------------------------------------------------------
# 7. Signalement
# ------------------------------------------------------------------
class SignalementView(generics.CreateAPIView):
    queryset = Signalement.objects.all()
    serializer_class = SignalementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(utilisateur=self.request.user)


# ------------------------------------------------------------------
# 8. Historique
# ------------------------------------------------------------------
class MemoireHistoryView(generics.ListAPIView):
    serializer_class = HistoricalMemoireSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return Memoire.objects.get(pk=self.kwargs['pk']).history.all()


# ------------------------------------------------------------------
# 9. Preview PDF
# ------------------------------------------------------------------
class MemoirePreviewView(generics.RetrieveAPIView):
    queryset = Memoire.objects.all()
    serializer_class = MemoireListSerializer
    permission_classes = [permissions.AllowAny]

    def retrieve(self, request, *args, **kwargs):
        memoire = self.get_object()
        return Response({
            "titre": memoire.titre,
            "pdf_url": request.build_absolute_uri(memoire.fichier_pdf.url),
            "pages": None,  # ou extraction via PyPDF2 si besoin
        })


# ------------------------------------------------------------------
# 10. Batch ZIP
# ------------------------------------------------------------------
class BatchUploadView(generics.CreateAPIView):
    serializer_class = BatchUploadSerializer
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        zip_file = request.FILES['zip']
        # Ici : logique d’extraction, création des mémoires, etc.
        # Retour fictif pour l’exemple
        return Response({"created": 42}, status=status.HTTP_201_CREATED)


# ------------------------------------------------------------------
# 11. Stats globales
# ------------------------------------------------------------------
class GlobalStatsView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from interactions.models import Telechargement, NotationCommentaire
        return Response({
            "total_memoires": Memoire.objects.count(),
            "total_telechargements": Telechargement.objects.count(),
            "total_commentaires": NotationCommentaire.objects.exclude(commentaire='').count(),
            "note_moyenne_globale": round(
                Memoire.objects.aggregate(avg=Avg('notations__note'))['avg'] or 0, 2
            ),
        })
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Notation
from .serializers import NotationSerializer

class NotationViewSet(viewsets.ModelViewSet):
    queryset = Notation.objects.all()
    serializer_class = NotationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Utilisateur standard : ne voit que ses notes
        if self.request.user.is_staff:
            return self.queryset
        return self.queryset.filter(utilisateur=self.request.user)

    def create(self, request, *args, **kwargs):
        memoire_id = request.data.get('memoire')
        note = request.data.get('note')

        if not memoire_id or note is None:
            return Response({'detail': 'mémoire et note requis'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            memoire = Memoire.objects.get(pk=memoire_id)
        except Memoire.DoesNotExist:
            return Response({'detail': 'Mémoire introuvable'}, status=status.HTTP_404_NOT_FOUND)

        if not (1 <= int(note) <= 5):
            return Response({'detail': 'La note doit être entre 1 et 5'}, status=status.HTTP_400_BAD_REQUEST)

        notation, created = Notation.objects.get_or_create(
            utilisateur=request.user,
            memoire=memoire,
            defaults={'note': note}
        )
        if not created:
            # Mise à jour si déjà noté
            notation.note = note
            notation.save()

        serializer = self.get_serializer(notation)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='par-memoire/(?P<memoire_id>\d+)')
    def par_memoire(self, request, memoire_id=None):
        """Récupérer toutes les notes d’un mémoire (auteur ou staff)"""
        try:
            memoire = Memoire.objects.get(pk=memoire_id)
        except Memoire.DoesNotExist:
            return Response({'detail': 'Mémoire introuvable'}, status=status.HTTP_404_NOT_FOUND)

        if request.user != memoire.auteur and not request.user.is_staff:
            return Response({'detail': 'Non autorisé'}, status=status.HTTP_403_FORBIDDEN)

        qs = self.queryset.filter(memoire=memoire).select_related('utilisateur')
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)        

# memoires/views.py
class MemoireCreateInUniversiteView(generics.CreateAPIView):
    serializer_class = MemoireCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        univ = get_object_or_404(Universite, slug=self.kwargs['univ_slug'])
        memoire = serializer.save(auteur=self.request.user)
        memoire.universites.add(univ)   # rattachement immédiat        