from decimal import Decimal, InvalidOperation
from io import BytesIO

from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from api.permissions import is_admin_finances, is_comptable
from audit.services import infos_requete
from demandes.models import Demande
from demandes.serializers import DemandeListeSerializer
from demandes.views import filtrer_par_dates
from workflow.erreurs import ErreurMetier
from workflow.models import EtapeInstance, InstanceWorkflow, Tache

from . import services
from .models import Reglement, Reversement
from .serializers import ReglementSerializer, ReversementSerializer


class EstTresorerie(BasePermission):
    message = "Accès réservé à la comptabilité et aux administrateurs des finances."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and (is_comptable(request.user) or is_admin_finances(request.user)))


def _decimal(v):
    try:
        return Decimal(str(v).replace(' ', '').replace(',', '.'))
    except (InvalidOperation, ValueError):
        raise ErreurMetier('Montant de filtre invalide.')


class APayerViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    GET /tresorerie/a-payer/?type_demande=&departement=&agence=&du=&au=&montant_min=&montant_max=&search=
        demandes approuvées à payer (ou partiellement payées), les plus anciennes d'abord ;
        &export=xlsx : fichier Excel de la liste filtrée.
    """
    serializer_class = DemandeListeSerializer
    permission_classes = [EstTresorerie]
    filter_backends = [filters.SearchFilter]
    search_fields = ['reference', 'objet', 'demandeur__nom', 'demandeur__prenom', 'demandeur__username']

    def get_queryset(self):
        p = self.request.query_params
        qs = Demande.objects.filter(statut__in=services.STATUTS_PAYABLES,
                                    statut_financier__in=services.FINANCIERS_PAYABLES)
        for cle, champ in (('type_demande', 'type_demande_id'), ('departement', 'departement_id'),
                           ('agence', 'agence_id')):
            if p.get(cle):
                qs = qs.filter(**{champ: p[cle]})
        if p.get('montant_min'):
            qs = qs.filter(montant_approuve__gte=_decimal(p['montant_min']))
        if p.get('montant_max'):
            qs = qs.filter(montant_approuve__lte=_decimal(p['montant_max']))
        qs = filtrer_par_dates(qs, p, 'approuvee_le')
        etapes = EtapeInstance.objects.select_related('etape').prefetch_related(
            Prefetch('taches', queryset=Tache.objects.select_related('valideur')))
        return qs.select_related('type_demande', 'demandeur', 'departement', 'agence').prefetch_related(
            Prefetch('instances', queryset=InstanceWorkflow.objects.prefetch_related(
                Prefetch('etapes', queryset=etapes)))).order_by('approuvee_le', 'id')

    def list(self, request, *args, **kwargs):
        if request.query_params.get('export') == 'xlsx':
            return self._export(self.filter_queryset(self.get_queryset()))
        return super().list(request, *args, **kwargs)

    def _export(self, qs):
        from openpyxl import Workbook
        from openpyxl.styles import Font
        wb = Workbook()
        ws = wb.active
        ws.title = 'À payer'
        entetes = ['N°', 'Référence', 'Type', 'Demandeur', 'Département', 'Agence', 'Objet', 'Approuvée le',
                   'Montant approuvé', 'Payé', 'Reste à payer', 'Devise', 'Statut financier']
        ws.append(entetes)
        for c in ws[1]:
            c.font = Font(bold=True)
        for i, d in enumerate(qs, start=1):
            ws.append([i, d.reference, d.type_demande.libelle, f"{d.demandeur.nom} {d.demandeur.prenom}".strip(),
                       d.departement.libelle_service if d.departement_id else '',
                       d.agence.nom_agence if d.agence_id else '', d.objet,
                       d.approuvee_le.date() if d.approuvee_le else None, float(d.montant_approuve or 0),
                       float(d.montant_paye or 0), float(d.solde or 0), d.devise, d.get_statut_financier_display()])
        for col, largeur in zip('ABCDEFGHIJKLM', (5, 18, 26, 24, 20, 16, 40, 13, 16, 14, 14, 8, 20)):
            ws.column_dimensions[col].width = largeur
        flux = BytesIO()
        wb.save(flux)
        r = HttpResponse(flux.getvalue(),
                         content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        r['Content-Disposition'] = 'attachment; filename="demandes-a-payer.xlsx"'
        return r


class ReglementViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    GET  /tresorerie/reglements/?demande=
    POST /tresorerie/reglements/                  multipart : demande, montant, date_paiement, mode, reference,
                                                   beneficiaire, justificatif (fichier)
    POST /tresorerie/reglements/{id}/annuler/     { motif }  (administrateurs des finances)
    """
    serializer_class = ReglementSerializer
    permission_classes = [EstTresorerie]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        qs = Reglement.objects.select_related('enregistre_par', 'annule_par', 'justificatif')
        if self.request.query_params.get('demande'):
            qs = qs.filter(demande_id=self.request.query_params['demande'])
        return qs.order_by('-date_paiement', '-id')

    def create(self, request):
        demande = get_object_or_404(Demande, pk=request.data.get('demande'))
        d = request.data
        r = services.enregistrer_reglement(demande, request.user, d.get('montant'), d.get('date_paiement'),
                                           d.get('mode') or 'virement', d.get('reference', ''),
                                           d.get('beneficiaire', ''), request.FILES.get('justificatif'),
                                           infos_requete(request))
        return Response(ReglementSerializer(r).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def annuler(self, request, pk=None):
        r = services.annuler_reglement(self.get_object(), request.user, request.data.get('motif', ''),
                                       infos_requete(request))
        return Response(ReglementSerializer(r).data)


class ReversementViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    GET  /tresorerie/reversements/?etat=a_percevoir|percu|abandonne&demande=&search=
    POST /tresorerie/reversements/{id}/percevoir/   multipart : percu_le, mode, reference, justificatif
    POST /tresorerie/reversements/{id}/abandonner/  { motif }  (administrateurs des finances)
    """
    serializer_class = ReversementSerializer
    permission_classes = [EstTresorerie]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filter_backends = [filters.SearchFilter]
    search_fields = ['demande__reference', 'demande__objet', 'demande__demandeur__nom', 'demande__demandeur__prenom']

    def get_queryset(self):
        p = self.request.query_params
        qs = Reversement.objects.select_related('demande__type_demande', 'demande__demandeur', 'traite_par',
                                                'justificatif')
        if p.get('etat'):
            qs = qs.filter(etat=p['etat'])
        if p.get('demande'):
            qs = qs.filter(demande_id=p['demande'])
        return qs.order_by('cree_le', 'id')

    @action(detail=True, methods=['post'])
    def percevoir(self, request, pk=None):
        d = request.data
        r = services.percevoir(self.get_object(), request.user, d.get('percu_le'), d.get('mode') or 'virement',
                               d.get('reference', ''), request.FILES.get('justificatif'), infos_requete(request))
        return Response(ReversementSerializer(r).data)

    @action(detail=True, methods=['post'])
    def abandonner(self, request, pk=None):
        r = services.abandonner(self.get_object(), request.user, request.data.get('motif', ''), infos_requete(request))
        return Response(ReversementSerializer(r).data)
