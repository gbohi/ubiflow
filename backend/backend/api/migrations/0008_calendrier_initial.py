"""
Calendrier initial : lundi à vendredi ouvrés ; jours fériés de Côte d'Ivoire à date
fixe et fêtes chrétiennes mobiles 2026-2027. Les fêtes musulmanes (Ramadan,
Tabaski, Maouloud, Lendemain de la Nuit du Destin), fixées chaque année, sont à
saisir par l'administrateur (Paramètres → Calendrier).
"""
from datetime import date

from django.db import migrations

FERIES = []
for an in (2026, 2027):
    FERIES += [(date(an, 1, 1), "Jour de l'an"), (date(an, 5, 1), 'Fête du travail'),
               (date(an, 8, 7), "Fête de l'indépendance"), (date(an, 8, 15), 'Assomption'),
               (date(an, 11, 1), 'Toussaint'), (date(an, 11, 15), 'Journée nationale de la paix'),
               (date(an, 12, 25), 'Noël')]
FERIES += [(date(2026, 4, 6), 'Lundi de Pâques'), (date(2026, 5, 14), 'Ascension'), (date(2026, 5, 25), 'Lundi de Pentecôte'),
           (date(2027, 3, 29), 'Lundi de Pâques'), (date(2027, 5, 6), 'Ascension'), (date(2027, 5, 17), 'Lundi de Pentecôte')]


def creer(apps, schema_editor):
    P = apps.get_model('api', 'ParametreSysteme')
    p, _ = P.objects.get_or_create(pk=1)
    if not p.jours_ouvres:
        p.jours_ouvres = [0, 1, 2, 3, 4]
        p.save(update_fields=['jours_ouvres'])
    J = apps.get_model('api', 'JourFerie')
    for d, libelle in FERIES:
        J.objects.get_or_create(date=d, defaults={'libelle': libelle})


class Migration(migrations.Migration):
    dependencies = [('api', '0007_jourferie_parametresysteme_jours_ouvres')]
    operations = [migrations.RunPython(creer, migrations.RunPython.noop)]
