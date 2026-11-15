"""
Suppléments (desserts ; plus tard boissons, entrées…) : un supplément
accompagne le plat principal du jour.

Règles (familles réglées dans Paramètres › Suppléments, FamilleSupplement) :
  - un supplément ne se commande JAMAIS sans plat principal : c'est une
    commande rattachée (Commande.commande_principale) au plat principal du
    même menu, du même employé ;
  - max_par_jour suppléments de la famille par jour (1 pour le dessert) ;
  - choisi parmi les plats de la famille présents au menu ;
  - famille « inclus » : gratuit pour l'employé (mode_paiement « offert » :
    hors facture de l'employé), payé au prestataire à son tarif du type de
    plat (relevé, clôture : tarif exigé, 0 F possible) ; famille payante :
    même mode de paiement que le plat principal, au tarif de la catégorie
    de salarié ;
  - équipes « repas offert » : proposé seulement si famille.repas_offert ;
  - modifiable (changer, ajouter, retirer) jusqu'à la date limite de commande ;
    annuler le plat principal annule ses suppléments (signal) ; retirer le
    repas au comptoir retire aussi les suppléments (même menu) ;
  - un supplément ne compte pas comme un repas (statistiques, jeux, défis,
    « un seul repas par jour ») : filtre PRINCIPALES.

API (préfixe /api/api/)
  GET  supplements/familles/                     familles (tout utilisateur connecté)
  POST supplements/familles/  PUT/DELETE supplements/familles/<id>/   (administrateurs)
  GET  commandes/<id>/supplement/                 suppléments proposés au menu de ce repas (choisi ou non)
  POST commandes/<id>/supplement/  { plat_id }    ajoute ou remplace le supplément de sa famille
  DELETE commandes/<id>/supplement/?famille=<id>  retire le supplément (« Sans dessert »)
"""
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Commande, FamilleSupplement, MenuPlat, Plat, TypePlat
from .permissions import is_admin

# Commandes qui comptent comme un repas (plats principaux)
PRINCIPALES = Q(commande_principale__isnull=True)
ACTIVES = ('en_attente', 'retiree')


def famille_du_plat(plat):
    """Famille de supplément du plat (active), sinon None (plat principal)."""
    tp = getattr(plat, 'type_plat', None)
    f = getattr(tp, 'famille_supplement', None) if tp is not None else None
    return f if f is not None and f.actif else None


def est_supplement(plat):
    tp = getattr(plat, 'type_plat', None)
    return bool(tp is not None and tp.famille_supplement_id)


def verifier_plat_principal(plat):
    if est_supplement(plat):
        f = plat.type_plat.famille_supplement
        raise ValidationError({'plat_id': f"Un {f.libelle.lower()} se commande avec un plat principal : "
                                          "choisissez d'abord votre plat."})


def _verifier_modifiable(principal):
    from .comptes_repas import mois_ouvert
    from .serializers import date_limite_commande, libelle_date_limite
    if principal.statut != 'en_attente':
        raise ValidationError("Le repas n'est plus en attente : son supplément ne peut plus être modifié.")
    if not mois_ouvert(principal.menu.date_menu):
        raise ValidationError("Le mois est clôturé : sa facturation est figée.")
    limite = date_limite_commande(principal.menu.date_menu)
    if timezone.now() > limite:
        raise ValidationError(f"Les commandes pour ce menu étaient ouvertes jusqu'au {libelle_date_limite(limite)} : "
                              "le supplément ne peut plus être modifié.")


def _mode(principal, famille):
    if famille.inclus or principal.mode_paiement == 'offert':
        return 'offert'
    return principal.mode_paiement


def _annuler(sup, par, raison):
    from .comptes_repas import liberer_reglement
    sup.statut = 'annulee'
    sup.date_annulation = timezone.now()
    sup.annulee_par = par
    if par is not None:
        sup.user_updated = par
    sup.save(update_fields=['statut', 'date_annulation', 'annulee_par', 'user_updated', 'updated_at'])
    liberer_reglement(sup, par, raison=raison)


def ajouter(principal, plat, par, verifier_delai=True):
    """
    Ajoute (ou remplace) le supplément de la famille du plat pour ce repas.
    À appeler dans une transaction, principal verrouillé. Renvoie le supplément.
    """
    from .comptes_repas import debiter_commande
    plat = Plat.objects.select_related('type_plat__famille_supplement').get(pk=plat.pk)
    famille = famille_du_plat(plat)
    if famille is None:
        raise ValidationError({'plat_id': "Ce plat n'est pas un supplément (dessert…)."})
    if principal.commande_principale_id or est_supplement(principal.plat):
        raise ValidationError("Un supplément s'ajoute à un plat principal.")
    if verifier_delai:
        _verifier_modifiable(principal)
    elif principal.statut != 'en_attente':
        raise ValidationError("Le repas n'est plus en attente.")
    menu = principal.menu
    if not MenuPlat.objects.filter(menu=menu, plat=plat).exists():
        raise ValidationError({'plat_id': f"« {plat.nom} » n'est pas au menu de ce jour."})
    if menu.typeequipe_id and menu.typeequipe.repas_offert and not famille.repas_offert:
        raise ValidationError({'plat_id': f"Pas de {famille.libelle.lower()} pour les repas offerts."})
    # Même famille sur ce repas : remplacé
    for ancien in principal.supplements.filter(statut='en_attente', plat__type_plat__famille_supplement=famille) \
            .exclude(plat=plat):
        _annuler(ancien, par, raison=f"{famille.libelle} remplacé")
    deja = principal.supplements.filter(statut='en_attente', plat=plat).first()
    if deja is not None:
        return deja
    # Nombre par jour (tous repas du jour confondus)
    n = (Commande.objects.filter(user=principal.user, menu__date_menu=menu.date_menu, statut__in=ACTIVES,
                                 commande_principale__isnull=False,
                                 plat__type_plat__famille_supplement=famille).count())
    if n >= famille.max_par_jour:
        raise ValidationError({'plat_id': f"{famille.max_par_jour} {famille.libelle.lower()} par jour au plus."})
    mode = _mode(principal, famille)
    sup = Commande.objects.filter(user=principal.user, menu=menu, plat=plat).first()
    if sup is not None and sup.statut != 'annulee':
        raise ValidationError({'plat_id': f"« {plat.nom} » est déjà commandé pour ce jour."})
    try:
        with transaction.atomic():
            if sup is not None:      # repris (contrainte : un même plat une fois par menu)
                sup.statut, sup.date_annulation, sup.annulee_par, sup.motif_annulation = 'en_attente', None, None, ''
                sup.commande_principale, sup.mode_paiement = principal, 'retenue'
                sup.date_commande, sup.user_updated = timezone.now(), par
                sup.save()
            else:
                sup = Commande.objects.create(user=principal.user, menu=menu, plat=plat, commande_principale=principal,
                                              mode_paiement='retenue', user_created=par, user_updated=par)
            if mode == 'compte':
                debiter_commande(sup, par)
            if sup.mode_paiement != mode:
                sup.mode_paiement = mode
                sup.save(update_fields=['mode_paiement'])
    except IntegrityError:
        raise ValidationError({'plat_id': f"« {plat.nom} » est déjà commandé pour ce jour."})
    return sup


def retirer(principal, famille_id, par):
    """« Sans dessert » : annule le supplément de la famille (jusqu'à la date limite)."""
    _verifier_modifiable(principal)
    qs = principal.supplements.filter(statut='en_attente')
    if famille_id:
        qs = qs.filter(plat__type_plat__famille_supplement_id=famille_id)
    for sup in qs:
        _annuler(sup, par, raison='Supplément retiré')


def annuler_avec_principal(principal, par):
    """Plat principal annulé : ses suppléments en attente sont annulés (et recrédités si payés)."""
    for sup in principal.supplements.filter(statut='en_attente'):
        _annuler(sup, par, raison='Repas annulé')


def suivre_mode(principal, par):
    """Mode de paiement du plat changé : les suppléments payants le suivent."""
    from .comptes_repas import debiter_commande, liberer_reglement
    for sup in principal.supplements.filter(statut='en_attente').exclude(mode_paiement='offert'):
        if sup.mode_paiement == principal.mode_paiement:
            continue
        if principal.mode_paiement == 'compte':
            debiter_commande(sup, par)
        else:
            liberer_reglement(sup, par, raison='Passage en retenue sur salaire')
        sup.mode_paiement = principal.mode_paiement
        sup.save(update_fields=['mode_paiement'])


def supplements_json(commande, request=None):
    """Suppléments actifs d'un plat principal (sérialisation légère)."""
    from .serializers import PlatSerializer
    sups = getattr(commande, '_supplements_actifs', None)
    if sups is None:
        sups = list(commande.supplements.exclude(statut='annulee')
                    .select_related('plat__type_plat__famille_supplement'))
    out = []
    for s in sups:
        f = s.plat.type_plat.famille_supplement if s.plat.type_plat_id else None
        out.append({
            'id': s.id, 'statut': s.statut, 'mode_paiement': s.mode_paiement,
            'famille_id': f.id if f else None, 'famille': f.libelle if f else '',
            'inclus': s.mode_paiement == 'offert',
            'plat_detail': PlatSerializer(s.plat, context={'request': request}).data,
        })
    return out


# ── Familles (paramètres) ──────────────────────────────────────

class FamilleSupplementSerializer(serializers.ModelSerializer):
    nb_types = serializers.SerializerMethodField()
    nb_plats = serializers.SerializerMethodField()

    class Meta:
        model = FamilleSupplement
        fields = ['id', 'libelle', 'inclus', 'max_par_jour', 'repas_offert', 'actif', 'ordre', 'nb_types', 'nb_plats']

    def get_nb_types(self, obj):
        return obj.types_plat.count()

    def get_nb_plats(self, obj):
        return Plat.objects.filter(type_plat__famille_supplement=obj).count()

    def validate_max_par_jour(self, v):
        if v < 1 or v > 5:
            raise ValidationError("Entre 1 et 5 par jour.")
        return v


def _exiger_admin(user):
    if not is_admin(user):
        raise PermissionDenied("Réservé aux administrateurs.")


class FamillesSupplementView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(FamilleSupplementSerializer(FamilleSupplement.objects.all(), many=True).data)

    def post(self, request):
        _exiger_admin(request.user)
        s = FamilleSupplementSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data, status=status.HTTP_201_CREATED)


class FamilleSupplementDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk):
        f = FamilleSupplement.objects.filter(pk=pk).first()
        if f is None:
            raise NotFound("Famille introuvable.")
        return f

    def put(self, request, pk):
        _exiger_admin(request.user)
        s = FamilleSupplementSerializer(self._get(pk), data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)

    patch = put

    def delete(self, request, pk):
        _exiger_admin(request.user)
        f = self._get(pk)
        if f.types_plat.exists():
            raise ValidationError("Des types de plat utilisent cette famille : retirez-la d'abord des types de plat "
                                  "(ou désactivez la famille).")
        f.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Supplément d'une commande ──────────────────────────────────

class CommandeSupplementView(APIView):
    permission_classes = [IsAuthenticated]

    def _principal(self, request, pk):
        c = Commande.objects.select_for_update().select_related('menu__typeequipe', 'plat__type_plat', 'user') \
            .filter(pk=pk).first()
        if c is None:
            raise NotFound("Commande introuvable.")
        if c.user_id != request.user.id:
            raise PermissionDenied("Seul l'employé modifie le supplément de son repas.")
        return c

    def _reponse(self, request, pk):
        from .serializers import CommandeSerializer
        c = Commande.objects.select_related('menu', 'plat').get(pk=pk)
        return Response(CommandeSerializer(c, context={'request': request}).data)

    def get(self, request, pk):
        from .parcours_commande import images_plats
        c = Commande.objects.select_related('menu__typeequipe').filter(pk=pk).first()
        if c is None:
            raise NotFound("Commande introuvable.")
        if c.user_id != request.user.id:
            raise PermissionDenied("Seul l'employé consulte les suppléments de son repas.")
        choisis = set(c.supplements.exclude(statut='annulee').values_list('plat_id', flat=True))
        plats = [mp.plat for mp in MenuPlat.objects.filter(menu=c.menu)
                 .select_related('plat__type_plat__famille_supplement').order_by('plat__nom')]
        offert = bool(c.menu.typeequipe_id and c.menu.typeequipe.repas_offert)
        plats = [p for p in plats if famille_du_plat(p) is not None
                 and (not offert or famille_du_plat(p).repas_offert)]
        images = images_plats({p.id for p in plats})
        modifiable = True
        try:
            _verifier_modifiable(c)
        except ValidationError:
            modifiable = False
        return Response({'modifiable': modifiable, 'supplements': [{
            'id': p.id, 'nom': p.nom, 'description': p.description, 'mentions': p.mentions or [],
            'photo_url': (images.get(p.id) or [None])[0],
            'famille_id': p.type_plat.famille_supplement_id, 'famille': p.type_plat.famille_supplement.libelle,
            'inclus': p.type_plat.famille_supplement.inclus or offert, 'choisi': p.id in choisis,
        } for p in plats]})

    def post(self, request, pk):
        plat_id = request.data.get('plat_id') or request.data.get('plat')
        plat = Plat.objects.filter(pk=plat_id).first() if str(plat_id or '').isdigit() else None
        if plat is None:
            raise ValidationError({'plat_id': "Choisissez le supplément."})
        with transaction.atomic():
            ajouter(self._principal(request, pk), plat, request.user)
        return self._reponse(request, pk)

    def delete(self, request, pk):
        famille = request.query_params.get('famille')
        with transaction.atomic():
            retirer(self._principal(request, pk), int(famille) if str(famille or '').isdigit() else None, request.user)
        return self._reponse(request, pk)
