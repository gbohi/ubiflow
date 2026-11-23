"""API du lot « Organisation » : responsabilités, N+1, véhicule, situation à une date, import Excel."""
from datetime import timedelta

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from . import organisation as org
from .import_collaborateurs import ImportInvalide, generer_modele, importer
from .models import (
    AffectationHierarchique, AffectationResponsabilite, ImportCollaborateurs, Responsabilite, Service,
    SituationVehicule, User,
)
from .organisation_serializers import (
    AffectationHierarchiqueSerializer, AffectationResponsabiliteSerializer, ImportCollaborateursSerializer,
    ReaffectationSerializer, ResponsabiliteSerializer, SituationVehiculeSerializer,
)
from .permissions import (
    IsAdminRole, IsAuthenticated, ReadAuthenticatedWriteAdmin, ReadGestionnaireWriteAdmin, is_gestionnaire,
)
from .views import BaseViewSet


def _date_param(request, nom='date'):
    valeur = request.query_params.get(nom)
    try:
        return org.normaliser_date(valeur)
    except ValueError:
        raise ValidationError({nom: 'Date invalide (format AAAA-MM-JJ).'})


def _filtrer_en_cours(request, qs):
    """?en_cours=AAAA-MM-JJ (ou ?en_cours=1 pour aujourd'hui) : lignes actives à cette date."""
    valeur = request.query_params.get('en_cours')
    if not valeur:
        return qs
    d = org.date_du_jour() if valeur in ('1', 'true') else _date_param(request, 'en_cours')
    return qs.filter(org.filtre_en_cours(d))


# ── Départements : arbre ───────────────────────────────────────

class ArbreDepartementsView(APIView):
    """GET /departements/arbre/?date= : arbre des départements avec leur responsable."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        d = _date_param(request)
        departements = list(Service.objects.order_by('libelle_service'))
        enfants = {}
        for dep in departements:
            enfants.setdefault(dep.parent_id, []).append(dep)

        def noeud(dep):
            resp = org.responsable_departement(dep, d)
            return {'id': dep.pk, 'libelle': dep.libelle_service, 'code': dep.code,
                    'responsable': org._personne(resp),
                    'enfants': [noeud(e) for e in enfants.get(dep.pk, [])]}

        return Response([noeud(dep) for dep in enfants.get(None, [])])


# ── Responsabilités ────────────────────────────────────────────

class ResponsabiliteViewSet(BaseViewSet):
    """Référentiel des responsabilités. Les responsabilités système ne sont pas supprimables."""
    queryset = Responsabilite.objects.all().order_by('libelle')
    serializer_class = ResponsabiliteSerializer
    permission_classes = [ReadAuthenticatedWriteAdmin]
    proteger_references = True
    champ_libelle = 'libelle'
    filterset_fields = ['portee', 'actif', 'systeme']
    search_fields = ['libelle', 'code']
    ordering_fields = ['id', 'libelle', 'code']

    def verifier_suppression(self, instance):
        if instance.systeme:
            raise ValidationError(f"« {instance.libelle} » est une responsabilité système : "
                                  "elle ne peut pas être supprimée.")
        super().verifier_suppression(instance)

    @action(detail=True, methods=['get'])
    def titulaires(self, request, pk=None):
        """GET /responsabilites/{id}/titulaires/?date=&departement=&agence="""
        resp = self.get_object()
        d = _date_param(request)
        dept = request.query_params.get('departement')
        agence = request.query_params.get('agence')
        users = org.titulaires(resp, d, departement=dept and int(dept), agence=agence and int(agence))
        return Response({'date': d.isoformat(), 'titulaires': [org._personne(u) for u in users]})


class AffectationResponsabiliteViewSet(BaseViewSet):
    queryset = (AffectationResponsabilite.objects
                .select_related('user', 'responsabilite', 'departement', 'agence').order_by('-date_debut', 'id'))
    serializer_class = AffectationResponsabiliteSerializer
    permission_classes = [ReadGestionnaireWriteAdmin]
    filterset_fields = ['user', 'responsabilite', 'departement', 'agence']
    search_fields = ['user__nom', 'user__prenom', 'user__username', 'responsabilite__libelle']
    ordering_fields = ['date_debut', 'date_fin']

    def get_queryset(self):
        return _filtrer_en_cours(self.request, super().get_queryset())


# ── Hiérarchie ─────────────────────────────────────────────────

class AffectationHierarchiqueViewSet(BaseViewSet):
    queryset = (AffectationHierarchique.objects.select_related('user', 'responsable')
                .order_by('-date_debut', 'id'))
    serializer_class = AffectationHierarchiqueSerializer
    permission_classes = [ReadGestionnaireWriteAdmin]
    filterset_fields = ['user', 'responsable', 'mode', 'exceptionnelle']
    ordering_fields = ['date_debut', 'date_fin']

    def get_queryset(self):
        return _filtrer_en_cours(self.request, super().get_queryset())

    def perform_update(self, serializer):
        if serializer.validated_data.get('user', serializer.instance.user) != serializer.instance.user:
            raise PermissionDenied("Le collaborateur d'une affectation existante ne peut pas être changé.")
        super().perform_update(serializer)


class SituationVehiculeViewSet(BaseViewSet):
    queryset = SituationVehicule.objects.select_related('user').order_by('-date_debut', 'id')
    serializer_class = SituationVehiculeSerializer
    permission_classes = [ReadGestionnaireWriteAdmin]
    filterset_fields = ['user', 'possede_vehicule']

    def get_queryset(self):
        return _filtrer_en_cours(self.request, super().get_queryset())


# ── Situation d'un collaborateur ───────────────────────────────

class OrganisationCollaborateurView(APIView):
    """
    GET /collaborateurs/{id}/organisation/?date=  (gestionnaires, administrateurs)
    GET /collaborateurs/moi/organisation/?date=   (tout utilisateur connecté)
    Département, agence, poste, catégorie, véhicule, N+1, N+2 et responsabilités à la date.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        if pk is None:
            user = request.user
        else:
            if not is_gestionnaire(request.user) and int(pk) != request.user.pk:
                raise PermissionDenied("Accès réservé aux gestionnaires.")
            user = get_object_or_404(User, pk=pk)
        return Response(org.organisation_de(user, _date_param(request)))


class ReaffectationN1View(APIView):
    """
    POST /collaborateurs/{id}/reaffecter-n-plus-1/  (administrateurs)
    { mode, responsable, date_effet, motif } : ferme l'affectation en cours la
    veille de la date d'effet et ouvre une affectation exceptionnelle motivée.
    """
    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        s = ReaffectationSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        donnees = s.validated_data
        d = donnees['date_effet']
        with transaction.atomic():
            en_cours = org.affectation_hierarchique_en_cours(user, d)
            if en_cours is not None:
                if en_cours.date_debut >= d:
                    raise ValidationError({'date_effet': "Une affectation commence déjà à cette date : "
                                                         "choisissez une date d'effet postérieure."})
                en_cours.date_fin = d - timedelta(days=1)
                en_cours.user_updated = request.user
                en_cours.save(update_fields=['date_fin', 'user_updated', 'updated_at'])
            suivante = (AffectationHierarchique.objects.filter(user=user, date_debut__gt=d)
                        .order_by('date_debut').first())
            nouvelle = AffectationHierarchiqueSerializer(data={
                'user': user.pk, 'mode': donnees['mode'],
                'responsable': donnees['responsable'].pk if donnees.get('responsable') else None,
                'date_debut': d, 'date_fin': suivante.date_debut - timedelta(days=1) if suivante else None,
                'exceptionnelle': True, 'motif': donnees['motif'],
            })
            nouvelle.is_valid(raise_exception=True)
            nouvelle.save(user_created=request.user, user_updated=request.user)
        return Response({'affectation': nouvelle.data,
                         'n_plus_1': org.organisation_de(user, d)['n_plus_1']},
                        status=status.HTTP_201_CREATED)


# ── Import Excel ───────────────────────────────────────────────

class ImportCollaborateursViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    GET  /imports-collaborateurs/          historique des imports
    GET  /imports-collaborateurs/modele/   modèle de fichier Excel
    POST /imports-collaborateurs/          multipart : fichier, date_effet, simulation (true/false)
    """
    queryset = ImportCollaborateurs.objects.select_related('auteur').all()
    serializer_class = ImportCollaborateursSerializer
    permission_classes = [IsAdminRole]
    parser_classes = [MultiPartParser, FormParser]

    TAILLE_MAX = 5 * 1024 * 1024

    def create(self, request):
        fichier = request.FILES.get('fichier')
        if not fichier:
            raise ValidationError({'fichier': 'Choisissez un fichier Excel (.xlsx).'})
        if not fichier.name.lower().endswith('.xlsx'):
            raise ValidationError({'fichier': 'Format attendu : Excel .xlsx.'})
        if fichier.size > self.TAILLE_MAX:
            raise ValidationError({'fichier': 'Le fichier ne doit pas dépasser 5 Mo.'})
        try:
            date_effet = org.normaliser_date(request.data.get('date_effet'))
        except ValueError:
            raise ValidationError({'date_effet': 'Date invalide (format AAAA-MM-JJ).'})
        simulation = str(request.data.get('simulation', 'false')).lower() in ('1', 'true', 'oui')
        try:
            resultat = importer(fichier, fichier.name, date_effet, request.user, simulation)
        except ImportInvalide as e:
            raise ValidationError({'fichier': str(e)})
        return Response(self.get_serializer(resultat).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def modele(self, request):
        reponse = HttpResponse(
            generer_modele(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        reponse['Content-Disposition'] = 'attachment; filename="modele-import-collaborateurs.xlsx"'
        return reponse
