"""Montant en toutes lettres (orthographe traditionnelle : vingt et un, quatre-vingts, deux cents, mille)."""
from decimal import Decimal, ROUND_HALF_UP

UNITES = ['zéro', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf', 'dix', 'onze', 'douze',
          'treize', 'quatorze', 'quinze', 'seize']
DIZAINES = {2: 'vingt', 3: 'trente', 4: 'quarante', 5: 'cinquante', 6: 'soixante'}
DEVISES = {'XOF': ('franc CFA', 'francs CFA'), 'XAF': ('franc CFA', 'francs CFA'), 'EUR': ('euro', 'euros'),
           'USD': ('dollar', 'dollars'), 'GBP': ('livre sterling', 'livres sterling')}


def _moins_de_cent(n):
    if n <= 16:
        return UNITES[n]
    if n < 20:
        return 'dix-' + UNITES[n - 10]
    d, u = divmod(n, 10)
    if d in (7, 9):  # soixante-dix…, quatre-vingt-dix…
        base = 'soixante' if d == 7 else 'quatre-vingt'
        reste = n - (60 if d == 7 else 80)
        if d == 7 and reste == 11:
            return 'soixante et onze'
        return f"{base}-{_moins_de_cent(reste)}"
    if d == 8:
        return 'quatre-vingts' if u == 0 else f"quatre-vingt-{UNITES[u]}"
    if u == 0:
        return DIZAINES[d]
    if u == 1:
        return f"{DIZAINES[d]} et un"
    return f"{DIZAINES[d]}-{UNITES[u]}"


def _moins_de_mille(n, final=True):
    c, r = divmod(n, 100)
    if c == 0:
        return _moins_de_cent(r)
    cent = 'cent' if c == 1 else f"{UNITES[c]} cent" + ('s' if r == 0 and final else '')
    return cent if r == 0 else f"{cent} {_moins_de_cent(r)}"


def nombre_en_lettres(n):
    n = int(n)
    if n == 0:
        return 'zéro'
    morceaux = []
    for valeur, sing, plur in ((10 ** 9, 'milliard', 'milliards'), (10 ** 6, 'million', 'millions')):
        q, n = divmod(n, valeur)
        if q:
            morceaux.append(f"{nombre_en_lettres(q)} {sing if q == 1 else plur}")
    q, n = divmod(n, 1000)
    if q:
        milliers = _moins_de_mille(q, final=False)
        if milliers.endswith('quatre-vingts'):  # « vingt » et « cent » ne prennent pas de « s » devant « mille »
            milliers = milliers[:-1]
        morceaux.append('mille' if q == 1 else f"{milliers} mille")
    if n:
        morceaux.append(_moins_de_mille(n))
    return ' '.join(morceaux)


def montant_en_lettres(montant, devise='XOF'):
    """1 500 000 XOF → « Un million cinq cent mille francs CFA »."""
    m = Decimal(str(montant or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    entier, centimes = int(m), int((m - int(m)) * 100)
    sing, plur = DEVISES.get((devise or '').upper(), (devise, devise))
    texte = f"{nombre_en_lettres(entier)} {sing if entier <= 1 else plur}"
    if entier >= 10 ** 6 and entier % 10 ** 6 == 0:  # « un million de francs »
        texte = f"{nombre_en_lettres(entier)} de {plur}"
    if centimes:
        texte += f" et {nombre_en_lettres(centimes)} centime{'s' if centimes > 1 else ''}"
    return texte[:1].upper() + texte[1:]
