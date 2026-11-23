"""
Import des collaborateurs depuis un fichier Excel (en attendant la
synchronisation avec un système RH). Le matricule est la clé de
rapprochement.

Règles :
- une ligne par collaborateur ; ligne entièrement vide ignorée ;
- matricule inconnu → collaborateur créé (rôle « employe », sans mot de
  passe utilisable : l'administrateur le définit, ou l'agent utilise « mot
  de passe oublié ») ; matricule connu → collaborateur mis à jour ;
- cellule vide = pas de changement ;
- une affectation qui change (agence, département, poste, catégorie,
  véhicule) ferme la ligne en cours la veille de la date d'effet et en
  ouvre une nouvelle à la date d'effet ; aucune ligne n'est écrasée ;
- N+1 : matricule du N+1 → N+1 désigné ; « AUTO » → responsable du
  département ; les matricules peuvent désigner un collaborateur créé plus
  loin dans le même fichier ;
- les référentiels (statut, agence, département, poste, catégorie) doivent
  exister : une valeur inconnue rejette la ligne, sans rien modifier ;
- mode simulation : tout est contrôlé puis annulé, seul le rapport reste.
"""
import io
import unicodedata
from datetime import datetime, time, timedelta

from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from .models import (
    AffectationHierarchique, Agence, Categoriesalarie, ImportCollaborateurs, Poste, Service,
    SituationVehicule, Statut, User, UserAgence, UserCategoriesalarie, UserPoste, UserService,
)
from .organisation import affectation_hierarchique_en_cours, filtre_en_cours
from .permissions import ROLE_EMPLOYE

# (clé, en-tête affiché, obligatoire, aide)
COLONNES = [
    ('matricule', 'Matricule', True, 'Identifiant unique du collaborateur (sert aussi à la connexion)'),
    ('nom', 'Nom', True, ''),
    ('prenom', 'Prénoms', True, ''),
    ('email', 'E-mail', False, ''),
    ('contact', 'Téléphone', False, 'Sert à l\'envoi du code « mot de passe oublié »'),
    ('statut', 'Statut', False, 'Libellé d\'un statut existant (défaut à la création : Actif)'),
    ('agence', 'Agence', False, 'Nom ou code d\'une agence existante'),
    ('departement', 'Département', False, 'Libellé ou code d\'un département existant'),
    ('poste', 'Poste', False, 'Libellé d\'un poste existant'),
    ('categorie', 'Catégorie', False, 'Libellé d\'une catégorie de salarié existante'),
    ('vehicule', 'Véhicule personnel', False, 'OUI ou NON'),
    ('matricule_n1', 'Matricule N+1', False, 'Matricule du N+1 désigné, ou AUTO pour le responsable du département'),
]
CLES = [c[0] for c in COLONNES]
OUI = {'oui', 'o', 'yes', 'y', '1', 'true', 'vrai', 'x'}
NON = {'non', 'n', 'no', '0', 'false', 'faux'}


class ImportInvalide(Exception):
    """Fichier inutilisable (format, en-têtes manquants)."""


class _LigneRejetee(Exception):
    pass


class _Simulation(Exception):
    """Levée en fin de simulation pour annuler toutes les écritures."""


def _norm(texte):
    texte = unicodedata.normalize('NFD', str(texte or '')).encode('ascii', 'ignore').decode()
    return ' '.join(texte.lower().replace('_', ' ').replace('-', ' ').split())


_ENTETES = {_norm(entete): cle for cle, entete, *_ in COLONNES}
_ENTETES.update({_norm(cle): cle for cle in CLES})
_ENTETES.update({'prenom': 'prenom', 'telephone': 'contact', 'service': 'departement',
                 'categorie salarie': 'categorie', 'categorie de salarie': 'categorie',
                 'vehicule': 'vehicule', 'possede vehicule': 'vehicule', 'n+1': 'matricule_n1',
                 'matricule n 1': 'matricule_n1', 'email': 'email', 'mail': 'email'})


def _texte(valeur):
    if valeur is None:
        return ''
    if isinstance(valeur, float) and valeur.is_integer():
        valeur = int(valeur)
    return str(valeur).strip()


# ── Modèle de fichier ──────────────────────────────────────────

def generer_modele():
    """Classeur Excel vierge : feuille « Collaborateurs » + feuille « Instructions »."""
    wb = Workbook()
    ws = wb.active
    ws.title = 'Collaborateurs'
    gras = Font(bold=True, color='FFFFFF')
    fond = PatternFill('solid', fgColor='0F3A6E')
    for i, (cle, entete, obligatoire, _) in enumerate(COLONNES, start=1):
        cell = ws.cell(row=1, column=i, value=entete + (' *' if obligatoire else ''))
        cell.font, cell.fill = gras, fond
        ws.column_dimensions[get_column_letter(i)].width = max(14, len(entete) + 4)
    ws.append(['A0001', 'KONE', 'Fatou', 'fatou.kone@exemple.com', '0700000000', 'Actif', 'Abidjan',
               'Finances', 'Comptable', 'Cadre', 'NON', 'AUTO'])
    ws.freeze_panes = 'A2'

    info = wb.create_sheet('Instructions')
    info.append(['Colonne', 'Obligatoire', 'Contenu'])
    for c in info[1]:
        c.font = Font(bold=True)
    for _, entete, obligatoire, aide in COLONNES:
        info.append([entete, 'Oui' if obligatoire else 'Non', aide])
    info.append([])
    for ligne in (
        'Une ligne par collaborateur. Le matricule identifie le collaborateur : connu = mise à jour, inconnu = création.',
        'Une cellule vide ne modifie rien.',
        "Une affectation modifiée ferme l'ancienne la veille de la date d'effet choisie à l'import.",
        'Les statuts, agences, départements, postes et catégories doivent déjà exister dans UbiFlow.',
        "Supprimez la ligne d'exemple avant l'import.",
    ):
        info.append([ligne])
    info.column_dimensions['A'].width = 22
    info.column_dimensions['B'].width = 12
    info.column_dimensions['C'].width = 90

    sortie = io.BytesIO()
    wb.save(sortie)
    return sortie.getvalue()


# ── Lecture ────────────────────────────────────────────────────

def lire_fichier(fichier):
    """Renvoie [(numéro de ligne, {clé: valeur})] ; lève ImportInvalide."""
    try:
        wb = load_workbook(fichier, read_only=True, data_only=True)
    except Exception:
        raise ImportInvalide("Le fichier n'est pas un classeur Excel (.xlsx) lisible.")
    ws = wb['Collaborateurs'] if 'Collaborateurs' in wb.sheetnames else wb.worksheets[0]
    lignes = ws.iter_rows(values_only=True)
    try:
        entetes = next(lignes)
    except StopIteration:
        raise ImportInvalide('Le fichier est vide.')
    colonnes = {}
    for i, entete in enumerate(entetes or ()):
        cle = _ENTETES.get(_norm(_texte(entete).rstrip('*').strip()))
        if cle and cle not in colonnes:
            colonnes[cle] = i
    manquantes = [entete for cle, entete, obligatoire, _ in COLONNES if obligatoire and cle not in colonnes]
    if manquantes:
        raise ImportInvalide(f"Colonne(s) obligatoire(s) absente(s) : {', '.join(manquantes)}. "
                             "Utilisez le modèle de fichier.")
    resultat = []
    for numero, valeurs in enumerate(lignes, start=2):
        donnees = {cle: _texte(valeurs[i]) if i < len(valeurs) else '' for cle, i in colonnes.items()}
        if any(donnees.values()):
            resultat.append((numero, donnees))
    return resultat


# ── Import ─────────────────────────────────────────────────────

class _Referentiels:
    """Recherche des référentiels par libellé ou code (casse et accents ignorés)."""

    def __init__(self):
        self.statuts = self._index(Statut.objects.all(), 'libelle_statut')
        self.agences = self._index(Agence.objects.all(), 'nom_agence', 'code')
        self.departements = self._index(Service.objects.all(), 'libelle_service', 'code')
        self.postes = self._index(Poste.objects.all(), 'libelle')
        self.categories = self._index(Categoriesalarie.objects.all(), 'libelle')
        self.actif = self.statuts.get('actif') or Statut.objects.order_by('id').first()

    @staticmethod
    def _index(qs, *champs):
        index = {}
        for obj in qs:
            for champ in champs:
                valeur = _norm(getattr(obj, champ, ''))
                if valeur:
                    index.setdefault(valeur, obj)
        return index

    def trouver(self, nom, index, valeur, messages):
        if not valeur:
            return None
        obj = index.get(_norm(valeur))
        if obj is None:
            messages.append(f"{nom} inconnu(e) : « {valeur} ».")
        return obj


def _debut_horodate(d):
    return timezone.make_aware(datetime.combine(d, time.min))


def _changer_affectation(user, modele, champ, valeur, date_effet, statut, horodate, auteur):
    """Ferme la ligne en cours et ouvre la nouvelle ; renvoie True si changement."""
    en_cours = (modele.objects.filter(user=user).filter(filtre_en_cours(date_effet, horodate))
                .order_by('-date_debut', '-id').first())
    if en_cours is not None and getattr(en_cours, champ + '_id', None) == getattr(valeur, 'pk', valeur):
        return False
    debut_en_cours = None
    if en_cours is not None:
        debut_en_cours = en_cours.date_debut.date() if horodate else en_cours.date_debut
    if en_cours is not None and debut_en_cours >= date_effet:
        # La ligne commence le jour même : on la corrige plutôt que d'en créer une d'un jour
        setattr(en_cours, champ, valeur)
        en_cours.user_updated = auteur
        en_cours.save()
        return True
    if en_cours is not None:
        veille = date_effet - timedelta(days=1)
        en_cours.date_fin = _debut_horodate(veille).replace(hour=23, minute=59, second=59) if horodate else veille
        en_cours.user_updated = auteur
        en_cours.save()
    # Lignes futures déjà saisies : on ne les touche pas, la nouvelle ligne s'arrête avant
    suivante = (modele.objects.filter(user=user, **({'date_debut__date__gt': date_effet} if horodate
                                                    else {'date_debut__gt': date_effet}))
                .order_by('date_debut').first())
    champs = {'user': user, champ: valeur, 'user_created': auteur, 'user_updated': auteur}
    if horodate:
        champs.update(date_debut=_debut_horodate(date_effet), statut=statut)
        if suivante:
            fin = suivante.date_debut.date() - timedelta(days=1)
            champs['date_fin'] = _debut_horodate(fin).replace(hour=23, minute=59, second=59)
    else:
        champs['date_debut'] = date_effet
        if suivante:
            champs['date_fin'] = suivante.date_debut - timedelta(days=1)
    modele.objects.create(**champs)
    return True


def _appliquer_ligne(donnees, refs, date_effet, auteur, groupe_employe, deja_vus):
    """Crée ou met à jour un collaborateur ; renvoie (user, résultat, messages)."""
    messages, changements = [], []
    matricule = donnees.get('matricule', '')
    if not matricule:
        raise _LigneRejetee(['Matricule manquant.'])
    if matricule.lower() in deja_vus:
        raise _LigneRejetee([f"Matricule « {matricule} » présent plusieurs fois dans le fichier."])
    deja_vus.add(matricule.lower())
    for cle in ('nom', 'prenom'):
        if not donnees.get(cle):
            messages.append(f"{'Nom' if cle == 'nom' else 'Prénoms'} manquant(s).")

    statut = refs.trouver('Statut', refs.statuts, donnees.get('statut'), messages)
    agence = refs.trouver('Agence', refs.agences, donnees.get('agence'), messages)
    dept = refs.trouver('Département', refs.departements, donnees.get('departement'), messages)
    poste = refs.trouver('Poste', refs.postes, donnees.get('poste'), messages)
    categorie = refs.trouver('Catégorie', refs.categories, donnees.get('categorie'), messages)
    vehicule = None
    if donnees.get('vehicule'):
        v = _norm(donnees['vehicule'])
        if v in OUI:
            vehicule = True
        elif v in NON:
            vehicule = False
        else:
            messages.append(f"Véhicule personnel : « {donnees['vehicule']} » (attendu : OUI ou NON).")
    email = donnees.get('email', '')
    if email and ('@' not in email or ' ' in email):
        messages.append(f"E-mail invalide : « {email} ».")
    if messages:
        raise _LigneRejetee(messages)

    user = User.objects.filter(username__iexact=matricule).first()
    creation = user is None
    if creation:
        user = User(username=matricule, statut=statut or refs.actif, user_created=auteur, is_active=True)
        user.set_unusable_password()
    identite = {'nom': donnees.get('nom'), 'prenom': donnees.get('prenom'), 'email': email,
                'contact': donnees.get('contact')}
    for champ, valeur in identite.items():
        if valeur and getattr(user, champ) != valeur:
            setattr(user, champ, valeur)
            changements.append(champ)
    if statut and user.statut_id != statut.pk:
        user.statut = statut
        changements.append('statut')
    if creation or changements:
        user.user_updated = auteur
        user.save()
    if creation:
        user.groups.add(groupe_employe)

    st = refs.actif
    for libelle, modele, champ, valeur in (('agence', UserAgence, 'agence', agence),
                                           ('département', UserService, 'service', dept),
                                           ('poste', UserPoste, 'poste', poste),
                                           ('catégorie', UserCategoriesalarie, 'categoriesalarie', categorie)):
        if valeur is not None and _changer_affectation(user, modele, champ, valeur, date_effet, st, True, auteur):
            changements.append(libelle)
    if vehicule is not None:
        en_cours = (SituationVehicule.objects.filter(user=user).filter(filtre_en_cours(date_effet))
                    .order_by('-date_debut').first())
        if en_cours is None or en_cours.possede_vehicule != vehicule:
            _changer_affectation(user, SituationVehicule, 'possede_vehicule', vehicule, date_effet,
                                 None, False, auteur)
            changements.append('véhicule')

    if creation:
        return user, 'cree', ['Collaborateur créé (mot de passe à définir).']
    if changements:
        return user, 'mis_a_jour', [f"Modifié : {', '.join(changements)}."]
    return user, 'inchange', []


def _appliquer_n1(user, valeur, date_effet, auteur):
    """Renvoie un message de changement, None si inchangé ; lève _LigneRejetee."""
    if not valeur:
        return None
    if _norm(valeur) == 'auto':
        mode, responsable = AffectationHierarchique.MODE_AUTOMATIQUE, None
    else:
        responsable = User.objects.filter(username__iexact=valeur).first()
        if responsable is None:
            raise _LigneRejetee([f"Matricule N+1 inconnu : « {valeur} »."])
        if responsable.pk == user.pk:
            raise _LigneRejetee(['Un collaborateur ne peut pas être son propre N+1.'])
        mode = AffectationHierarchique.MODE_DESIGNE
    en_cours = affectation_hierarchique_en_cours(user, date_effet)
    actuel_mode = en_cours.mode if en_cours else AffectationHierarchique.MODE_AUTOMATIQUE
    actuel_resp = en_cours.responsable_id if en_cours else None
    if actuel_mode == mode and actuel_resp == (responsable.pk if responsable else None):
        return None
    if en_cours is not None and en_cours.date_debut >= date_effet:
        en_cours.mode, en_cours.responsable, en_cours.user_updated = mode, responsable, auteur
        en_cours.save()
    else:
        if en_cours is not None:
            en_cours.date_fin, en_cours.user_updated = date_effet - timedelta(days=1), auteur
            en_cours.save()
        AffectationHierarchique.objects.create(user=user, mode=mode, responsable=responsable,
                                               date_debut=date_effet, motif='Import Excel',
                                               user_created=auteur, user_updated=auteur)
    return f"N+1 : {responsable.username if responsable else 'responsable du département'}."


def importer(fichier, nom_fichier, date_effet, auteur, simulation=False):
    """Importe le fichier et renvoie l'ImportCollaborateurs enregistré (rapport)."""
    lignes = lire_fichier(fichier)
    if not lignes:
        raise ImportInvalide('Aucune ligne de collaborateur dans le fichier.')
    rapport = []

    def traiter():
        refs = _Referentiels()
        groupe_employe, _ = Group.objects.get_or_create(name=ROLE_EMPLOYE)
        deja_vus, acceptes = set(), []
        # 1er passage : identités et affectations
        for numero, donnees in lignes:
            entree = {'ligne': numero, 'matricule': donnees.get('matricule', ''), 'resultat': 'rejete',
                      'messages': []}
            try:
                with transaction.atomic():
                    user, resultat, messages = _appliquer_ligne(donnees, refs, date_effet, auteur,
                                                                groupe_employe, deja_vus)
                entree.update(resultat=resultat, messages=messages)
                acceptes.append((entree, user, donnees))
            except _LigneRejetee as e:
                entree['messages'] = e.args[0]
            rapport.append(entree)
        # 2e passage : N+1 (peut désigner un collaborateur créé plus bas dans le fichier)
        for entree, user, donnees in acceptes:
            try:
                with transaction.atomic():
                    message = _appliquer_n1(user, donnees.get('matricule_n1'), date_effet, auteur)
                if message:
                    entree['messages'].append(message)
                    if entree['resultat'] == 'inchange':
                        entree['resultat'] = 'mis_a_jour'
            except _LigneRejetee as e:
                entree['messages'] += e.args[0] + ['Le reste de la ligne a été importé.']
                entree['avertissement'] = True

    if simulation:
        try:
            with transaction.atomic():
                traiter()
                raise _Simulation()
        except _Simulation:
            pass
    else:
        with transaction.atomic():
            traiter()

    compte = lambda r: sum(1 for e in rapport if e['resultat'] == r)
    return ImportCollaborateurs.objects.create(
        fichier_nom=nom_fichier[:255], auteur=auteur, date_effet=date_effet, simulation=simulation,
        nb_lignes=len(rapport), nb_crees=compte('cree'), nb_mis_a_jour=compte('mis_a_jour'),
        nb_inchanges=compte('inchange'), nb_rejetes=compte('rejete'), rapport=rapport,
    )
