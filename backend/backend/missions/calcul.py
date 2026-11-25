"""
Calcul des frais de mission (§7) : fonctions pures, sans écriture.

    donnees = normaliser(type_mission, donnees_saisies, complet=True)
    baremes = figer_baremes(type_mission, categorie, donnees, possede_vehicule, d)
    resultat = calculer(type_mission, donnees, baremes)

`baremes` est la copie figée des barèmes (stockée dans la demande à la
soumission) : le calcul d'une demande soumise ne dépend plus des barèmes
modifiés ensuite.
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from baremes import services as baremes
from workflow.erreurs import ErreurMetier

from .models import Distance, Ville

MOYENS = {'vehicule_personnel': 'Véhicule personnel', 'vehicule_service': 'Véhicule de service',
          'transport_commun': 'Transport en commun', 'avion': 'Avion', 'autre': 'Autre'}
TRAJETS = {'aller_retour': 'Aller-retour', 'aller_simple': 'Aller simple'}
RUBRIQUES_FRAIS = {'visa': 'Frais de visa', 'aerien': 'Transport aérien', 'hebergement': 'Hébergement',
                   'autres': 'Autres frais'}
FRAIS_PAR_TYPE = {'locale': ('hebergement', 'autres'), 'hors_pays': ('visa', 'aerien', 'hebergement', 'autres')}
# Une modification de ces champs, après un retour pour correction, fait recalculer avec les barèmes du jour
DETERMINANTS = ('type_mission', 'depart_le', 'retour_le', 'ville_destination', 'pays_destination')
# … et ceux-ci (avec les déterminants) font reprendre le circuit au début
SENSIBLES = DETERMINANTS + ('ville_depart', 'moyen_transport', 'trajet', 'distance_km', 'montant_transport_manuel',
                            'forfait_transport', 'frais')


def _decimal(v, nom):
    try:
        d = Decimal(str(v).replace(' ', '').replace(',', '.'))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{nom} : montant invalide.")
    if d < 0:
        raise ValueError(f"{nom} : montant négatif.")
    return d.quantize(Decimal('0.01'))


def _date_heure(v):
    d = datetime.fromisoformat(str(v).replace('Z', '+00:00'))
    if timezone.is_naive(d):
        d = timezone.make_aware(d)
    return d


def nombre_jours(depart, retour):
    """retour − départ + 1, en jours calendaires (aucune demi-journée)."""
    return (timezone.localtime(retour).date() - timezone.localtime(depart).date()).days + 1


# ═══════════════════════════════════════════════════════════════
# SAISIE
# ═══════════════════════════════════════════════════════════════

def normaliser(type_mission, donnees, complet=False):
    """
    Contrôle et normalise la saisie d'une mission ; ajoute les champs calculés
    (nombre de jours, libellés, distance du référentiel). complet=True : soumission.
    """
    donnees = dict(donnees or {})
    erreurs, m = {}, {'type_mission': type_mission}

    def exiger(cle, message):
        if complet and donnees.get(cle) in (None, '', []):
            erreurs[cle] = message

    texte = (donnees.get('motif') or '').strip()
    m['motif'] = texte[:5000]
    exiger('motif', 'Le motif et la justification sont obligatoires.')

    for cle, libelle in (('ville_depart', 'La ville de départ'), ('ville_destination', 'La destination')):
        valeur = donnees.get(cle)
        if valeur in (None, ''):
            exiger(cle, f"{libelle} est obligatoire.")
            continue
        ville = Ville.objects.select_related('pays').filter(pk=valeur, actif=True).first()
        if ville is None:
            erreurs[cle] = f"{libelle} est inconnue."
            continue
        m[cle], m[f'{cle}_libelle'] = ville.pk, ville.libelle
        if cle == 'ville_destination':
            m['pays_destination'], m['pays_destination_libelle'] = ville.pays_id, ville.pays.libelle

    depart = retour = None
    for cle, libelle in (('depart_le', 'La date de départ'), ('retour_le', 'La date de retour')):
        valeur = donnees.get(cle)
        if valeur in (None, ''):
            exiger(cle, f"{libelle} est obligatoire.")
            continue
        try:
            d = _date_heure(valeur)
        except (ValueError, TypeError):
            erreurs[cle] = f"{libelle} est invalide."
            continue
        m[cle] = d.isoformat()
        depart, retour = (d, retour) if cle == 'depart_le' else (depart, d)
    if depart and retour:
        if retour < depart:
            erreurs['retour_le'] = 'Le retour ne peut pas précéder le départ.'
        else:
            m['nombre_jours'] = nombre_jours(depart, retour)

    moyen = donnees.get('moyen_transport') or ('avion' if type_mission == 'hors_pays' else '')
    if moyen and moyen not in MOYENS:
        erreurs['moyen_transport'] = 'Moyen de transport inconnu.'
    elif moyen:
        m['moyen_transport'] = moyen
    else:
        exiger('moyen_transport', 'Le moyen de transport est obligatoire.')
    trajet = donnees.get('trajet') or 'aller_retour'
    if trajet not in TRAJETS:
        erreurs['trajet'] = 'Trajet inconnu.'
    m['trajet'] = trajet

    try:
        if donnees.get('distance_km') not in (None, ''):
            km = int(Decimal(str(donnees['distance_km'])))
            if km < 0:
                raise ValueError
            m['distance_km'] = km
    except (ValueError, InvalidOperation):
        erreurs['distance_km'] = 'Distance invalide.'
    for cle, nom in (('montant_transport_manuel', 'Transport'), ('forfait_transport', 'Forfait de transport')):
        if donnees.get(cle) not in (None, ''):
            try:
                m[cle] = str(_decimal(donnees[cle], nom))
            except ValueError as e:
                erreurs[cle] = str(e)
    for cle in ('justification_distance', 'justification_transport', 'justification_forfait'):
        m[cle] = (donnees.get(cle) or '').strip()[:1000]

    if type_mission == 'locale' and m.get('ville_depart') and m.get('ville_destination'):
        distance = Distance.entre(m['ville_depart'], m['ville_destination'])
        m['distance_referentiel_km'] = distance.km if distance else None

    frais, erreurs_frais = [], []
    autorises = FRAIS_PAR_TYPE[type_mission]
    for i, f in enumerate(donnees.get('frais') or [], start=1):
        if not isinstance(f, dict) or (f.get('montant') in (None, '') and not f.get('description')):
            continue
        rubrique = f.get('rubrique')
        if rubrique not in autorises:
            erreurs_frais.append(f"Ligne {i} : rubrique non prévue pour ce type de mission.")
            continue
        try:
            montant = _decimal(f.get('montant'), RUBRIQUES_FRAIS[rubrique])
        except ValueError as e:
            erreurs_frais.append(f"Ligne {i} : {e}")
            continue
        devise = (f.get('devise') or baremes.devise_reference()).upper()[:3]
        frais.append({'rubrique': rubrique, 'montant': str(montant), 'devise': devise,
                      'description': (f.get('description') or '').strip()[:255]})
    if erreurs_frais:
        erreurs['frais'] = ' '.join(erreurs_frais)
    m['frais'] = frais

    if erreurs:
        raise ErreurMetier({'mission': erreurs})
    return m


# ═══════════════════════════════════════════════════════════════
# BARÈMES FIGÉS
# ═══════════════════════════════════════════════════════════════

def figer_baremes(type_mission, categorie, donnees, possede_vehicule, d):
    """Copie des barèmes applicables à la date d pour cette mission."""
    fig = {'date': d.isoformat(), 'type_mission': type_mission, 'devise_reference': baremes.devise_reference(),
           'categorie': getattr(categorie, 'pk', None), 'categorie_libelle': getattr(categorie, 'libelle', None),
           'possede_vehicule': possede_vehicule, 'taux': {}}
    fig['per_diem'] = baremes.per_diem(type_mission, categorie, d) if categorie else None
    if type_mission == 'locale':
        fig['tarif_km'] = baremes.tarif_km('locale', categorie, d)
        fig['tarif_ville'] = baremes.tarif_ville(donnees.get('ville_destination'), d)
    else:
        fig['forfait'] = baremes.forfait_hors_pays(d)
    return completer_taux(fig, donnees, d)


def completer_taux(fig, donnees, d):
    """Ajoute les taux des devises utilisées qui manquent encore (nouvelle devise saisie…)."""
    devises = {fig['devise_reference']}
    for cle in ('per_diem', 'tarif_km', 'tarif_ville', 'forfait'):
        if fig.get(cle):
            devises.add(fig[cle]['devise'])
    devises |= {f['devise'] for f in donnees.get('frais', [])}
    for devise in devises:
        if devise not in fig['taux']:
            fig['taux'][devise] = baremes.taux(devise, d, fig['devise_reference'])
    return fig


# ═══════════════════════════════════════════════════════════════
# CALCUL
# ═══════════════════════════════════════════════════════════════

def _fmt(n):
    return f"{n:,.0f}".replace(',', ' ') if n == n.to_integral() else f"{n:,.2f}".replace(',', ' ')


def calculer(type_mission, donnees, fig):
    """
    Récapitulatif détaillé : lignes, total en devise de référence, erreurs
    bloquantes (barème manquant…) et signalements à l'attention des valideurs.
    """
    ref = fig['devise_reference']
    lignes, erreurs, signalements = [], [], []

    def ajouter(rubrique, libelle, montant, devise, base=None, unite='', tarif=None, source=None, signalement=''):
        t = fig['taux'].get(devise)
        if t is None:
            erreurs.append(f"Aucun taux de change défini pour la devise {devise}.")
            montant_ref = None
        else:
            montant_ref = baremes.convertir(montant, t)
        lignes.append({'rubrique': rubrique, 'libelle': libelle, 'base': str(base) if base is not None else None,
                       'unite': unite, 'tarif': str(tarif) if tarif is not None else None, 'devise': devise,
                       'taux': t['taux'] if t else None, 'montant': str(Decimal(montant).quantize(Decimal('0.01'))),
                       'montant_ref': str(montant_ref) if montant_ref is not None else None,
                       'source': source, 'signalement': signalement})
        if signalement:
            signalements.append(signalement)

    jours = donnees.get('nombre_jours')
    type_libelle = 'mission locale' if type_mission == 'locale' else 'mission hors pays'

    # Tant que la destination n'est pas choisie, pas de « tarif introuvable » prématuré :
    # le champ obligatoire est signalé par la validation de la saisie
    destination_choisie = bool(donnees.get('ville_destination'))

    # ── Indemnités journalières ──
    pd = fig.get('per_diem')
    if not fig.get('categorie'):
        erreurs.append("Votre catégorie de salarié n'est pas renseignée : demandez à l'administrateur de la compléter.")
    elif pd is None and type_mission == 'hors_pays' and not destination_choisie:
        pass  # le per diem hors pays dépend du pays de destination
    elif pd is None:
        erreurs.append(f"Aucun per diem n'est défini pour la catégorie « {fig['categorie_libelle']} » en {type_libelle}.")
    elif jours:
        tarif = Decimal(pd['montant'])
        ajouter('per_diem', f"{jours} jour(s) × {_fmt(tarif)} {pd['devise']} ({fig['categorie_libelle']}, {type_libelle}, "
                f"barème du {_date_fr(pd['date_effet'])})", tarif * jours, pd['devise'], jours, 'jour(s)', tarif, pd)

    # ── Transport ──
    if type_mission == 'hors_pays':
        forfait = fig.get('forfait')
        if forfait is None:
            erreurs.append("Le forfait de transport des missions hors pays n'est pas défini.")
        else:
            bareme = Decimal(forfait['montant'])
            saisi = donnees.get('forfait_transport')
            montant, signalement = bareme, ''
            if saisi not in (None, '') and Decimal(saisi) != bareme:
                if not donnees.get('justification_forfait'):
                    erreurs.append("Justifiez l'ajustement du forfait de transport.")
                montant = Decimal(saisi)
                signalement = (f"Forfait de transport ajusté : {_fmt(montant)} {forfait['devise']} au lieu de "
                               f"{_fmt(bareme)} ({donnees.get('justification_forfait', '')}).")
            ajouter('transport', "Forfait de transport (trajet vers l'aéroport)", montant, forfait['devise'],
                    tarif=bareme, source=forfait, signalement=signalement)
    else:
        moyen = donnees.get('moyen_transport')
        depart, destination = donnees.get('ville_depart_libelle', '?'), donnees.get('ville_destination_libelle', '?')
        if moyen == 'vehicule_personnel':
            km_ref, km_saisi = donnees.get('distance_referentiel_km'), donnees.get('distance_km')
            if not fig.get('possede_vehicule'):
                erreurs.append("Aucun véhicule personnel n'est déclaré pour vous : choisissez un autre moyen de transport.")
            elif km_ref is None and km_saisi is None:
                erreurs.append(f"Distance inconnue entre {depart} et {destination} : saisissez-la avec une justification.")
            elif fig.get('tarif_km') is None:
                erreurs.append("Aucun tarif kilométrique n'est défini.")
            else:
                km, signalement = km_ref, ''
                if km_saisi is not None and km_saisi != km_ref:
                    if not donnees.get('justification_distance'):
                        erreurs.append("Justifiez la distance saisie (différente du référentiel ou hors référentiel).")
                    km = km_saisi
                    signalement = (f"Distance saisie : {km_saisi} km au lieu de {km_ref} km (référentiel)" if km_ref is not None
                                   else f"Distance hors référentiel saisie : {km_saisi} km") + \
                        f" — {donnees.get('justification_distance', '')}"
                aller_retour = donnees.get('trajet') == 'aller_retour'
                base = km * (2 if aller_retour else 1)
                tarif = Decimal(fig['tarif_km']['montant'])
                ajouter('transport', f"{depart} → {destination}{' aller-retour' if aller_retour else ''} : "
                        f"{base} km × {_fmt(tarif)} {fig['tarif_km']['devise']}", tarif * base, fig['tarif_km']['devise'],
                        base, 'km', tarif, fig['tarif_km'], signalement)
        elif moyen == 'vehicule_service':
            ajouter('transport', "Véhicule de service : pas d'indemnité de transport", Decimal('0'), ref)
        elif moyen:
            tv = fig.get('tarif_ville')
            if tv is not None:
                ajouter('transport', f"Transport {depart} → {destination}, tarif de la ville (aller-retour inclus)",
                        Decimal(tv['montant']), tv['devise'], tarif=Decimal(tv['montant']), source=tv)
            elif donnees.get('montant_transport_manuel') not in (None, ''):
                if not donnees.get('justification_transport'):
                    erreurs.append(f"Aucun tarif de transport pour {destination} : justifiez le montant saisi.")
                montant = Decimal(donnees['montant_transport_manuel'])
                ajouter('transport', f"Transport {depart} → {destination} (montant saisi, ville sans tarif)", montant, ref,
                        signalement=f"Ville sans tarif de transport : montant saisi par le demandeur "
                                    f"({_fmt(montant)} {ref}) — {donnees.get('justification_transport', '')}")
            elif destination_choisie:
                erreurs.append(f"Aucun tarif de transport n'est défini pour {destination} : "
                               "saisissez le montant avec une justification.")

    # ── Autres frais ──
    for f in donnees.get('frais', []):
        libelle = RUBRIQUES_FRAIS[f['rubrique']] + (f" — {f['description']}" if f.get('description') else '')
        ajouter(f['rubrique'], libelle, Decimal(f['montant']), f['devise'])

    total = sum((Decimal(l['montant_ref']) for l in lignes if l['montant_ref'] is not None), Decimal('0'))
    return {'lignes': lignes, 'total_ref': str(total.quantize(Decimal('0.01'))), 'devise_reference': ref,
            'nombre_jours': jours, 'erreurs': erreurs, 'signalements': signalements,
            'date_baremes': fig['date'], 'categorie': fig.get('categorie_libelle')}


def _date_fr(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}" if iso else '—'
