# universites/views.py
import csv
import unicodedata
from django.core.exceptions import ValidationError
from django.contrib.postgres.search import TrigramSimilarity
from django.utils.text import slugify
from rest_framework import viewsets, permissions, filters, generics, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Universite, Domaine, RoleUniversite
from .serializers import (
    UniversiteSerializer,
    DomaineSerializer,
    RoleUniversiteSerializer,
)


# -------------------- Université (CRUD) --------------------
class UniversiteViewSet(viewsets.ModelViewSet):
    queryset = Universite.objects.all()
    serializer_class = UniversiteSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['nom', 'acronyme']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]


# -------------------- Rôle par université --------------------
class RoleUniversiteViewSet(viewsets.ModelViewSet):
    queryset = RoleUniversite.objects.all()
    serializer_class = RoleUniversiteSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['utilisateur__email', 'universite__nom']

    def get_queryset(self):
        qs = super().get_queryset()
        univ_id = self.request.query_params.get('universite')
        if univ_id:
            qs = qs.filter(universite_id=univ_id)
        return qs

    def perform_create(self, serializer):
        serializer.save()


# ------------------------------------------------------------------
#  EXTENSIONS « réalisables maintenant » (sans attendre mémoires)
# ------------------------------------------------------------------

# --------- 1. Stats simples d’une université ---------
class UniversiteStatsView(generics.GenericAPIView):
    """
    GET /api/universites/<id>/stats/
    Retour : nb membres par rôle, nb domaines, date création
    """
    queryset = Universite.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        univ = self.get_object()
        roles = (
            RoleUniversite.objects.filter(universite=univ)
            .values('role')
            .annotate(count=RoleUniversite.objects.count())
        )
        return Response(
            {
                "universite": univ.nom,
                "acronyme": univ.acronyme,
                "created_at": univ.created_at,
                "total_membres": RoleUniversite.objects.filter(universite=univ).count(),
                "membres_par_role": {r['role']: r['count'] for r in roles},
                "total_domaines": univ.domaines.count(),
            }
        )


# --------- 2. Upload / suppression logo ---------
class LogoUploadView(generics.GenericAPIView):
    """
    POST /api/universites/<id>/upload-logo/
    Form-data : logo
    """
    queryset = Universite.objects.all()
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, *args, **kwargs):
        univ = self.get_object()
        file = request.FILES.get('logo')
        if not file:
            return Response({"logo": "Fichier manquant."}, status=status.HTTP_400_BAD_REQUEST)
        if univ.logo:
            univ.logo.delete(save=False)
        univ.logo = file
        univ.save()
        return Response(
            {"detail": "Logo mis à jour.", "logo": request.build_absolute_uri(univ.logo.url)},
            status=status.HTTP_200_OK,
        )


class LogoDeleteView(generics.GenericAPIView):
    """
    DELETE /api/universites/<id>/delete-logo/
    """
    queryset = Universite.objects.all()
    permission_classes = [permissions.IsAdminUser]

    def delete(self, request, *args, **kwargs):
        univ = self.get_object()
        if univ.logo:
            univ.logo.delete(save=False)
            univ.logo = None
            univ.save()
            return Response({"detail": "Logo supprimé."}, status=status.HTTP_200_OK)
        return Response({"detail": "Aucun logo à supprimer."}, status=status.HTTP_400_BAD_REQUEST)


# --------- 3. Gestion des membres ---------
class MembresListView(generics.ListAPIView):
    """
    GET /api/universites/<id>/membres/
    Liste paginée des membres avec rôle
    """
    serializer_class = RoleUniversiteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return RoleUniversite.objects.filter(universite_id=self.kwargs['pk'])

    # pagination déjà activée par ListAPIView


class MembreRoleUpdateView(generics.UpdateAPIView):
    """
    PATCH /api/universites/<id>/membres/<user_id>/role/
    Body : {"role": "professeur"}
    """
    queryset = RoleUniversite.objects.all()
    serializer_class = RoleUniversiteSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'utilisateur_id'

    def get_object(self):
        univ = get_object_or_404(Universite, pk=self.kwargs['pk'])
        return get_object_or_404(
            RoleUniversite, universite=univ, utilisateur_id=self.kwargs['user_id']
        )

    def update(self, request, *args, **kwargs):
        role_obj = self.get_object()
        new_role = request.data.get('role')
        if new_role not in [r[0] for r in RoleUniversite.ROLE_CHOICES]:
            return Response({"role": "Rôle inconnu."}, status=status.HTTP_400_BAD_REQUEST)
        role_obj.role = new_role
        role_obj.save()
        return Response({"detail": "Rôle mis à jour.", "role": new_role})


class MembreRemoveView(generics.DestroyAPIView):
    """
    DELETE /api/universites/<id>/membres/<user_id>/
    """
    queryset = RoleUniversite.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'utilisateur_id'

    def get_object(self):
        univ = get_object_or_404(Universite, pk=self.kwargs['pk'])
        role_obj = get_object_or_404(
            RoleUniversite, universite=univ, utilisateur_id=self.kwargs['user_id']
        )
        # Soi-même ou admin
        if role_obj.utilisateur != self.request.user and not self.request.user.is_staff:
            return Response({"detail": "Permission refusée."}, status=status.HTTP_403_FORBIDDEN)
        return role_obj

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if isinstance(instance, Response):  # déjà une 403
            return instance
        instance.delete()
        return Response({"detail": "Membre retiré de l’université."}, status=status.HTTP_204_NO_CONTENT)


# --------- 4. Bulk delete & export (super-admin) ---------
class BulkDeleteUniversitesView(generics.GenericAPIView):
    """
    POST /api/universites/bulk-delete/
    Body : {"ids": [1, 2, 3]}
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, *args, **kwargs):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({"ids": "Liste d’IDs requise."}, status=status.HTTP_400_BAD_REQUEST)
        queryset = Universite.objects.filter(id__in=ids)
        count = queryset.count()
        queryset.delete()
        return Response({"detail": f"{count} université(s) supprimée(s)."}, status=status.HTTP_200_OK)


class ExportUniversitesCSVView(generics.GenericAPIView):
    """
    GET /api/universites/export/csv/
    Télécharge un fichier CSV : nom, acronyme, nb membres, nb domaines
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, *args, **kwargs):
        from django.http import HttpResponse

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="universites.csv"'
        writer = csv.writer(response)
        writer.writerow(['Nom', 'Acronyme', 'Site web', 'Membres', 'Domaines', 'Créée le'])

        for univ in Universite.objects.all():
            writer.writerow([
                univ.nom,
                univ.acronyme,
                univ.site_web or '',
                univ.roles.count(),
                univ.domaines.count(),
                univ.created_at.date(),
            ])
        return response


# -------------------- CRUD complet + filtres --------------------
class DomaineViewSet(viewsets.ModelViewSet):
    queryset = Domaine.objects.all()
    serializer_class = DomaineSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nom', 'slug']
    ordering_fields = ['nom', 'id']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        nom = serializer.validated_data['nom']
        cleaned = unicodedata.normalize('NFKD', nom).encode('ASCII', 'ignore').decode('ASCII')
        slug = slugify(cleaned) or slugify(nom)
        if Domaine.objects.filter(slug=slug).exists():
            instance = Domaine.objects.get(slug=slug)
            serializer.instance = instance
            return instance
        serializer.save(slug=slug)

    def perform_destroy(self, instance):
        if instance.universites.exists():
            raise ValidationError("Ce domaine est encore rattaché à des universités.")
        super().perform_destroy(instance)


# -------------------- Suggestion orthographique --------------------
class DomaineSuggestView(generics.GenericAPIView):
    serializer_class = DomaineSerializer
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        q = request.GET.get('q', '').strip()
        if len(q) < 2:
            return Response([])
        cleaned = unicodedata.normalize('NFKD', q).encode('ASCII', 'ignore').decode('ASCII')
        slug_q = slugify(cleaned) or slugify(q)
        candidates = (
            Domaine.objects.annotate(similarity=TrigramSimilarity('slug', slug_q))
            .filter(similarity__gte=0.3)
            .order_by('-similarity')[:5]
        )
        return Response(self.get_serializer(candidates, many=True).data)


# -------------------- Liste filtrée par université --------------------
class DomaineByUniversiteListView(generics.ListAPIView):
    serializer_class = DomaineSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        univ = get_object_or_404(Universite, pk=self.kwargs['pk'])
        return univ.domaines.all()