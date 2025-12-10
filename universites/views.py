# universites/views.py
import csv
from django.conf import settings
import unicodedata
from django.core.exceptions import ValidationError
from django.contrib.postgres.search import TrigramSimilarity
from django.utils.text import slugify
from rest_framework import viewsets, permissions, filters, generics, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Universite, Domaine, RoleUniversite,News,OldStudent
from .serializers import (
    UniversiteSerializer,
    DomaineSerializer,
    UserRoleSerializer,
    OldStudentSerializer,
    NewsSerializer,
    RoleUniversiteSerializer,
)
from django.core.mail import send_mail, EmailMessage
from django.template.loader import render_to_string
from users.tokens import make_email_token, verify_email_token
import logging
from django.contrib.auth import get_user_model
User = get_user_model()
logger = logging.getLogger(__name__)


from users.permissions import(IsSuperAdminInUniversite,IsAdminInUniversite)
# -------------------- Université (CRUD) --------------------
class UniversiteViewSet(viewsets.ModelViewSet):
    queryset = Universite.objects.all()
    serializer_class = UniversiteSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['nom', 'acronyme']

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsSuperAdminInUniversite()]
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
            return [IsAdminInUniversite()]
        return [permissions.AllowAny()]

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

        # Normaliser et créer le slug
        cleaned = unicodedata.normalize('NFKD', q).encode('ASCII', 'ignore').decode('ASCII')
        slug_q = slugify(cleaned) or slugify(q)

        # Trouver les domaines correspondants sans filtrer par université
        candidates = (
            Domaine.objects.annotate(similarity=TrigramSimilarity('slug', slug_q))
            .filter(similarity__gte=0.3)  # Ajustez le seuil selon vos besoins
            .order_by('-similarity')[:5]
        )
        
        return Response(self.get_serializer(candidates, many=True).data)


# -------------------- Liste filtrée par université --------------------
class DomaineByUniversiteListView(generics.ListAPIView):
    serializer_class = DomaineSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        univ_slug = self.kwargs['univ_slug']
        univ = get_object_or_404(Universite, slug=univ_slug)
        return univ.domaines.all()
from universites.models import Universite
from .serializers import RegisterViaUniversiteSerializer


class RegisterViaUniversiteView(generics.CreateAPIView):
    """
    POST /api/auth/register-via-universite/
    Crée un compte + l’ajoute immédiatement à l’université choisie.
    """
    serializer_class = RegisterViaUniversiteSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        # envoi du mail de vérification (réutilisation du système existant)
        token = make_email_token(user.id)
        verify_url = f"{settings.FRONTEND_URL}/verify-email/?token={token}"

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
# universites/views.py
class DomaineCreateInUniversiteView(generics.CreateAPIView):
    serializer_class = DomaineSerializer
    permission_classes = [IsAdminInUniversite]   # ou [IsAuthenticated] si tu veux plus souple

    def perform_create(self, serializer):
        try:
            univ = get_object_or_404(Universite, slug=self.kwargs['univ_slug'])
            nom = serializer.validated_data['nom']
            cleaned = unicodedata.normalize('NFKD', nom).encode('ASCII', 'ignore').decode('ASCII')
            slug = slugify(cleaned) or slugify(nom)
            # dé-duplication
            counter = 1
            while Domaine.objects.filter(slug=slug).exists():
                slug = f"{slugify(nom)}-{counter}"
                counter += 1
            domaine = serializer.save(slug=slug)
            domaine.universites.add(univ)
        except Exception as e:
            # Gérer les exceptions
            print(f"Erreur lors de la création du domaine: {e}")
            raise  # Laissez les erreurs remonter
class DomaineDestroyInUniversiteView(generics.DestroyAPIView):
    permission_classes = [IsAdminInUniversite]

    def get_queryset(self):
        # Vous pouvez filtrer ici si besoin
        return Domaine.objects.all()

    def delete(self, request, univ_slug, domaine_slug, *args, **kwargs):
        universite = get_object_or_404(Universite, slug=univ_slug)
        domaine = get_object_or_404(Domaine, slug=domaine_slug)

        # Retirer l'université du domaine
        domaine.universites.remove(universite)

        if not domaine.universites.exists():
            # Si le domaine n'est associé à aucune autre université, supprimer le domaine
            domaine.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        
        return Response(status=status.HTTP_200_OK)
class UserRoleInUniversityView(generics.RetrieveAPIView):
    """
    GET /api/auth/<univ_slug>/my-role/
    Renvoie le rôle de l'utilisateur connecté dans l'université <univ_slug>.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserRoleSerializer

    def get_object(self):
        user = self.request.user
        univ = get_object_or_404(Universite, slug=self.kwargs["univ_slug"])
        return get_object_or_404(RoleUniversite, utilisateur=user, universite=univ)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
class UserRoleInUniversityByIdView(generics.RetrieveAPIView):
    """
    GET /api/auth/universities/<univ_slug>/user-role/<user_id>/
    Renvoie le rôle de l'utilisateur avec <user_id> dans l'université <univ_slug>.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserRoleSerializer

    def get_object(self):
        univ_slug = self.kwargs["univ_slug"]
        user_id = self.kwargs["user_id"]
        univ = get_object_or_404(Universite, slug=univ_slug)
        return get_object_or_404(RoleUniversite, utilisateur_id=user_id, universite=univ)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)        
class NewsBySlugViewSet(viewsets.ModelViewSet):
    """CRUD complet filtré sur l’université (slug)"""
    serializer_class = NewsSerializer

    def get_university(self):
        return get_object_or_404(Universite, slug=self.kwargs['slug'])

    def get_queryset(self):
        return News.objects.filter(publisher=self.get_university())

    def perform_create(self, serializer):
        # on lie automatiquement au slug de l’URL
        serializer.save(publisher=self.get_university())
    from rest_framework.decorators import action    
    @action(detail=True, methods=['delete'], url_path='dissociate')
    def dissociate(self, request, slug=None, pk=None):
        """
        Retire l'université 'slug' de la news.
        Si c'était la dernière → suppression complète.
        """
        university = self.get_university()          # slug de l'URL
        news = self.get_object()                    # pk de l'URL

        # 1. on retire l’université (relation M-N)
        news.universities.remove(university)

        # 2. s’il ne reste plus aucune université → on supprime la news
        if not news.universities.exists():
            news.delete()
            return Response({'detail': 'News supprimée (dernière université).'},
                            status=status.HTTP_204_NO_CONTENT)

        return Response({'detail': 'Université retirée.'},
                        status=status.HTTP_200_OK)    
class OldStudentBySlugViewSet(viewsets.ModelViewSet):
    """CRUD complet filtré sur l’université (slug)"""
    serializer_class = OldStudentSerializer
    permission_classes = [permissions.AllowAny]

    def get_university(self):
        return get_object_or_404(Universite, slug=self.kwargs['slug'])

    def get_queryset(self):
        return OldStudent.objects.filter(publisher=self.get_university())

    def perform_create(self, serializer):
        # on lie automatiquement au slug de l’URL
        serializer.save(publisher=self.get_university())
    from rest_framework.decorators import action    
    @action(detail=True, methods=['delete'], url_path='dissociate')
    def dissociate(self, request, slug=None, pk=None):
        """
        Retire l'université 'slug' de la news.
        Si c'était la dernière → suppression complète.
        """
        university = self.get_university()          # slug de l'URL
        oldstudent = self.get_object()                    # pk de l'URL

        # 1. on retire l’université (relation M-N)
        oldstudent.universities.remove(university)

        # 2. s’il ne reste plus aucune université → on supprime la news
        if not oldstudent.universities.exists():
            oldstudent.delete()
            return Response({'detail': 'News supprimée (dernière université).'},
                            status=status.HTTP_204_NO_CONTENT)

        return Response({'detail': 'Université retirée.'},
                        status=status.HTTP_200_OK)    


class NewsGlobalViewSet(viewsets.ModelViewSet):
    """CRUD global – on précise l’université dans le payload"""
    queryset = News.objects.all()
    serializer_class = NewsSerializer

    def create(self, request, *args, **kwargs):
        # on attend publisher (id ou slug) dans le payload
        univ_slug = request.data.get('publisher')
        if not univ_slug:
            return Response({'publisher': 'Ce champ est obligatoire.'},
                            status=status.HTTP_400_BAD_REQUEST)
        university = get_object_or_404(Universite, slug=univ_slug)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(publisher=university)
        return Response(serializer.data, status=status.HTTP_201_CREATED)    