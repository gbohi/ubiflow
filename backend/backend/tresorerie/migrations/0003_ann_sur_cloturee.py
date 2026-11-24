"""Décision 2 : une demande clôturée peut faire l'objet d'une demande d'annulation (reversement du payé)."""
from django.db import migrations


def ajouter(apps, schema_editor):
    TypeDemande = apps.get_model('demandes', 'TypeDemande')
    for td in TypeDemande.objects.filter(famille='annulation'):
        p = dict(td.parametres or {})
        parent = dict(p.get('parent') or {})
        statuts = list(parent.get('statuts') or ['approuvee', 'en_attente_cloture'])
        if 'cloturee' not in statuts:
            statuts.append('cloturee')
        parent['statuts'] = statuts
        p['parent'] = parent
        td.parametres = p
        td.save(update_fields=['parametres'])


class Migration(migrations.Migration):
    dependencies = [('tresorerie', '0002_types_lot4')]
    operations = [migrations.RunPython(ajouter, migrations.RunPython.noop)]
