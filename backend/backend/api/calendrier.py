"""Calendrier ouvré : jours ouvrés (paramètre système) et jours fériés (JourFerie)."""
from datetime import timedelta

from django.utils import timezone

JOURS_OUVRES_DEFAUT = [0, 1, 2, 3, 4]


def _contexte():
    from .models import JourFerie, ParametreSysteme
    ouvres = set(ParametreSysteme.charger().jours_ouvres or JOURS_OUVRES_DEFAUT)
    feries = set(JourFerie.objects.values_list('date', flat=True))
    return ouvres, feries


def est_ouvre(d, ctx=None):
    ouvres, feries = ctx or _contexte()
    return d.weekday() in ouvres and d not in feries


def heures_ouvrees(debut, fin, ctx=None):
    """Heures écoulées entre deux instants, en ne comptant que les jours ouvrés (24 h par jour ouvré)."""
    if not debut or not fin or fin <= debut:
        return 0.0
    ctx = ctx or _contexte()
    debut, fin = timezone.localtime(debut), timezone.localtime(fin)
    total, curseur = 0.0, debut
    while curseur < fin:
        minuit = (curseur + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        borne = min(minuit, fin)
        if est_ouvre(curseur.date(), ctx):
            total += (borne - curseur).total_seconds() / 3600
        curseur = borne
    return total


def ajouter_heures_ouvrees(debut, heures, ctx=None):
    """Instant atteint après `heures` heures ouvrées à partir de `debut`."""
    ctx = ctx or _contexte()
    curseur, reste = timezone.localtime(debut), float(heures)
    for _ in range(3660):  # au plus 10 ans
        minuit = (curseur + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        if est_ouvre(curseur.date(), ctx):
            dispo = (minuit - curseur).total_seconds() / 3600
            if reste <= dispo:
                return curseur + timedelta(hours=reste)
            reste -= dispo
        curseur = minuit
    return curseur
