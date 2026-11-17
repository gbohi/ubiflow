from django.db import migrations, models


def recompter(apps, schema_editor):
    """Relevés déjà émis : les desserts (suppléments) ne comptent plus comme des repas."""
    Facture = apps.get_model('api', 'FacturePrestataire')
    Ligne = apps.get_model('api', 'LigneFacturePrestataire')
    for f in Facture.objects.all():
        n = Ligne.objects.filter(facture=f, commande__commande_principale__isnull=False).count()
        if n:
            Facture.objects.filter(pk=f.pk).update(nb_supplements=n, nb_repas=max(f.nb_repas - n, 0))


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0055_jours_ouverture_agences'),
    ]

    operations = [
        migrations.AddField(
            model_name='factureprestataire',
            name='nb_supplements',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(recompter, migrations.RunPython.noop),
    ]
