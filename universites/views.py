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
from .models import Universite, Domaine, RoleUniversite,News,OldStudent,Affiliation
from .serializers import (
    UniversiteSerializer,
    DomaineSerializer,
    UserRoleSerializer,
    OldStudentSerializer,
    NewsSerializer,
    RoleUniversiteSerializer,
    AffiliationSerializer,
)
from universites.permissions import IsMemberOfUniversite,IsAdminOfUniversite ,IsBigBossOrSuperAdmin
from django.core.mail import send_mail, EmailMessage
from django.template.loader import render_to_string
from users.tokens import make_email_token, verify_email_token
import logging
from django.contrib.auth import get_user_model
User = get_user_model()
logger = logging.getLogger(__name__)

# ==== IMPORTS TRAÇABILITÉ (AJOUTÉS) ====
from users.utils import AuditMixin, serialize_instance, create_audit_log, get_client_ip
from users.models import AuditLog
from users.permissions import(IsSuperAdminInUniversite,IsAdminInUniversite)
# -------------------- Université (CRUD) --------------------
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

    def perform_create(self, serializer):
        instance = serializer.save()
        # ==== TRAÇABILITÉ CRÉATION UNIVERSITÉ ====
        create_audit_log(
            action=AuditLog.ActionType.UNIV_CREATE if hasattr(AuditLog.ActionType, 'UNIV_CREATE') else 'UNIV_CREATE',
            severity=AuditLog.Severity.MEDIUM,
            user=self.request.user,
            target=instance,
            target_type='Universite',
            new_data=serialize_instance(instance),
            request=self.request,
            description=f"Création de l'université {instance.nom}"
        )
        # =========================================
        return instance

    def perform_update(self, serializer):
        old_instance = self.get_object()
        previous_data = serialize_instance(old_instance)
        instance = serializer.save()
        # ==== TRAÇABILITÉ MODIFICATION UNIVERSITÉ ====
        create_audit_log(
            action=AuditLog.ActionType.UNIV_UPDATE if hasattr(AuditLog.ActionType, 'UNIV_UPDATE') else 'UNIV_UPDATE',
            severity=AuditLog.Severity.MEDIUM,
            user=self.request.user,
            target=instance,
            target_type='Universite',
            previous_data=previous_data,
            new_data=serialize_instance(instance),
            request=self.request,
            description=f"Modification de l'université {instance.nom}"
        )
        # =============================================
        return instance

    def perform_destroy(self, instance):
        previous_data = serialize_instance(instance)
        # ==== TRAÇABILITÉ SUPPRESSION UNIVERSITÉ (CRITICAL) ====
        create_audit_log(
            action=AuditLog.ActionType.UNIV_DELETE if hasattr(AuditLog.ActionType, 'UNIV_DELETE') else 'UNIV_DELETE',
            severity=AuditLog.Severity.CRITICAL,
            user=self.request.user,
            target=instance,
            target_type='Universite',
            previous_data=previous_data,
            request=self.request,
            description=f"SUPRESSION de l'université {instance.nom} ({instance.acronyme}) - ACTION CRITIQUE"
        )
        # ======================================================
        super().perform_destroy(instance)

# -------------------- Rôle par université --------------------
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
        instance = serializer.save()
        # ==== TRAÇABILITÉ ATTRIBUTION RÔLE ====
        create_audit_log(
            action=AuditLog.ActionType.USER_ROLE_CREATE if hasattr(AuditLog.ActionType, 'USER_ROLE_CREATE') else 'USER_ROLE_UPDATE',
            severity=AuditLog.Severity.HIGH,
            user=self.request.user,
            university=instance.universite,
            target=instance,
            target_type='RoleUniversite',
            new_data={
                'user': instance.utilisateur.email,
                'role': instance.role,
                'universite': instance.universite.nom
            },
            request=self.request,
            description=f"Attribution du rôle '{instance.role}' à {instance.utilisateur.email} dans {instance.universite.nom}"
        )
        # =====================================
        return instance

    def perform_destroy(self, instance):
        # ==== TRAÇABILITÉ RETRAIT RÔLE ====
        create_audit_log(
            action=AuditLog.ActionType.USER_ROLE_DELETE if hasattr(AuditLog.ActionType, 'USER_ROLE_DELETE') else 'USER_ROLE_UPDATE',
            severity=AuditLog.Severity.HIGH,
            user=self.request.user,
            university=instance.universite,
            target=instance,
            target_type='RoleUniversite',
            previous_data={
                'user': instance.utilisateur.email,
                'role': instance.role,
                'universite': instance.universite.nom
            },
            request=self.request,
            description=f"Retrait du rôle '{instance.role}' de {instance.utilisateur.email} dans {instance.universite.nom}"
        )
        # =================================
        super().perform_destroy(instance)


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
         # ==== TRAÇABILITÉ UPLOAD LOGO ====
        create_audit_log(
            action=AuditLog.ActionType.UNIV_LOGO_UPDATE,
            severity=AuditLog.Severity.LOW,
            user=request.user,
            target=univ,
            target_type='Universite',
            previous_data={'logo': old_logo},
            new_data={'logo': str(univ.logo)},
            request=request,
            description=f"Mise à jour du logo de {univ.nom}"
        )
        # =================================
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
            # ==== TRAÇABILITÉ SUPPRESSION LOGO ====
            create_audit_log(
                action=AuditLog.ActionType.UNIV_LOGO_DELETE,
                severity=AuditLog.Severity.LOW,
                user=request.user,
                target=univ,
                target_type='Universite',
                previous_data={'logo': old_logo},
                new_data={'logo': None},
                request=request,
                description=f"Suppression du logo de {univ.nom}"
            )
            # ======================================
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
        old_role = role_obj.role
        role_obj.save()
        # ==== TRAÇABILITÉ CHANGEMENT RÔLE (HIGH) ====
        create_audit_log(
            action=AuditLog.ActionType.USER_ROLE_UPDATE,
            severity=AuditLog.Severity.HIGH,
            user=request.user,
            university=role_obj.universite,
            target=role_obj,
            target_type='RoleUniversite',
            previous_data={'role': old_role, 'user': role_obj.utilisateur.email},
            new_data={'role': new_role, 'user': role_obj.utilisateur.email},
            request=request,
            description=f"Changement de rôle: {role_obj.utilisateur.email} passé de '{old_role}' à '{new_role}' dans {role_obj.universite.nom}"
        )
        # ============================================
        
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
        # ==== TRAÇABILITÉ RETRAIT MEMBRE (HIGH) ====
        create_audit_log(
            action=AuditLog.ActionType.USER_REMOVE,
            severity=AuditLog.Severity.HIGH,
            user=request.user,
            university=instance.universite,
            target=instance,
            target_type='RoleUniversite',
            previous_data={
                'user': instance.utilisateur.email,
                'role': instance.role,
                'universite': instance.universite.nom
            },
            request=request,
            description=f"Retrait de {instance.utilisateur.email} (rôle: {instance.role}) de l'université {instance.universite.nom}"
        )
        # ==========================================
        
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
        universities_data = list(queryset.values('id', 'nom', 'acronyme', 'slug'))
        count = queryset.count()
        # ==== TRAÇABILITÉ BULK DELETE (CRITICAL) ====
        audit_entry = create_audit_log(
            action=AuditLog.ActionType.UNIV_BULK_DELETE,
            severity=AuditLog.Severity.CRITICAL,
            user=request.user,
            target_type='Universite',
            target_id=f"bulk_{ids}",
            target_repr=f"Suppression de {count} universités",
            previous_data={'universities': universities_data, 'ids': ids},
            request=request,
            description=f"SUPRESSION BULK de {count} universités: {', '.join([u['nom'] for u in universities_data])} - ACTION CRITIQUE"
        )
        # ============================================
        
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
        try:
            univ = get_object_or_404(Universite, slug=self.kwargs['univ_slug'])
            nom = serializer.validated_data['nom']
            cleaned = unicodedata.normalize('NFKD', nom).encode('ASCII', 'ignore').decode('ASCII')
            slug = slugify(cleaned) or slugify(nom)
            
            # Dé-duplication
            counter = 1
            original_slug = slug  # Sauvegarder l'original
            while Domaine.objects.filter(slug=slug).exists():
                slug = f"{original_slug}-{counter}"  # Utiliser l'original pour éviter la confusion
                counter += 1
            
            # Sauvegarder le domaine
            domaine = serializer.save(slug=slug)
             
            # ==== TRAÇABILITÉ CRÉATION DOMAINE ====
            create_audit_log(
                action=AuditLog.ActionType.DOMAINE_CREATE,
                severity=AuditLog.Severity.MEDIUM,
                user=self.request.user,
                university=univ,
                target=domaine,
                target_type='Domaine',
                new_data=serialize_instance(domaine),
                request=self.request,
                description=f"Création du domaine '{domaine.nom}' dans {univ.nom}"
            )
            # =====================================
            # Ajouter l'université actuelle
            domaine.universites.add(univ)
            
            # Ajouter les universités mères
            for affiliation in univ.universites_affiliees.all():
                print("sdfgvnb,", affiliation.universite_mere)
                domaine.universites.add(affiliation.universite_mere)  # Ajouter chaque université mère
            
        except Exception as e:
            print(f"Erreur lors de la création du domaine: {e}")
            raise  # Laissez les erreurs remonter
    def perform_update(self, serializer):
        old_instance = self.get_object()
        previous_data = serialize_instance(old_instance)
        
        instance = serializer.save()
        
        # ==== TRAÇABILITÉ MODIFICATION DOMAINE ====
        univ_slug = self.kwargs.get('univ_slug')
        univ = get_object_or_404(Universite, slug=univ_slug) if univ_slug else None
        
        create_audit_log(
            action=AuditLog.ActionType.DOMAINE_UPDATE,
            severity=AuditLog.Severity.MEDIUM,
            user=self.request.user,
            university=univ,
            target=instance,
            target_type='Domaine',
            previous_data=previous_data,
            new_data=serialize_instance(instance),
            request=self.request,
            description=f"Modification du domaine '{instance.nom}'"
        )
        # ==========================================
        
        return instance
    def perform_destroy(self, instance):
        previous_data = serialize_instance(instance)
        univ_slug = self.kwargs.get('univ_slug')
        univ = get_object_or_404(Universite, slug=univ_slug) if univ_slug else None
        
        # ==== TRAÇABILITÉ SUPPRESSION DOMAINE (HIGH) ====
        create_audit_log(
            action=AuditLog.ActionType.DOMAINE_DELETE,
            severity=AuditLog.Severity.HIGH,
            user=self.request.user,
            university=univ,
            target=instance,
            target_type='Domaine',
            previous_data=previous_data,
            request=self.request,
            description=f"Suppression du domaine '{instance.nom}'"
        )
        # ==============================================
        
        if instance.universites.exists():
            raise ValidationError("Ce domaine est encore rattaché à des universités.")
        super().perform_destroy(instance)
from rest_framework.decorators import api_view, permission_classes
@api_view(['PATCH', 'PUT'])
@permission_classes([IsAdminInUniversite])
def domaine_update(request, univ_slug, domaine_slug):
    """
    Met à jour le nom (et donc le slug) d’un domaine
    rattaché à l’université <univ_slug>.
    """
    universite = get_object_or_404(Universite, slug=univ_slug)
    domaine    = get_object_or_404(Domaine, slug=domaine_slug)

    # Vérifie que le domaine est bien lié à cette université
    if not domaine.universites.filter(id=universite.id).exists():
        return Response({'detail': 'Domaine non rattaché à cette université'},
                        status=status.HTTP_404_NOT_FOUND)
    
    previous_data = serialize_instance(domaine)
    serializer = DomaineSerializer(domaine, data=request.data, partial=True)
    if serializer.is_valid(raise_exception=True):
        serializer.save()  # slug regénéré automatiquement # ==== TRAÇABILITÉ MISE À JOUR DOMAINE ====
        create_audit_log(
            action=AuditLog.ActionType.DOMAINE_UPDATE,
            severity=AuditLog.Severity.MEDIUM,
            user=request.user,
            university=universite,
            target=domaine,
            target_type='Domaine',
            previous_data=previous_data,
            new_data=serialize_instance(domaine),
            request=request,
            description=f"Mise à jour du domaine '{domaine.nom}' dans {universite.nom}"
        )
        # =========================================
        
        
        return Response(serializer.data, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
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


   
# universites/views.py
class DomaineCreateInUniversiteView(generics.CreateAPIView):
    serializer_class = DomaineSerializer
    permission_classes = [IsAdminOfUniversite]  
    # ou [IsAuthenticated] si tu veux plus souple

    def perform_create(self, serializer):
        try:
            univ = get_object_or_404(Universite, slug=self.kwargs['univ_slug'])
            nom = serializer.validated_data['nom']
            cleaned = unicodedata.normalize('NFKD', nom).encode('ASCII', 'ignore').decode('ASCII')
            slug = slugify(cleaned) or slugify(nom)
            
            # Dé-duplication
            counter = 1
            original_slug = slug  # Sauvegarder l'original
            while Domaine.objects.filter(slug=slug).exists():
                slug = f"{original_slug}-{counter}"  # Utiliser l'original pour éviter la confusion
                counter += 1
            print("sdfghj")
            # Sauvegarder le domaine
            domaine = serializer.save(slug=slug)
            # ==== TRAÇABILITÉ CRÉATION DOMAINE ====
            create_audit_log(
                action=AuditLog.ActionType.DOMAINE_CREATE,
                severity=AuditLog.Severity.MEDIUM,
                user=self.request.user,
                university=univ,
                target=domaine,
                target_type='Domaine',
                new_data=serialize_instance(domaine),
                request=self.request,
                description=f"Création du domaine '{domaine.nom}' dans {univ.nom}"
            )
            # =====================================
            
            # Ajouter l'université actuelle
            domaine.universites.add(univ)
            
            # Ajouter les universités mères
            for affiliation in univ.get_universites_meres():
                print(affiliation.universite_mere)
                domaine.universites.add(affiliation.universite_mere)  # Ajouter chaque université mère
            
        except Exception as e:
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
        # Données avant
        previous_data = serialize_instance(domaine)
        universites_liees = list(domaine.universites.values_list('nom', flat=True))
        # Retirer l'université du domaine
        domaine.universites.remove(universite)

        if not domaine.universites.exists():
            # ==== TRAÇABILITÉ SUPPRESSION TOTALE DOMAINE (HIGH) ====
            create_audit_log(
                action=AuditLog.ActionType.DOMAINE_DELETE,
                severity=AuditLog.Severity.HIGH,
                user=request.user,
                university=universite,
                target=domaine,
                target_type='Domaine',
                previous_data={**previous_data, 'universites_liees': universites_liees},
                request=request,
                description=f"Suppression totale du domaine '{domaine.nom}' (dernière université: {universite.nom})"
            )
            # =======================================================
            # Si le domaine n'est associé à aucune autre université, supprimer le domaine
            domaine.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        # ==== TRAÇABILITÉ RETRAIT DOMAINE ====
        create_audit_log(
            action=AuditLog.ActionType.DOMAINE_UPDATE,
            severity=AuditLog.Severity.MEDIUM,
            user=request.user,
            university=universite,
            target=domaine,
            target_type='Domaine',
            previous_data={'universites_liees': universites_liees},
            new_data={'universite_retiree': universite.nom},
            request=request,
            description=f"Retrait du domaine '{domaine.nom}' de l'université {universite.nom}"
        )
        # =====================================
        
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
from rest_framework.decorators import action
class NewsBySlugViewSet(viewsets.ModelViewSet):
    serializer_class = NewsSerializer

    def get_university(self):
        return get_object_or_404(Universite, slug=self.kwargs['slug'])

    def get_queryset(self):
        return News.objects.filter(publishers=self.get_university())

    def perform_create(self, serializer):
        news = serializer.save()
        univ = self.get_university()
        news.publishers.add(univ)
        
        # universités-mères via la méthode existante
        affiliations = univ.get_universites_meres()
        meres = [aff.universite_mere for aff in affiliations]
        if meres:
            news.publishers.add(*meres)
        
        # ==== TRAÇABILITÉ CRÉATION NEWS ====
        create_audit_log(
            action=AuditLog.ActionType.NEWS_CREATE,
            severity=AuditLog.Severity.MEDIUM,
            user=self.request.user if self.request.user.is_authenticated else None,
            university=univ,
            target=news,
            target_type='News',
            new_data={
                'title': news.title,
                'slug': news.slug,
                'topics': news.topics,
                'publishers': [p.nom for p in news.publishers.all()]
            },
            request=self.request,
            description=f"Création de la news '{news.title}' dans {univ.nom}"
        )
        # ==================================
        return news

    def perform_update(self, serializer):
        """
        PUT/PATCH /api/universites/<slug>/news/<pk>/
        Modification d'une news avec traçabilité
        """
        # Récupérer l'ancienne instance avant modification
        old_instance = self.get_object()
        previous_data = {
            'title': old_instance.title,
            'headline': old_instance.headline,
            'body': old_instance.body[:200] + '...' if len(old_instance.body) > 200 else old_instance.body,
            'topics': old_instance.topics,
            'is_published': old_instance.is_published,
            'publish_at': str(old_instance.publish_at),
        }
        
        # Sauvegarder les modifications
        news = serializer.save()
        univ = self.get_university()
        
        # ==== TRAÇABILITÉ MODIFICATION NEWS ====
        create_audit_log(
            action=AuditLog.ActionType.NEWS_UPDATE,
            severity=AuditLog.Severity.MEDIUM,
            user=self.request.user if self.request.user.is_authenticated else None,
            university=univ,
            target=news,
            target_type='News',
            previous_data=previous_data,
            new_data={
                'title': news.title,
                'slug': news.slug,
                'topics': news.topics,
                'is_published': news.is_published,
            },
            request=self.request,
            description=f"Modification de la news '{news.title}' dans {univ.nom}"
        )
        # ======================================
        
        return news

    def perform_destroy(self, instance):
        """
        DELETE /api/universites/<slug>/news/<pk>/
        Suppression directe d'une news (pas dissociation) avec traçabilité
        """
        univ = self.get_university()
        
        # Données avant suppression
        previous_data = {
            'title': instance.title,
            'slug': instance.slug,
            'topics': instance.topics,
            'publishers': [p.nom for p in instance.publishers.all()],
        }
        
        # ==== TRAÇABILITÉ SUPPRESSION NEWS (HIGH) ====
        create_audit_log(
            action=AuditLog.ActionType.NEWS_DELETE,
            severity=AuditLog.Severity.HIGH,
            user=self.request.user if self.request.user.is_authenticated else None,
            university=univ,
            target=instance,
            target_type='News',
            previous_data=previous_data,
            request=self.request,
            description=f"Suppression directe de la news '{instance.title}' de {univ.nom}"
        )
        # ===========================================
        
        # Suppression réelle
        instance.delete()

    @action(detail=True, methods=['delete'], url_path='dissociate')
    def dissociate(self, request, slug=None, pk=None):
        print("delete()")
        university = self.get_university()
        news = self.get_object()
        previous_publishers = [p.nom for p in news.publishers.all()]
        affiliations = university.get_universites_meres()
        meres = [aff.universite_mere for aff in affiliations]
        to_remove = [university] + meres
        news.publishers.remove(*to_remove)

        if not news.publishers.exists():
            # ==== TRAÇABILITÉ SUPPRESSION NEWS (HIGH) ====
            create_audit_log(
                action=AuditLog.ActionType.NEWS_DELETE,
                severity=AuditLog.Severity.HIGH,
                user=request.user if request.user.is_authenticated else None,
                university=university,
                target=news,
                target_type='News',
                previous_data={'title': news.title, 'publishers': previous_publishers},
                request=request,
                description=f"Suppression totale de la news '{news.title}' (dernière université retirée)"
            )
            # ===========================================
            news.delete()
            return Response({'detail': 'News supprimée (dernière université).'},
                            status=status.HTTP_204_NO_CONTENT)
        
        # ==== TRAÇABILITÉ DISSOCIATION NEWS ====
        create_audit_log(
            action=AuditLog.ActionType.NEWS_DISSOCIATE,
            severity=AuditLog.Severity.MEDIUM,
            user=request.user if request.user.is_authenticated else None,
            university=university,
            target=news,
            target_type='News',
            previous_data={'publishers': previous_publishers},
            new_data={'publishers_retirees': [u.nom for u in to_remove]},
            request=request,
            description=f"Dissociation de la news '{news.title}' de {university.nom}"
        )
        # =======================================    
        return Response({'detail': 'Université(s) retirée(s).'},
                        status=status.HTTP_200_OK)
class OldStudentBySlugViewSet(viewsets.ModelViewSet):
    serializer_class = OldStudentSerializer
    permission_classes = [permissions.AllowAny]

    def get_university(self):
        return get_object_or_404(Universite, slug=self.kwargs['slug'])

    def get_queryset(self):
        return OldStudent.objects.filter(publishers=self.get_university())

    def perform_create(self, serializer):
        old = serializer.save()
        univ = self.get_university()
        old.publishers.add(univ)
        affiliations = univ.get_universites_meres()
        meres = [aff.universite_mere for aff in affiliations]
        if meres:
            old.publishers.add(*meres)
        
        # ==== TRAÇABILITÉ CRÉATION OLDSTUDENT ====
        create_audit_log(
            action=AuditLog.ActionType.OLDSTUDENT_CREATE,
            severity=AuditLog.Severity.MEDIUM,
            user=self.request.user if self.request.user.is_authenticated else None,
            university=univ,
            target=old,
            target_type='OldStudent',
            new_data={
                'title': old.title,
                'publishers': [p.nom for p in old.publishers.all()]
            },
            request=self.request,
            description=f"Création de l'ancien étudiant '{old.title}' dans {univ.nom}"
        )
        # =========================================
        return old

    def perform_update(self, serializer):
        """
        PUT/PATCH /api/universites/<slug>/oldstudents/<pk>/
        Modification d'un ancien étudiant avec traçabilité
        """
        # Récupérer l'ancienne instance avant modification
        old_instance = self.get_object()
        previous_data = {
            'title': old_instance.title,
            'body': old_instance.body[:200] + '...' if len(old_instance.body) > 200 else old_instance.body,
            'cover': str(old_instance.cover) if old_instance.cover else None,
        }
        
        # Sauvegarder les modifications
        old = serializer.save()
        univ = self.get_university()
        
        # ==== TRAÇABILITÉ MODIFICATION OLDSTUDENT ====
        create_audit_log(
            action=AuditLog.ActionType.OLDSTUDENT_UPDATE,
            severity=AuditLog.Severity.MEDIUM,
            user=self.request.user if self.request.user.is_authenticated else None,
            university=univ,
            target=old,
            target_type='OldStudent',
            previous_data=previous_data,
            new_data={
                'title': old.title,
                'cover': str(old.cover) if old.cover else None,
            },
            request=self.request,
            description=f"Modification de l'ancien étudiant '{old.title}' dans {univ.nom}"
        )
        # ============================================
        
        return old

    def perform_destroy(self, instance):
        """
        DELETE /api/universites/<slug>/oldstudents/<pk>/
        Suppression directe d'un ancien étudiant (pas dissociation) avec traçabilité
        """
        univ = self.get_university()
        
        # Données avant suppression
        previous_data = {
            'title': instance.title,
            'body': instance.body[:200] + '...' if len(instance.body) > 200 else instance.body,
            'publishers': [p.nom for p in instance.publishers.all()],
        }
        
        # ==== TRAÇABILITÉ SUPPRESSION OLDSTUDENT (HIGH) ====
        create_audit_log(
            action=AuditLog.ActionType.OLDSTUDENT_DELETE,
            severity=AuditLog.Severity.HIGH,
            user=self.request.user if self.request.user.is_authenticated else None,
            university=univ,
            target=instance,
            target_type='OldStudent',
            previous_data=previous_data,
            request=self.request,
            description=f"Suppression directe de l'ancien étudiant '{instance.title}' de {univ.nom}"
        )
        # ==================================================
        
        # Suppression réelle
        instance.delete()

    @action(detail=True, methods=['delete'], url_path='dissociate')
    def dissociate(self, request, slug=None, pk=None):
        university = self.get_university()
        old = self.get_object()
        previous_publishers = [p.nom for p in old.publishers.all()]
        affiliations = university.get_universites_meres()
        meres = [aff.universite_mere for aff in affiliations]
        to_remove = [university] + meres
        old.publishers.remove(*to_remove)

        if not old.publishers.exists():
            # ==== TRAÇABILITÉ SUPPRESSION TOTALE OLDSTUDENT (HIGH) ====
            create_audit_log(
                action=AuditLog.ActionType.OLDSTUDENT_DELETE,
                severity=AuditLog.Severity.HIGH,
                user=request.user if request.user.is_authenticated else None,
                university=university,
                target=old,
                target_type='OldStudent',
                previous_data={'title': old.title, 'publishers': previous_publishers},
                request=request,
                description=f"Suppression totale de l'ancien étudiant '{old.title}' (dernière université retirée)"
            )
            # =========================================================
            old.delete()
            return Response({'detail': 'OldStudent supprimé (dernière université).'},
                            status=status.HTTP_204_NO_CONTENT)
        
        # ==== TRAÇABILITÉ DISSOCIATION OLDSTUDENT ====
        create_audit_log(
            action=AuditLog.ActionType.OLDSTUDENT_DISSOCIATE,
            severity=AuditLog.Severity.MEDIUM,
            user=request.user if request.user.is_authenticated else None,
            university=university,
            target=old,
            target_type='OldStudent',
            previous_data={'publishers': previous_publishers},
            new_data={'publishers_retirees': [u.nom for u in to_remove]},
            request=request,
            description=f"Dissociation de l'ancien étudiant '{old.title}' de {university.nom}"
        )
        # ============================================    
        return Response({'detail': 'Université(s) retirée(s).'},
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
        # ==== TRAÇABILITÉ CRÉATION NEWS GLOBALE ====
        create_audit_log(
            action=AuditLog.ActionType.NEWS_CREATE,
            severity=AuditLog.Severity.MEDIUM,
            user=request.user if request.user.is_authenticated else None,
            university=university,
            target=news,
            target_type='News',
            new_data={
                'title': news.title,
                'slug': news.slug,
                'topics': news.topics
            },
            request=request,
            description=f"Création globale de la news '{news.title}' dans {university.nom}"
        )
        # ==========================================
        return Response(serializer.data, status=status.HTTP_201_CREATED)    
    



class AffilierUniversiteView(generics.CreateAPIView):
    """
    POST /api/universites/affilier/
    Body :
    {
        "universite_mere_slug": "paris-1",
        "universite_fille_slug": "paris-1-antenne-creteil"
    }
    """
    queryset = Affiliation.objects.all()
    serializer_class = AffiliationSerializer
    permission_classes = [permissions.IsAuthenticated, IsBigBossOrSuperAdmin]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        affiliation = serializer.save()
        # ==== TRAÇABILITÉ CRÉATION AFFILIATION (HIGH) ====
        create_audit_log(
            action=AuditLog.ActionType.UNIV_AFFILIATION_CREATE,
            severity=AuditLog.Severity.HIGH,
            user=request.user,
            university=mere,
            target=affiliation,
            target_type='Affiliation',
            new_data={
                'universite_mere': mere.nom if mere else None,
                'universite_fille': fille.nom if fille else None,
                'universite_mere_slug': mere_slug,
                'universite_fille_slug': fille_slug
            },
            request=request,
            description=f"Affiliation créée: {fille.nom if fille else 'N/A'} → {mere.nom if mere else 'N/A'}"
        )
        # ================================================
        return Response(
            {"detail": f"Université affiliée avec succès : {affiliation}"},
            status=status.HTTP_201_CREATED
        )    