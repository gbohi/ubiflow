from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsAuthenticated

from .indicateurs import profils_accessibles, tableau_de_bord


class ProfilsView(APIView):
    """GET /tableaux-de-bord/ : tableaux accessibles à l'utilisateur."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(profils_accessibles(request.user))


class TableauDeBordView(APIView):
    """
    GET /tableaux-de-bord/{profil}/?du=&au=&type_demande=&statut=&departement=&agence=&categorie=&demandeur=
    profil : collaborateur, valideur, direction, comptabilite, administrateur.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, profil):
        return Response(tableau_de_bord(request.user, profil, request.query_params))


from rest_framework import serializers, viewsets  # noqa: E402

from api.models import PerimetreConsultation  # noqa: E402
from api.permissions import IsAdminRole  # noqa: E402


class PerimetreConsultationSerializer(serializers.ModelSerializer):
    user_nom = serializers.SerializerMethodField()
    type_libelle = serializers.CharField(source='get_type_display', read_only=True)
    departement_libelle = serializers.ReadOnlyField(source='departement.libelle_service')
    agence_libelle = serializers.ReadOnlyField(source='agence.nom_agence')

    class Meta:
        model = PerimetreConsultation
        fields = '__all__'

    def get_user_nom(self, obj):
        return f"{obj.user.nom} {obj.user.prenom} ({obj.user.username})".strip()

    def validate(self, attrs):
        t = attrs.get('type', getattr(self.instance, 'type', None))
        if t == 'departement' and not attrs.get('departement', getattr(self.instance, 'departement', None)):
            raise serializers.ValidationError({'departement': 'Choisissez le département.'})
        if t == 'agence' and not attrs.get('agence', getattr(self.instance, 'agence', None)):
            raise serializers.ValidationError({'agence': "Choisissez l'agence."})
        if t != 'departement':
            attrs['departement'] = None
        if t != 'agence':
            attrs['agence'] = None
        return attrs


class PerimetreConsultationViewSet(viewsets.ModelViewSet):
    """Périmètres de consultation des profils direction, contrôleur, gestionnaire (administrateurs)."""
    queryset = PerimetreConsultation.objects.select_related('user', 'departement', 'agence')
    serializer_class = PerimetreConsultationSerializer
    permission_classes = [IsAdminRole]
    pagination_class = None
