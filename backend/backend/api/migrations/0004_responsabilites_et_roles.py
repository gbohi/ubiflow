from django.db import migrations

# (code, libellé, portée, système)
RESPONSABILITES = [
    ('DG', 'Directeur général', 'globale', False),
    ('DAF', 'Directeur administratif et financier', 'globale', False),
    ('CHEF_COMPTABLE', 'Chef comptable', 'globale', False),
    ('RESP_RH', 'Responsable RH', 'globale', False),
    ('RESP_DEPARTEMENT', 'Responsable de département', 'departement', True),
]
ROLES = ['admin_workflow', 'admin_finances', 'comptable', 'direction', 'controleur']


def creer(apps, schema_editor):
    Responsabilite = apps.get_model('api', 'Responsabilite')
    for code, libelle, portee, systeme in RESPONSABILITES:
        Responsabilite.objects.get_or_create(
            code=code, defaults={'libelle': libelle, 'portee': portee, 'systeme': systeme})
    Group = apps.get_model('auth', 'Group')
    for nom in ROLES:
        Group.objects.get_or_create(name=nom)


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0003_organisation'),
    ]

    operations = [
        migrations.RunPython(creer, migrations.RunPython.noop),
    ]
