"""
Conditions d'exécution des étapes (§5.3) : structure JSON, jamais de code.

    {"et": [ {"champ": "montant_demande_ref", "op": ">", "valeur": 1000000},
             {"ou": [ {...}, {...} ]} ]}

Opérateurs : = ≠ > ≥ < ≤ dans pas_dans vide non_vide sous (département ou
un de ses sous-départements). Les champs propres à un type de demande
s'écrivent « champ.<code> ».
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from .erreurs import ErreurMetier

OPERATEURS = {
    '=': 'est égal à', '≠': 'est différent de', '>': 'est supérieur à', '≥': 'est supérieur ou égal à',
    '<': 'est inférieur à', '≤': 'est inférieur ou égal à', 'dans': 'fait partie de',
    'pas_dans': 'ne fait pas partie de', 'vide': 'est vide', 'non_vide': "n'est pas vide",
    'sous': 'est le département ou un de ses sous-départements',
}
SANS_VALEUR = {'vide', 'non_vide'}
NUMERIQUES = {'>', '≥', '<', '≤'}


def champs_disponibles(type_demande=None):
    """Champs utilisables dans les conditions : communs + champs du type marqués « utilisables »."""
    champs = [
        {'code': 'montant_demande_ref', 'libelle': 'Montant (devise de référence)', 'nature': 'montant'},
        {'code': 'categorie', 'libelle': 'Catégorie du demandeur', 'nature': 'categorie'},
        {'code': 'departement', 'libelle': 'Département du demandeur', 'nature': 'departement'},
        {'code': 'agence', 'libelle': 'Agence du demandeur', 'nature': 'agence'},
        {'code': 'type_demande', 'libelle': 'Type de demande', 'nature': 'texte'},
    ]
    if type_demande is not None:
        for c in type_demande.champs.filter(utilisable_en_condition=True, actif=True):
            champs.append({'code': f'champ.{c.code}', 'libelle': c.libelle, 'nature': c.nature,
                           'options': c.options})
        from demandes import extensions
        champs += extensions.pour(type_demande).champs_condition(type_demande)
    return champs


def _nombre(v):
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _comparable(v):
    """Nombres et dates ISO comparables ; le reste en texte (casse ignorée)."""
    if isinstance(v, bool) or v is None:
        return v
    n = _nombre(v)
    if n is not None:
        return n
    if isinstance(v, date):
        return v.isoformat()
    return str(v).strip().lower()


def _egal(a, b):
    return _comparable(a) == _comparable(b)


def _feuille(cond, contexte):
    champ, op, attendu = cond.get('champ'), cond.get('op'), cond.get('valeur')
    valeur = contexte.get(champ)
    if op == 'vide':
        return valeur in (None, '', [])
    if op == 'non_vide':
        return valeur not in (None, '', [])
    if op == 'sous':
        return _comparable(attendu) in {_comparable(x) for x in contexte.get(f'{champ}__arbre', [])}
    if valeur in (None, ''):
        return op in ('≠', 'pas_dans')
    if op == '=':
        return _egal(valeur, attendu)
    if op == '≠':
        return not _egal(valeur, attendu)
    if op in ('dans', 'pas_dans'):
        liste = attendu if isinstance(attendu, list) else [attendu]
        present = any(_egal(valeur, x) for x in liste)
        return present if op == 'dans' else not present
    a, b = _comparable(valeur), _comparable(attendu)
    if type(a) is not type(b):
        return False
    return {'>': a > b, '≥': a >= b, '<': a < b, '≤': a <= b}[op]


def evaluer(condition, contexte):
    """Vrai si la condition est remplie (condition vide = toujours vraie)."""
    if not condition:
        return True
    if 'et' in condition:
        return all(evaluer(c, contexte) for c in condition['et'])
    if 'ou' in condition:
        return any(evaluer(c, contexte) for c in condition['ou'])
    return _feuille(condition, contexte)


def valider(condition, type_demande=None, profondeur=0):
    """Lève ErreurMetier si la condition est mal formée (contrôle à l'enregistrement)."""
    if condition in (None, {}):
        return
    if not isinstance(condition, dict) or profondeur > 5:
        raise ErreurMetier("Condition mal formée.")
    codes = {c['code'] for c in champs_disponibles(type_demande)}
    for groupe in ('et', 'ou'):
        if groupe in condition:
            enfants = condition[groupe]
            if not isinstance(enfants, list) or not enfants:
                raise ErreurMetier("Un groupe ET / OU doit contenir au moins une règle.")
            for enfant in enfants:
                valider(enfant, type_demande, profondeur + 1)
            return
    champ, op = condition.get('champ'), condition.get('op')
    if champ not in codes:
        raise ErreurMetier(f"Champ inconnu dans la condition : « {champ} ».")
    if op not in OPERATEURS:
        raise ErreurMetier(f"Opérateur inconnu dans la condition : « {op} ».")
    if op not in SANS_VALEUR and condition.get('valeur') in (None, '', []):
        raise ErreurMetier(f"Condition sur « {champ} » : la valeur est obligatoire.")
    if op in NUMERIQUES and _nombre(condition.get('valeur')) is None and not str(condition.get('valeur'))[:4].isdigit():
        raise ErreurMetier(f"Condition sur « {champ} » : une valeur numérique ou une date est attendue.")


def nom_valeur(champ, valeur):
    """Libellé d'une valeur de référentiel (catégorie, département, agence) ; sinon la valeur."""
    from api.models import Agence, Categoriesalarie, Service
    modele, attribut = {'categorie': (Categoriesalarie, 'libelle'), 'departement': (Service, 'libelle_service'),
                        'agence': (Agence, 'nom_agence')}.get(champ, (None, None))
    if modele is None:
        return valeur
    obj = modele.objects.filter(pk=valeur).first() if str(valeur).isdigit() else None
    return getattr(obj, attribut) if obj else valeur


def decrire(condition, libelles=None):
    """Texte lisible de la condition (plan de validation, simulation)."""
    if not condition:
        return 'toujours'
    libelles = libelles or {}
    for groupe, mot in (('et', ' et '), ('ou', ' ou ')):
        if groupe in condition:
            parties = [decrire(c, libelles) for c in condition[groupe]]
            texte = mot.join(parties)
            return f'({texte})' if len(parties) > 1 else texte
    champ = libelles.get(condition.get('champ'), condition.get('champ'))
    op = OPERATEURS.get(condition.get('op'), condition.get('op'))
    if condition.get('op') in SANS_VALEUR:
        return f'{champ} {op}'
    code, valeur = condition.get('champ'), condition.get('valeur')
    if isinstance(valeur, list):
        valeur = ', '.join(str(nom_valeur(code, v)) for v in valeur)
    else:
        valeur = nom_valeur(code, valeur)
        if isinstance(valeur, (int, float)) or str(valeur).isdigit():
            valeur = f"{int(float(valeur)):,}".replace(',', ' ')
    return f'{champ} {op} {valeur}'
