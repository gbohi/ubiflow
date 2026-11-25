"""Coordonnées des villes du référentiel, pour la carte des destinations (statistiques)."""
from decimal import Decimal

from django.db import migrations, models

COORDONNEES = {
    'Abengourou': (6.7297, -3.4964), 'Abidjan': (5.3600, -4.0083), 'Accra': (5.6037, -0.1870),
    'Agboville': (5.9280, -4.2130), 'Bamako': (12.6392, -8.0029), 'Bondoukou': (8.0402, -2.8000),
    'Bouaké': (7.6906, -5.0300), 'Bruxelles': (50.8503, 4.3517), 'Casablanca': (33.5731, -7.5898),
    'Cotonou': (6.3703, 2.3912), 'Dabou': (5.3256, -4.3768), 'Dakar': (14.7167, -17.4677),
    'Daloa': (6.8774, -6.4502), 'Divo': (5.8372, -5.3572), 'Douala': (4.0511, 9.7679),
    'Dubaï': (25.2048, 55.2708), 'Ferkessédougou': (9.5928, -5.1944), 'Francfort': (50.1109, 8.6821),
    'Gagnoa': (6.1319, -5.9506), 'Grand-Bassam': (5.2118, -3.7388), 'Katiola': (8.1333, -5.1000),
    'Korhogo': (9.4580, -5.6296), 'Lagos': (6.5244, 3.3792), 'Libreville': (0.4162, 9.4673),
    'Lomé': (6.1725, 1.2314), 'Londres': (51.5074, -0.1278), 'Lyon': (45.7640, 4.8357),
    'Man': (7.4125, -7.5538), 'Marseille': (43.2965, 5.3698), 'New York': (40.7128, -74.0060),
    'Niamey': (13.5116, 2.1254), 'Odienné': (9.5051, -7.5643), 'Ouagadougou': (12.3714, -1.5197),
    'Paris': (48.8566, 2.3522), 'Pékin': (39.9042, 116.4074), 'Rabat': (34.0209, -6.8416),
    'San-Pédro': (4.7485, -6.6363), 'Sassandra': (4.9500, -6.0833), 'Shanghai': (31.2304, 121.4737),
    'Soubré': (5.7856, -6.6083), 'Séguéla': (7.9611, -6.6731), 'Tunis': (36.8065, 10.1815),
    'Washington': (38.9072, -77.0369), 'Yamoussoukro': (6.8276, -5.2893), 'Yaoundé': (3.8480, 11.5021),
}


def renseigner(apps, schema_editor):
    Ville = apps.get_model('missions', 'Ville')
    for v in Ville.objects.filter(libelle__in=COORDONNEES, latitude__isnull=True):
        lat, lon = COORDONNEES[v.libelle]
        v.latitude, v.longitude = Decimal(str(lat)), Decimal(str(lon))
        v.save(update_fields=['latitude', 'longitude'])


class Migration(migrations.Migration):
    dependencies = [('missions', '0005_cloturemission_dernier_rappel')]
    operations = [
        migrations.AddField('ville', 'latitude', models.DecimalField(max_digits=8, decimal_places=5, null=True, blank=True)),
        migrations.AddField('ville', 'longitude', models.DecimalField(max_digits=8, decimal_places=5, null=True, blank=True)),
        migrations.RunPython(renseigner, migrations.RunPython.noop),
    ]
