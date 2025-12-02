# interactions/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count
from .models import Telechargement, Like, Commentaire
from .serializers import TelechargementSerializer, LikeSerializer, CommentaireSerializer
from memoires.models import Memoire


class TelechargementViewSet(viewsets.ModelViewSet):
    queryset = Telechargement.objects.all()
    serializer_class = TelechargementSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Utilisateur standard : ne voit que ses téléchargements
        if self.request.user.is_staff:
            return self.queryset
        return self.queryset.filter(utilisateur=self.request.user)

    def create(self, request, *args, **kwargs):
        memoire_id = request.data.get('memoire')
        if not memoire_id:
            return Response({'detail': 'mémoire requis'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            memoire = Memoire.objects.get(pk=memoire_id)
        except Memoire.DoesNotExist:
            return Response({'detail': 'Mémoire introuvable'}, status=status.HTTP_404_NOT_FOUND)

        telechargement, created = Telechargement.objects.get_or_create(
            utilisateur=request.user,
            memoire=memoire,
            defaults={
                'ip': request.META.get('REMOTE_ADDR'),
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
            }
        )
        if not created:
            return Response({'detail': 'Déjà téléchargé'}, status=status.HTTP_200_OK)

        serializer = self.get_serializer(telechargement)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='mes-telechargements')
    def mes_telechargements(self, request):
        qs = self.get_queryset().select_related('memoire')
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='par-memoire/(?P<memoire_id>\d+)')
    def par_memoire(self, request, memoire_id=None):
        try:
            memoire = Memoire.objects.get(pk=memoire_id)
        except Memoire.DoesNotExist:
            return Response({'detail': 'Mémoire introuvable'}, status=status.HTTP_404_NOT_FOUND)

        if request.user != memoire.auteur and not request.user.is_staff:
            return Response({'detail': 'Non autorisé'}, status=status.HTTP_403_FORBIDDEN)

        qs = self.queryset.filter(memoire=memoire).select_related('utilisateur')
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)
class LikeViewSet(viewsets.ModelViewSet):
    queryset = Like.objects.all()
    serializer_class = LikeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset
        return self.queryset.filter(utilisateur=self.request.user)

    def create(self, request, *args, **kwargs):
        memoire_id = request.data.get('memoire')
        if not memoire_id:
            return Response({'detail': 'mémoire requis'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            memoire = Memoire.objects.get(pk=memoire_id)
        except Memoire.DoesNotExist:
            return Response({'detail': 'Mémoire introuvable'}, status=status.HTTP_404_NOT_FOUND)

        like, created = Like.objects.get_or_create(
            utilisateur=request.user,
            memoire=memoire
        )
        if not created:
            return Response({'detail': 'Déjà liké'}, status=status.HTTP_200_OK)

        serializer = self.get_serializer(like)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['delete'], url_path='unlike/(?P<memoire_id>\d+)')
    def unlike(self, request, memoire_id=None):
        deleted, _ = Like.objects.filter(utilisateur=request.user, memoire_id=memoire_id).delete()
        if deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response({'detail': 'Like non trouvé'}, status=status.HTTP_404_NOT_FOUND)    
class CommentaireViewSet(viewsets.ModelViewSet):
    queryset = Commentaire.objects.filter(modere=False)
    serializer_class = CommentaireSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_staff:
            return Commentaire.objects.all()  # modérateur voit tout
        memoire_id = self.request.query_params.get('memoire')
        if memoire_id:
            qs = qs.filter(memoire_id=memoire_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(utilisateur=self.request.user)

    @action(detail=True, methods=['patch'], url_path='moderer')
    def moderer(self, request, pk=None):
        if not request.user.is_staff:
            return Response({'detail': 'Réservé aux modérateurs'}, status=status.HTTP_403_FORBIDDEN)
        commentaire = self.get_object()
        commentaire.modere = not commentaire.modere
        commentaire.save()
        return Response({'modere': commentaire.modere})    
# interactions/views.py (ajout)
from rest_framework.generics import GenericAPIView

class InteractionsGlobalStatsView(GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from interactions.models import Telechargement, Like, Commentaire
        return Response({
            "total_telechargements": Telechargement.objects.count(),
            "total_likes": Like.objects.count(),
            "total_commentaires": Commentaire.objects.filter(modere=False).count(),
            "top_memoire_telecharge": (
                Telechargement.objects.values('memoire__titre')
                .annotate(nb=Count('id'))
                .order_by('-nb')
                .first()
            ),
            "top_memoire_like": (
                Like.objects.values('memoire__titre')
                .annotate(nb=Count('id'))
                .order_by('-nb')
                .first()
            ),
        })    