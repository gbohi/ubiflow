from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsAdminWorkflow, IsAuthenticated, is_admin_workflow
from audit.services import infos_requete, journaliser
from demandes.models import TypeDemande
from notifications.services import notifier

from . import conditions, moteur, parametrage
from .erreurs import ErreurMetier, Interdit
from .models import Delegation, Etape, Tache, VersionWorkflow
from .serializers import DelegationSerializer, EtapeSerializer, TacheSerializer, VersionWorkflowSerializer


# ── Paramétrage des circuits ───────────────────────────────────

class VersionWorkflowViewSet(viewsets.ModelViewSet):
    """
    GET    /versions-workflow/?type_demande=      versions (publiée, brouillon, archivées)
    POST   /versions-workflow/                    { type_demande, source }  brouillon (copie de source)
    PATCH  /versions-workflow/{id}/               brouillon seulement
    DELETE /versions-workflow/{id}/               brouillon seulement
    POST   /versions-workflow/{id}/publier/       { commentaire }
    GET    /versions-workflow/{id}/controle/      erreurs bloquant la publication
    POST   /versions-workflow/{id}/simuler/       { demandeur, montant, donnees }
    POST   /versions-workflow/{id}/reordonner/    { etapes: [id, …] }
    """
    serializer_class = VersionWorkflowSerializer
    pagination_class = None
    filterset_fields = ['type_demande', 'etat']

    def get_permissions(self):
        return [IsAuthenticated()] if self.action in ('list', 'retrieve') else [IsAdminWorkflow()]

    def get_queryset(self):
        return (VersionWorkflow.objects.select_related('type_demande', 'publiee_par')
                .prefetch_related('etapes__regles__responsabilite', 'etapes__regles__personne'))

    def create(self, request):
        type_demande = get_object_or_404(TypeDemande, pk=request.data.get('type_demande'))
        source = None
        if request.data.get('source'):
            source = get_object_or_404(VersionWorkflow, pk=request.data['source'], type_demande=type_demande)
        version = parametrage.nouvelle_version(type_demande, request.user, source)
        journaliser(request.user, 'workflow.version_creee', version, request=request,
                    motif=f"Copie de la v{source.numero}" if source else '')
        return Response(self.get_serializer(version).data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        if not instance.modifiable:
            raise ErreurMetier("Seul un brouillon peut être supprimé.")
        journaliser(self.request.user, 'workflow.brouillon_supprime', instance, request=self.request)
        instance.delete()

    @action(detail=True, methods=['post'])
    def publier(self, request, pk=None):
        version = parametrage.publier(self.get_object(), request.user, request.data.get('commentaire', ''))
        journaliser(request.user, 'workflow.publication', version, request=request,
                    apres=VersionWorkflowSerializer(version).data, motif=version.commentaire_version)
        return Response(self.get_serializer(version).data)

    @action(detail=True, methods=['get'])
    def controle(self, request, pk=None):
        return Response({'erreurs': parametrage.controler(self.get_object())})

    @action(detail=True, methods=['post'])
    def simuler(self, request, pk=None):
        version = self.get_object()
        demandeur = get_object_or_404(get_user_model(), pk=request.data.get('demandeur'))
        try:
            resultat = parametrage.simuler(version, demandeur, request.data.get('montant'),
                                           request.data.get('donnees') or {})
        except (ValueError, ArithmeticError):
            raise ErreurMetier({'montant': 'Montant invalide.'})
        return Response(resultat)

    @action(detail=True, methods=['post'])
    def reordonner(self, request, pk=None):
        version = self.get_object()
        parametrage.reordonner(version, [int(x) for x in request.data.get('etapes', [])])
        return Response(self.get_serializer(version).data)


class EtapeViewSet(viewsets.ModelViewSet):
    """Étapes d'une version brouillon (avec leurs règles de désignation)."""
    queryset = Etape.objects.select_related('version__type_demande').prefetch_related('regles')
    serializer_class = EtapeSerializer
    permission_classes = [IsAdminWorkflow]
    pagination_class = None
    filterset_fields = ['version']

    def perform_create(self, serializer):
        version = serializer.validated_data['version']
        if 'ordre' not in self.request.data:
            serializer.validated_data['ordre'] = version.etapes.count() + 1
        serializer.save()

    def perform_destroy(self, instance):
        if not instance.version.modifiable:
            raise ErreurMetier("Version publiée : dupliquez-la pour la modifier.")
        version = instance.version
        instance.delete()
        for ordre, e in enumerate(version.etapes.order_by('ordre', 'id'), start=1):
            Etape.objects.filter(pk=e.pk).update(ordre=ordre)


class ChampsConditionView(APIView):
    """GET /champs-condition/?type_demande= : champs et opérateurs de l'éditeur de conditions."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        type_demande = TypeDemande.objects.filter(pk=request.query_params.get('type_demande')).first()
        return Response({'champs': conditions.champs_disponibles(type_demande),
                         'operateurs': [{'code': k, 'libelle': v} for k, v in conditions.OPERATEURS.items()]})


# ── Validations ────────────────────────────────────────────────

class TacheViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    GET  /taches/?etat=en_attente|faite&type_demande=&du=&au=   mes validations (et celles reçues par délégation)
    POST /taches/{id}/approuver/               { motif, modifications }
    POST /taches/{id}/rejeter/                 { motif }
    POST /taches/{id}/retourner/               { motif }
    POST /taches/{id}/reaffecter/              { valideur, motif }  (administrateurs des workflows)
    """
    serializer_class = TacheSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        etat = self.request.query_params.get('etat', 'en_attente')
        base = Tache.objects.select_related('etape_instance__etape', 'etape_instance__instance__demande__type_demande',
                                            'etape_instance__instance__demande__demandeur', 'valideur')
        if etat == 'faite':
            qs = base.filter(traitee_par=user, etat='faite').order_by('-traitee_le')
        else:
            qs = base.filter(etat='en_attente').filter(moteur.filtre_taches_de(user)).order_by('ouverte_le', 'id')
        type_demande = self.request.query_params.get('type_demande')
        if type_demande:
            qs = qs.filter(etape_instance__instance__demande__type_demande_id=type_demande)
        from demandes.views import filtrer_par_dates
        return filtrer_par_dates(qs, self.request.query_params, 'etape_instance__instance__demande__soumise_le')

    def _tache(self, pk):
        return get_object_or_404(Tache.objects.select_related('etape_instance__instance__demande'), pk=pk)

    def _agir(self, request, pk, quoi):
        tache = self._tache(pk)
        with transaction.atomic():
            moteur.agir(tache, request.user, quoi, request.data.get('motif', ''),
                        request.data.get('modifications') or None, infos_requete(request))
        demande = tache.etape_instance.instance.demande
        demande.refresh_from_db()
        return Response({'demande': demande.pk, 'statut': demande.statut,
                         'statut_libelle': demande.get_statut_display()})

    @action(detail=True, methods=['post'])
    def approuver(self, request, pk=None):
        return self._agir(request, pk, 'approuver')

    @action(detail=True, methods=['post'])
    def rejeter(self, request, pk=None):
        return self._agir(request, pk, 'rejeter')

    @action(detail=True, methods=['post'])
    def retourner(self, request, pk=None):
        return self._agir(request, pk, 'retourner')

    @action(detail=True, methods=['post'], permission_classes=[IsAdminWorkflow])
    def reaffecter(self, request, pk=None):
        tache = self._tache(pk)
        nouveau = get_object_or_404(get_user_model(), pk=request.data.get('valideur'))
        ancien = tache.valideur
        with transaction.atomic():
            moteur.reaffecter_tache(tache, nouveau, request.user, request.data.get('motif', ''),
                                    infos_requete(request))
        journaliser(request.user, 'workflow.reaffectation', tache.etape_instance.instance.demande, request=request,
                    avant={'valideur': ancien.username}, apres={'valideur': nouveau.username},
                    motif=request.data.get('motif', ''))
        return Response(TacheSerializer(tache, context={'request': request}).data)


# ── Délégations ────────────────────────────────────────────────

class DelegationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                        viewsets.GenericViewSet):
    """
    GET  /delegations/?sens=donnees|recues|toutes   (toutes : administrateurs des workflows)
    POST /delegations/        { delegataire, date_debut, date_fin, types_demande, responsabilites, motif, delegant? }
    POST /delegations/{id}/revoquer/
    """
    serializer_class = DelegationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        qs = Delegation.objects.select_related('delegant', 'delegataire').prefetch_related(
            'types_demande', 'responsabilites')
        sens = self.request.query_params.get('sens')
        if sens == 'toutes' and is_admin_workflow(user):
            return qs
        if sens == 'donnees':
            return qs.filter(delegant=user)
        if sens == 'recues':
            return qs.filter(delegataire=user)
        return qs.filter(delegant=user) | qs.filter(delegataire=user)

    def perform_create(self, serializer):
        user = self.request.user
        delegant = serializer.validated_data['delegant']
        if delegant.pk != user.pk:
            if not is_admin_workflow(user):
                raise Interdit("Vous ne pouvez déléguer que vos propres validations.")
            if not (serializer.validated_data.get('motif') or '').strip():
                raise ErreurMetier({'motif': "Le motif est obligatoire pour une délégation créée pour autrui."})
        delegation = serializer.save(cree_par=user)
        journaliser(user, 'delegation.creation', delegation, request=self.request,
                    apres=DelegationSerializer(delegation).data, pour_compte_de=delegant if delegant != user else None)
        notifier([delegation.delegataire], 'delegation_recue', 'Délégation de validations',
                 f"{moteur.nom(delegant)} vous délègue ses validations du {delegation.date_debut:%d/%m/%Y} "
                 f"au {delegation.date_fin:%d/%m/%Y}.")

    @action(detail=True, methods=['post'])
    def revoquer(self, request, pk=None):
        delegation = self.get_object()
        if request.user.pk != delegation.delegant_id and not is_admin_workflow(request.user):
            raise Interdit("Seul le délégant peut révoquer sa délégation.")
        if delegation.revoquee:
            raise ErreurMetier("Délégation déjà révoquée.")
        delegation.revoquee, delegation.revoquee_le = True, timezone.now()
        delegation.save()
        journaliser(request.user, 'delegation.revocation', delegation, request=request)
        notifier([delegation.delegataire], 'delegation_revoquee', 'Délégation révoquée',
                 f"La délégation de {moteur.nom(delegation.delegant)} a été révoquée.")
        return Response(self.get_serializer(delegation).data)
