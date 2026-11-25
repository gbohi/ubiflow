"""Remplace les libellés techniques « Modele object (n) » du journal par le libellé lisible de l'objet."""
from django.apps import apps as apps_globales
from django.db import migrations


def renommer(apps, schema_editor):
    Journal = apps.get_model('audit', 'JournalActivite')
    for ligne in Journal.objects.filter(objet_libelle__contains=' object ('):
        try:
            modele = apps_globales.get_model(ligne.objet_type)
            objet = modele.objects.filter(pk=ligne.objet_id).first()
        except (LookupError, ValueError):
            objet = None
        if objet is not None:
            ligne.objet_libelle = str(objet)[:255]
            ligne.save(update_fields=['objet_libelle'])


class Migration(migrations.Migration):
    dependencies = [('audit', '0001_initial')]
    operations = [migrations.RunPython(renommer, migrations.RunPython.noop)]
