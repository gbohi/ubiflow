from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import ParametreSysteme
from api.permissions import IsAuthenticated, ReadAuthenticatedWriteAdminFinances
from audit.services import journaliser
from workflow.erreurs import ErreurMetier, Interdit

from . import serializers as s
from .models import ForfaitTransportHorsPays, PerDiem, TarifKilometrique, TarifTransportVille, TauxChange


class _BaremeViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                     mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """
    Lignes datées : création d'une nouvelle ligne pour tout changement (aucune
    modification), suppression seulement d'une ligne pas encore en vigueur.
    """
    permission_classes = [ReadAuthenticatedWriteAdminFinances]
    pagination_class = None

    def get_queryset(self):
        qs = self.queryset.select_related('modifie_par')
        for cle in self.queryset.model.CLE:
            valeur = self.request.query_params.get(cle)
            if valeur:
                qs = qs.filter(**{cle: valeur})
        return qs.order_by(*self.queryset.model.CLE, '-date_effet', '-id')

    def perform_create(self, serializer):
        obj = serializer.save(modifie_par=self.request.user)
        journaliser(self.request.user, 'bareme.creation', obj, apres=serializer.data, motif=obj.motif,
                    request=self.request)

    def perform_destroy(self, instance):
        if instance.date_effet <= timezone.localdate():
            raise ErreurMetier("Une ligne déjà en vigueur ne peut pas être supprimée : "
                               "créez une nouvelle ligne avec une date d'effet.")
        avant = self.get_serializer(instance).data
        journaliser(self.request.user, 'bareme.suppression', instance, avant=avant, request=self.request)
        instance.delete()


class PerDiemViewSet(_BaremeViewSet):
    queryset = PerDiem.objects.select_related('categorie')
    serializer_class = s.PerDiemSerializer


class TarifKilometriqueViewSet(_BaremeViewSet):
    queryset = TarifKilometrique.objects.select_related('categorie')
    serializer_class = s.TarifKilometriqueSerializer


class TarifTransportVilleViewSet(_BaremeViewSet):
    queryset = TarifTransportVille.objects.select_related('ville')
    serializer_class = s.TarifTransportVilleSerializer


class ForfaitTransportHorsPaysViewSet(_BaremeViewSet):
    queryset = ForfaitTransportHorsPays.objects.all()
    serializer_class = s.ForfaitTransportHorsPaysSerializer


class TauxChangeViewSet(_BaremeViewSet):
    queryset = TauxChange.objects.all()
    serializer_class = s.TauxChangeSerializer


class ParametreSystemeView(APIView):
    """GET : tous ; PATCH : administrateurs (devise de référence, taille des pièces)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(s.ParametreSystemeSerializer(ParametreSysteme.charger()).data)

    def patch(self, request):
        from api.permissions import is_admin_finances
        if not is_admin_finances(request.user):
            raise Interdit("Modification réservée aux administrateurs des finances.")
        obj = ParametreSysteme.charger()
        avant = s.ParametreSystemeSerializer(obj).data
        ser = s.ParametreSystemeSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save(user_updated=request.user)
        journaliser(request.user, 'parametrage.modification', obj, libelle='Paramètres système', avant=avant,
                    apres=ser.data, request=request)
        return Response(ser.data, status=status.HTTP_200_OK)
