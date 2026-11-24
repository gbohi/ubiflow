"""
Lot 5 : contrôle de la clôture des missions par la comptabilité (paramètre du type,
modifiable) ; les missions déjà approuvées passent « En attente de clôture ».
"""
from django.db import migrations


def appliquer(apps, schema_editor):
    TypeDemande = apps.get_model('demandes', 'TypeDemande')
    Demande = apps.get_model('demandes', 'Demande')
    for td in TypeDemande.objects.filter(famille='mission'):
        td.parametres = {**(td.parametres or {}), 'controle_cloture': (td.parametres or {}).get('controle_cloture', 'comptable')}
        td.save(update_fields=['parametres'])
    Demande.objects.filter(type_demande__mode_cloture='demandeur', statut='approuvee').update(statut='en_attente_cloture')


class Migration(migrations.Migration):
    dependencies = [('missions', '0003_cloturemission'), ('tresorerie', '0003_ann_sur_cloturee')]
    operations = [migrations.RunPython(appliquer, migrations.RunPython.noop)]
