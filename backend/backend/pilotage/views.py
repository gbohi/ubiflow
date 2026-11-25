from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsAuthenticated

from .indicateurs import profils_accessibles, tableau_de_bord


class ProfilsView(APIView):
    """GET /tableaux-de-bord/ : tableaux accessibles à l'utilisateur."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(profils_accessibles(request.user))


class AccueilView(APIView):
    """GET /accueil/?profil= : accueil de synthèse (collaborateur, valideur, direction, finances)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .accueil import accueil
        return Response(accueil(request.user, request.query_params.get('profil')))


class RechercheView(APIView):
    """
    GET /recherche/?q=  recherche globale de la barre du haut : demandes que l'utilisateur
    a le droit de voir (les siennes, celles qu'il valide ou a validées, et pour les
    profils de gestion toutes celles de son périmètre ; jamais les brouillons des autres),
    par référence, objet ou demandeur (nom, prénom, matricule). 8 résultats au plus.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db.models import Q
        from demandes.models import StatutDemande
        from demandes.services import demandes_visibles
        q = (request.query_params.get('q') or '').strip()
        if len(q) < 2:
            return Response({'q': q, 'demandes': [], 'total': 0})
        filtre = Q()
        for mot in q.split()[:4]:
            filtre &= (Q(reference__icontains=mot) | Q(objet__icontains=mot) | Q(demandeur__nom__icontains=mot)
                       | Q(demandeur__prenom__icontains=mot) | Q(demandeur__username__iexact=mot))
        qs = (demandes_visibles(request.user).exclude(Q(statut=StatutDemande.BROUILLON) & ~Q(demandeur=request.user))
              .filter(filtre).select_related('type_demande', 'demandeur').order_by('-updated_at'))
        total = qs.count()
        return Response({'q': q, 'total': total, 'demandes': [{
            'id': d.pk, 'reference': d.reference or 'Brouillon', 'objet': d.objet, 'type': d.type_demande.libelle,
            'type_code': d.type_demande.code, 'type_icone': d.type_demande.icone, 'statut': d.statut,
            'statut_libelle': d.get_statut_display(), 'demandeur': f"{d.demandeur.nom} {d.demandeur.prenom}".strip(),
            'montant': str(d.montant_approuve if d.montant_approuve is not None else d.montant_demande or '') or None,
            'devise': d.devise} for d in qs[:8]]})


class ThemesStatistiquesView(APIView):
    """GET /statistiques/ : tableaux de statistiques accessibles (vide si aucun)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .statistiques import themes
        return Response(themes(request.user))


class StatistiquesView(APIView):
    """
    GET /statistiques/{theme}/?du=&au=&type_demande=&statut=&departement=&agence=&categorie=&demandeur=
    theme : global, missions, finances, paiements, departements, circuits, remboursements, receptions.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, theme):
        from .statistiques import statistiques
        return Response(statistiques(request.user, theme, request.query_params))


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
