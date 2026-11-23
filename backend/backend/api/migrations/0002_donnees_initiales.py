from django.db import migrations

ROLES = ['super_admin', 'admin', 'gestionnaire', 'employe']
STATUTS = ['Actif', 'Inactif']


def creer_donnees(apps, schema_editor):
    """Rôles de l'application et statuts de base (sans toucher aux existants)."""
    Group = apps.get_model('auth', 'Group')
    for nom in ROLES:
        Group.objects.get_or_create(name=nom)
    Statut = apps.get_model('api', 'Statut')
    for libelle in STATUTS:
        if not Statut.objects.filter(libelle_statut__iexact=libelle).exists():
            Statut.objects.create(libelle_statut=libelle)


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(creer_donnees, migrations.RunPython.noop),
    ]
