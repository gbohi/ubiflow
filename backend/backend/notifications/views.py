from rest_framework.views import APIView
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


class PreferencesView(APIView):
    """
    GET /notifications/preferences/ : événements, canaux par défaut, choix de l'utilisateur, état des canaux.
    PUT /notifications/preferences/ : [{evenement, email, push}] (événements désactivables seulement).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .canaux import EVENEMENTS, canaux_de, email_configure, push_configure
        lignes = []
        for code, (libelle, email_d, push_d, desactivable) in EVENEMENTS.items():
            email, push = canaux_de(request.user, code)
            lignes.append({'evenement': code, 'libelle': libelle, 'email': email, 'push': push, 'email_defaut': email_d,
                           'push_defaut': push_d, 'desactivable': desactivable})
        return Response({'email_actif': email_configure(), 'push_actif': push_configure(),
                         'adresse': request.user.email, 'appareils': request.user.appareils_mobiles.filter(actif=True).count(),
                         'evenements': lignes})

    def put(self, request):
        from .canaux import EVENEMENTS
        from .models import PreferenceNotification
        for p in request.data if isinstance(request.data, list) else []:
            code = p.get('evenement')
            if code not in EVENEMENTS or not EVENEMENTS[code][3]:
                continue
            PreferenceNotification.objects.update_or_create(user=request.user, evenement=code, defaults={
                'email': bool(p.get('email')), 'push': bool(p.get('push'))})
        return self.get(request)


class AppareilsView(APIView):
    """POST /notifications/appareils/ {jeton, plateforme} (application mobile) ; DELETE ?jeton= à la déconnexion."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .models import AppareilMobile
        jeton = (request.data.get('jeton') or '').strip()
        if not jeton:
            return Response({'jeton': 'Jeton manquant.'}, status=400)
        AppareilMobile.objects.update_or_create(jeton=jeton, defaults={
            'user': request.user, 'actif': True, 'plateforme': request.data.get('plateforme') or 'android'})
        return Response(status=204)

    def delete(self, request):
        from .models import AppareilMobile
        AppareilMobile.objects.filter(user=request.user, jeton=request.query_params.get('jeton', '')).update(actif=False)
        return Response(status=204)
