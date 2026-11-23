from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from api.permissions import IsAuthenticated

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    demande_reference = serializers.ReadOnlyField(source='demande.reference')

    class Meta:
        model = Notification
        fields = ['id', 'evenement', 'titre', 'message', 'lien', 'demande', 'demande_reference', 'lue', 'creee_le']


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    GET  /notifications/?non_lues=1     mes notifications (20 par page)
    GET  /notifications/compteur/       { non_lues }
    POST /notifications/{id}/lire/
    POST /notifications/tout-lire/
    """
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Notification.objects.filter(destinataire=self.request.user).select_related('demande')
        if self.request.query_params.get('non_lues') == '1':
            qs = qs.filter(lue=False)
        return qs

    @action(detail=False, methods=['get'])
    def compteur(self, request):
        return Response({'non_lues': Notification.objects.filter(destinataire=request.user, lue=False).count()})

    @action(detail=True, methods=['post'])
    def lire(self, request, pk=None):
        Notification.objects.filter(destinataire=request.user, pk=pk).update(lue=True)
        return Response({'ok': True})

    @action(detail=False, methods=['post'], url_path='tout-lire')
    def tout_lire(self, request):
        n = Notification.objects.filter(destinataire=request.user, lue=False).update(lue=True)
        return Response({'lues': n})
