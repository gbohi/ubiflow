from django.db.models import Prefetch
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from api.permissions import IsAuthenticated, ReadAuthenticatedWriteAdminWorkflow, voit_toutes_les_demandes
from audit.services import infos_requete, journaliser
from workflow import moteur
from workflow.erreurs import ErreurMetier, Interdit
from workflow.models import EtapeInstance, InstanceWorkflow, Tache

from . import services
from .models import ChampType, Demande, Document, ExigencePiece, StatutDemande, TypeDemande, TypePiece
from .serializers import (
    ActionSerializer, ChampTypeSerializer, CommentaireSerializer, DemandeDetailSerializer, DemandeEcritureSerializer,
    DemandeListeSerializer, DocumentSerializer, ExigencePieceSerializer, TypeDemandeSerializer, TypePieceSerializer,
    VersionContenuSerializer,
)


def filtrer_par_dates(qs, params, champ, repli=None):
    """
    Filtre « du / au » (dates incluses, AAAA-MM-JJ) sur la date de la demande :
    `champ`, ou `repli` quand il est vide (brouillon jamais soumis : date de création).
    """
    from datetime import date
    from django.db.models.functions import Coalesce, TruncDate
    bornes = {}
    for cle in ('du', 'au'):
        if params.get(cle):
            try:
                bornes[cle] = date.fromisoformat(params[cle][:10])
            except ValueError:
                raise ErreurMetier({cle: 'Date invalide (AAAA-MM-JJ).'})
    if not bornes:
        return qs
    expression = Coalesce(champ, repli) if repli else champ
    qs = qs.annotate(_date_demande=TruncDate(expression))
    if 'du' in bornes:
        qs = qs.filter(_date_demande__gte=bornes['du'])
    if 'au' in bornes:
        qs = qs.filter(_date_demande__lte=bornes['au'])
    return qs


class _JournalMixin:
    """Journalise les créations, modifications et suppressions du paramétrage."""

    def perform_create(self, serializer):
        obj = serializer.save()
        journaliser(self.request.user, 'parametrage.creation', obj, apres=serializer.data, request=self.request)

    def perform_update(self, serializer):
        avant = type(serializer)(serializer.instance).data
        obj = serializer.save()
        journaliser(self.request.user, 'parametrage.modification', obj, avant=avant, apres=serializer.data,
                    request=self.request)

    def perform_destroy(self, instance):
        from django.db.models.deletion import ProtectedError
        libelle, pk, label = str(instance), instance.pk, instance._meta.label
        try:
            instance.delete()
        except ProtectedError:
            raise ErreurMetier("Élément utilisé : il ne peut pas être supprimé (désactivez-le).")
        journaliser(self.request.user, 'parametrage.suppression', objet_type=label, objet_id=pk, libelle=libelle,
                    request=self.request)


# ── Paramétrage des types ──────────────────────────────────────

class TypeDemandeViewSet(_JournalMixin, viewsets.ModelViewSet):
    """Lecture : tous (types actifs) ; écriture : administrateurs des workflows."""
    serializer_class = TypeDemandeSerializer
    permission_classes = [ReadAuthenticatedWriteAdminWorkflow]
    pagination_class = None

    def get_queryset(self):
        qs = TypeDemande.objects.prefetch_related('champs', 'exigences__type_piece')
        if self.request.query_params.get('tous') != '1':
            qs = qs.filter(actif=True)
        return qs


class ChampTypeViewSet(_JournalMixin, viewsets.ModelViewSet):
    queryset = ChampType.objects.all()
    serializer_class = ChampTypeSerializer
    permission_classes = [ReadAuthenticatedWriteAdminWorkflow]
    pagination_class = None
    filterset_fields = ['type_demande']


class ExigencePieceViewSet(_JournalMixin, viewsets.ModelViewSet):
    queryset = ExigencePiece.objects.select_related('type_piece')
    serializer_class = ExigencePieceSerializer
    permission_classes = [ReadAuthenticatedWriteAdminWorkflow]
    pagination_class = None
    filterset_fields = ['type_demande']


class TypePieceViewSet(_JournalMixin, viewsets.ModelViewSet):
    queryset = TypePiece.objects.all()
    serializer_class = TypePieceSerializer
    permission_classes = [ReadAuthenticatedWriteAdminWorkflow]
    pagination_class = None


# ── Demandes ───────────────────────────────────────────────────

class DemandeViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    GET    /demandes/?vue=mes|toutes&statut=&type_demande=&du=AAAA-MM-JJ&au=AAAA-MM-JJ&search=
    POST   /demandes/                       brouillon
    PATCH  /demandes/{id}/                  brouillon / correction
    DELETE /demandes/{id}/                  brouillon jamais soumis
    POST   /demandes/{id}/soumettre/        soumission ou resoumission { motif }
    POST   /demandes/{id}/annuler/          { motif }
    POST   /demandes/{id}/dupliquer/
    GET    /demandes/{id}/historique/       actions du workflow
    GET    /demandes/{id}/versions/         versions du contenu
    POST   /demandes/{id}/commentaires/     { texte }
    POST   /demandes/{id}/documents/        multipart : fichier, type_piece, remplace
    POST   /demandes/{id}/documents/{doc}/retirer/   { motif }
    GET    /demandes/{id}/documents/{doc}/fichier/
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['reference', 'objet', 'demandeur__nom', 'demandeur__prenom', 'demandeur__username']
    ordering_fields = ['created_at', 'soumise_le', 'reference', 'montant_demande', 'updated_at']
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        user = self.request.user
        vue = self.request.query_params.get('vue', 'mes')
        if vue == 'toutes' and voit_toutes_les_demandes(user):
            qs = Demande.objects.all()
        elif vue == 'visibles':
            qs = services.demandes_visibles(user)
        else:
            qs = Demande.objects.filter(demandeur=user)
        p = self.request.query_params
        if p.get('statut'):
            qs = qs.filter(statut__in=p['statut'].split(','))
        if p.get('type_demande'):
            qs = qs.filter(type_demande_id=p['type_demande'])
        qs = filtrer_par_dates(qs, p, 'soumise_le', 'created_at')
        etapes = EtapeInstance.objects.select_related('etape').prefetch_related(
            Prefetch('taches', queryset=Tache.objects.select_related('valideur')))
        return qs.select_related('type_demande', 'demandeur').prefetch_related(
            Prefetch('instances', queryset=InstanceWorkflow.objects.prefetch_related(
                Prefetch('etapes', queryset=etapes)))).order_by('-updated_at', '-id')

    def get_serializer_class(self):
        return DemandeListeSerializer if self.action == 'list' else DemandeDetailSerializer

    def get_object(self):
        demande = get_object_or_404(Demande.objects.select_related(
            'type_demande', 'demandeur', 'cree_par', 'n_plus_1', 'departement', 'agence', 'categorie',
            'version_courante', 'version_workflow', 'origine_copie'), pk=self.kwargs['pk'])
        if not services.peut_voir(demande, self.request.user):
            raise Interdit("Vous n'avez pas accès à cette demande.")
        return demande

    def _detail(self, demande, code=status.HTTP_200_OK):
        demande.refresh_from_db()
        return Response(DemandeDetailSerializer(demande, context={'request': self.request}).data, status=code)

    def create(self, request):
        s = DemandeEcritureSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        if 'type_demande' not in d:
            raise ErreurMetier({'type_demande': 'Choisissez le type de demande.'})
        demande = services.creer_brouillon(request.user, d['type_demande'], d.get('objet', ''),
                                           d.get('montant_demande'), d.get('devise', ''), d.get('donnees'),
                                           infos_requete(request), demande_parent=d.get('demande_parent'))
        return self._detail(demande, status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        demande = self.get_object()
        s = DemandeEcritureSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        services.modifier(demande, request.user, champs=set(s.validated_data), **{
            k: v for k, v in s.validated_data.items() if k not in ('type_demande', 'demande_parent')})
        return self._detail(demande)

    def destroy(self, request, pk=None):
        services.supprimer_brouillon(self.get_object(), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def soumettre(self, request, pk=None):
        demande = self.get_object()
        try:
            demande = services.soumettre(demande, request.user, request.data.get('motif', ''), infos_requete(request))
        except ErreurMetier as e:
            if isinstance(e.detail, dict) and 'circuit' in e.detail:
                services.alerter_blocage(demande, [str(x) for x in e.detail['circuit']])
            raise
        return self._detail(demande)

    @action(detail=True, methods=['post'])
    def annuler(self, request, pk=None):
        demande = services.annuler(self.get_object(), request.user, request.data.get('motif', ''),
                                   infos_requete(request))
        return self._detail(demande)

    @action(detail=True, methods=['post'])
    def dupliquer(self, request, pk=None):
        copie = services.dupliquer(self.get_object(), request.user, infos_requete(request))
        return self._detail(copie, status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """Fiche PDF de présentation de la demande."""
        from django.http import HttpResponse
        from .pdf import generer
        demande = self.get_object()
        r = HttpResponse(generer(demande, request.user), content_type='application/pdf')
        r['Content-Disposition'] = f'attachment; filename="{demande.reference or f"brouillon-{demande.pk}"}.pdf"'
        return r

    @action(detail=True, methods=['get'], url_path='ordre-mission')
    def ordre_mission(self, request, pk=None):
        """Ordre de mission au format de la société (mission approuvée)."""
        from django.http import HttpResponse
        from .documents_mission import ordre_de_mission
        demande = self.get_object()
        r = HttpResponse(ordre_de_mission(demande, request.user), content_type='application/pdf')
        r['Content-Disposition'] = f'attachment; filename="ordre-de-mission-{demande.reference}.pdf"'
        return r

    @action(detail=True, methods=['get'], url_path='note-frais')
    def note_frais(self, request, pk=None):
        """Note de frais de mission (formulaire de la société)."""
        from django.http import HttpResponse
        from .documents_mission import note_de_frais
        demande = self.get_object()
        r = HttpResponse(note_de_frais(demande, request.user), content_type='application/pdf')
        r['Content-Disposition'] = f'attachment; filename="note-de-frais-{demande.reference or demande.pk}.pdf"'
        return r

    @action(detail=True, methods=['get'])
    def historique(self, request, pk=None):
        actions = self.get_object().actions.select_related(
            'auteur_reel', 'pour_compte_de', 'etape_instance__etape', 'instance')
        return Response(ActionSerializer(actions, many=True).data)

    @action(detail=True, methods=['get'])
    def versions(self, request, pk=None):
        return Response(VersionContenuSerializer(self.get_object().versions.all(), many=True).data)

    @action(detail=True, methods=['post'])
    def commentaires(self, request, pk=None):
        c = services.commenter(self.get_object(), request.user, request.data.get('texte', ''), infos_requete(request))
        return Response(CommentaireSerializer(c).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='documents')
    def ajouter_document(self, request, pk=None):
        demande = self.get_object()
        fichier = request.FILES.get('fichier')
        if not fichier:
            raise ErreurMetier({'fichier': 'Choisissez un fichier.'})
        type_piece = TypePiece.objects.filter(pk=request.data.get('type_piece')).first() \
            if request.data.get('type_piece') else None
        remplace = demande.documents.filter(pk=request.data.get('remplace')).first() \
            if request.data.get('remplace') else None
        doc = services.ajouter_document(demande, request.user, fichier, type_piece, remplace, infos_requete(request))
        return Response(DocumentSerializer(doc).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path=r'documents/(?P<doc>\d+)/retirer')
    def retirer_document(self, request, pk=None, doc=None):
        demande = self.get_object()
        document = get_object_or_404(Document, pk=doc, demande=demande)
        resultat = services.retirer_document(document, request.user, request.data.get('motif', ''),
                                             infos_requete(request))
        if resultat is not None:
            journaliser(request.user, 'document.retrait', document, motif=request.data.get('motif', ''),
                        request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'], url_path=r'documents/(?P<doc>\d+)/fichier')
    def fichier(self, request, pk=None, doc=None):
        demande = self.get_object()
        document = get_object_or_404(Document, pk=doc, demande=demande)
        return FileResponse(document.fichier.open('rb'), as_attachment=True, filename=document.nom_origine)

    @action(detail=False, methods=['get'], url_path='parents-possibles')
    def parents_possibles(self, request):
        """Demandes auxquelles rattacher une nouvelle demande du type donné (?type_demande=)."""
        type_demande = get_object_or_404(TypeDemande, pk=request.query_params.get('type_demande'))
        qs = services.parents_possibles(type_demande, request.user)
        return Response([{'id': d.pk, 'reference': d.reference, 'objet': d.objet, 'type_libelle': d.type_demande.libelle,
                          'type_code': d.type_demande.code, 'statut': d.statut, 'statut_libelle': d.get_statut_display(),
                          'montant_approuve': d.montant_approuve, 'montant_paye': d.montant_paye, 'devise': d.devise}
                         for d in qs[:200]])

    @action(detail=False, methods=['get'])
    def compteurs(self, request):
        """Nombre de mes demandes par statut et de validations en attente (tableau de bord)."""
        from django.db.models import Count
        mes = dict(Demande.objects.filter(demandeur=request.user).values_list('statut').annotate(n=Count('id')))
        a_valider = Tache.objects.filter(etat='en_attente').filter(moteur.filtre_taches_de(request.user)).count()
        return Response({'mes_demandes': {s: mes.get(s, 0) for s in StatutDemande.values}, 'a_valider': a_valider})
