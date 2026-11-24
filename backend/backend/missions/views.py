from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsAuthenticated, ReadAuthenticatedWriteAdminFinances
from demandes.models import Demande, TypeDemande
from demandes.services import peut_voir
from demandes.views import _JournalMixin
from workflow.erreurs import ErreurMetier, Interdit

from .extension import apercu
from .models import Distance, Pays, Ville
from .serializers import DistanceSerializer, PaysSerializer, VilleSerializer


class PaysViewSet(_JournalMixin, viewsets.ModelViewSet):
    serializer_class = PaysSerializer
    permission_classes = [ReadAuthenticatedWriteAdminFinances]
    pagination_class = None
    filter_backends = [filters.SearchFilter]
    search_fields = ['libelle', 'code_iso']

    def get_queryset(self):
        qs = Pays.objects.annotate(nb_villes=Count('villes'))
        if self.request.query_params.get('tous') != '1':
            qs = qs.filter(actif=True)
        return qs


class VilleViewSet(_JournalMixin, viewsets.ModelViewSet):
    """GET /villes/?pays=&locales=1 (villes du pays de la société)&tous=1 (inactives aussi)."""
    serializer_class = VilleSerializer
    permission_classes = [ReadAuthenticatedWriteAdminFinances]
    pagination_class = None
    filter_backends = [filters.SearchFilter]
    search_fields = ['libelle', 'pays__libelle']

    def get_queryset(self):
        qs = Ville.objects.select_related('pays')
        p = self.request.query_params
        if p.get('tous') != '1':
            qs = qs.filter(actif=True, pays__actif=True)
        if p.get('pays'):
            qs = qs.filter(pays_id=p['pays'])
        if p.get('pays_code'):
            qs = qs.filter(pays__code_iso=p['pays_code'].upper())
        if p.get('exclure_pays_code'):
            qs = qs.exclude(pays__code_iso=p['exclure_pays_code'].upper())
        return qs


class DistanceViewSet(_JournalMixin, viewsets.ModelViewSet):
    """GET /distances/?ville=  ;  GET /distances/entre/?a=&b="""
    serializer_class = DistanceSerializer
    permission_classes = [ReadAuthenticatedWriteAdminFinances]
    pagination_class = None

    def get_queryset(self):
        qs = Distance.objects.select_related('ville_a', 'ville_b').order_by('ville_a__libelle', 'ville_b__libelle')
        ville = self.request.query_params.get('ville')
        if ville:
            qs = qs.filter(Q(ville_a_id=ville) | Q(ville_b_id=ville))
        return qs

    @action(detail=False, methods=['get'])
    def entre(self, request):
        d = Distance.entre(request.query_params.get('a'), request.query_params.get('b'))
        return Response({'km': d.km if d else None})


class CalculerMissionView(APIView):
    """
    POST /missions/calculer/ { type_demande, mission, demande? }
    Récapitulatif en direct (rien n'est enregistré).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        type_demande = get_object_or_404(TypeDemande, pk=request.data.get('type_demande'))
        if type_demande.famille != 'mission':
            raise ErreurMetier("Ce type de demande n'est pas une mission.")
        demande = None
        if request.data.get('demande'):
            demande = get_object_or_404(Demande, pk=request.data['demande'])
            if not peut_voir(demande, request.user):
                raise Interdit("Vous n'avez pas accès à cette demande.")
        mission = request.data.get('mission') or {}
        if not isinstance(mission, dict):
            raise ErreurMetier({'mission': 'Format invalide.'})
        return Response(apercu(request.user, type_demande, mission, demande))


class CloturesAControlerView(APIView):
    """GET /missions/clotures/?etat=soumise : clôtures que l'utilisateur peut contrôler."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .cloture import peut_controler
        from .models import ClotureMission
        etat = request.query_params.get('etat', 'soumise')
        qs = (ClotureMission.objects.filter(etat=etat).select_related('demande__type_demande', 'demande__demandeur')
              .order_by('soumise_le'))
        lignes = []
        for c in qs:
            d = c.demande
            if not peut_controler(d, request.user):
                continue
            lignes.append({'id': d.pk, 'reference': d.reference, 'type_libelle': d.type_demande.libelle,
                           'type_code': d.type_demande.code, 'type_icone': d.type_demande.icone,
                           'demandeur_nom': f"{d.demandeur.nom} {d.demandeur.prenom}".strip(), 'objet': d.objet,
                           'montant_approuve': d.montant_approuve, 'montant_paye': d.montant_paye, 'devise': d.devise,
                           'soumise_le': c.soumise_le, 'etat': c.etat, 'etat_libelle': c.get_etat_display(),
                           'total_reel': (c.calcul or {}).get('total')})
        return Response(lignes)
