from django.db import migrations
from django.utils import timezone

TOUTES = ['approuver', 'rejeter', 'retourner']


def creer(apps, schema_editor):
    TypeDemande = apps.get_model('demandes', 'TypeDemande')
    VersionWorkflow = apps.get_model('workflow', 'VersionWorkflow')
    Etape = apps.get_model('workflow', 'Etape')
    RegleDesignation = apps.get_model('workflow', 'RegleDesignation')
    Responsabilite = apps.get_model('api', 'Responsabilite')
    frc = TypeDemande.objects.filter(code='FRC').first()
    if frc is None or VersionWorkflow.objects.filter(type_demande=frc).exists():
        return
    v = VersionWorkflow.objects.create(type_demande=frc, numero=1, etat='publiee', publiee_le=timezone.now(),
                                       commentaire_version='Circuit initial : N+1, DAF, puis DG au-delà de 1 000 000.')
    n1 = Etape.objects.create(version=v, ordre=1, code='n_plus_1', libelle='Validation du N+1', actions_autorisees=TOUTES)
    RegleDesignation.objects.create(etape=n1, mode='relation', relation='n_plus_1')
    daf = Etape.objects.create(version=v, ordre=2, code='daf', libelle='Validation du DAF', actions_autorisees=TOUTES,
                               champs_modifiables=['montant_approuve'])
    RegleDesignation.objects.create(etape=daf, mode='responsabilite',
                                    responsabilite=Responsabilite.objects.get(code='DAF'))
    dg = Etape.objects.create(version=v, ordre=3, code='dg', libelle='Validation du DG', actions_autorisees=TOUTES,
                              condition={'et': [{'champ': 'montant_demande_ref', 'op': '>', 'valeur': 1000000}]})
    RegleDesignation.objects.create(etape=dg, mode='responsabilite',
                                    responsabilite=Responsabilite.objects.get(code='DG'))


class Migration(migrations.Migration):

    dependencies = [
        ('workflow', '0001_initial'),
        ('demandes', '0003_donnees_initiales'),
        ('api', '0004_responsabilites_et_roles'),
    ]

    operations = [
        migrations.RunPython(creer, migrations.RunPython.noop),
    ]
