"""
Données initiales du lot 3 : types Mission locale (MLO) et Mission hors pays
(MHP) avec leur circuit, pays et villes, premiers barèmes (per diem des
missions locales, forfait de transport hors pays, taux EUR).

Les distances, tarifs kilométriques, tarifs par ville et per diem hors pays
ne sont pas créés : ils sont saisis par l'administrateur des finances.
"""
from datetime import date
from decimal import Decimal

from django.db import migrations
from django.utils import timezone

TOUTES = ['approuver', 'rejeter', 'retourner']
DATE_EFFET = date(2026, 1, 1)

# (code ISO, libellé, devise usuelle, villes)
PAYS = [
    ('CI', "Côte d'Ivoire", 'XOF', ['Abidjan', 'Yamoussoukro', 'Bouaké', 'Daloa', 'San-Pédro', 'Korhogo', 'Man',
                                    'Gagnoa', 'Abengourou', 'Divo', 'Grand-Bassam', 'Odienné', 'Bondoukou',
                                    'Séguéla', 'Soubré', 'Agboville', 'Dabou', 'Sassandra', 'Katiola', 'Ferkessédougou']),
    ('SN', 'Sénégal', 'XOF', ['Dakar']), ('BF', 'Burkina Faso', 'XOF', ['Ouagadougou']),
    ('ML', 'Mali', 'XOF', ['Bamako']), ('TG', 'Togo', 'XOF', ['Lomé']), ('BJ', 'Bénin', 'XOF', ['Cotonou']),
    ('NE', 'Niger', 'XOF', ['Niamey']), ('GH', 'Ghana', 'GHS', ['Accra']), ('NG', 'Nigeria', 'NGN', ['Lagos']),
    ('CM', 'Cameroun', 'XAF', ['Douala', 'Yaoundé']), ('GA', 'Gabon', 'XAF', ['Libreville']),
    ('MA', 'Maroc', 'MAD', ['Casablanca', 'Rabat']), ('TN', 'Tunisie', 'TND', ['Tunis']),
    ('FR', 'France', 'EUR', ['Paris', 'Lyon', 'Marseille']), ('BE', 'Belgique', 'EUR', ['Bruxelles']),
    ('DE', 'Allemagne', 'EUR', ['Francfort']), ('GB', 'Royaume-Uni', 'GBP', ['Londres']),
    ('US', 'États-Unis', 'USD', ['New York', 'Washington']), ('AE', 'Émirats arabes unis', 'AED', ['Dubaï']),
    ('CN', 'Chine', 'CNY', ['Pékin', 'Shanghai']),
]

TYPES = [
    ('MLO', 'Mission locale', 'locale', 'ri-road-map-line', 10,
     "Déplacement professionnel dans le pays : indemnités journalières, transport, hébergement."),
    ('MHP', 'Mission hors pays', 'hors_pays', 'ri-flight-takeoff-line', 20,
     "Déplacement professionnel à l'étranger : indemnités journalières, forfait de transport, visa, billet."),
]


def creer(apps, schema_editor):
    Pays = apps.get_model('missions', 'Pays')
    Ville = apps.get_model('missions', 'Ville')
    for code, libelle, devise, villes in PAYS:
        pays, _ = Pays.objects.get_or_create(code_iso=code, defaults={'libelle': libelle, 'devise_usuelle': devise})
        for v in villes:
            Ville.objects.get_or_create(libelle=v, pays=pays)

    Categorie = apps.get_model('api', 'Categoriesalarie')
    PerDiem = apps.get_model('baremes', 'PerDiem')
    for libelle, montant in (('Cadre', 25000), ('Non-cadre', 15000)):
        categorie = Categorie.objects.filter(libelle__iexact=libelle).first() or Categorie.objects.create(libelle=libelle)
        if not PerDiem.objects.filter(type_mission='locale', categorie=categorie).exists():
            PerDiem.objects.create(type_mission='locale', categorie=categorie, montant=Decimal(montant), devise='XOF',
                                   date_effet=DATE_EFFET, motif='Barème initial')
    Forfait = apps.get_model('baremes', 'ForfaitTransportHorsPays')
    if not Forfait.objects.exists():
        Forfait.objects.create(montant=Decimal(20000), devise='XOF', date_effet=DATE_EFFET, motif='Barème initial')
    Taux = apps.get_model('baremes', 'TauxChange')
    if not Taux.objects.filter(devise='EUR').exists():
        Taux.objects.create(devise='EUR', taux=Decimal('655.957'), date_effet=DATE_EFFET,
                            motif='Parité fixe EUR / XOF')

    TypeDemande = apps.get_model('demandes', 'TypeDemande')
    TypePiece = apps.get_model('demandes', 'TypePiece')
    ExigencePiece = apps.get_model('demandes', 'ExigencePiece')
    VersionWorkflow = apps.get_model('workflow', 'VersionWorkflow')
    Etape = apps.get_model('workflow', 'Etape')
    RegleDesignation = apps.get_model('workflow', 'RegleDesignation')
    Responsabilite = apps.get_model('api', 'Responsabilite')
    for code, libelle, type_mission, icone, ordre, description in TYPES:
        td, cree = TypeDemande.objects.get_or_create(code=code, defaults={
            'libelle': libelle, 'famille': 'mission', 'prefixe_reference': code, 'icone': icone, 'ordre': ordre,
            'description': description, 'avec_montant': True, 'paiement_fractionne_autorise': True,
            'mode_cloture': 'demandeur', 'rapport_obligatoire': True, 'delai_cloture_jours': 15,
            'annulation_demandeur': ['en_validation', 'a_corriger'], 'parametres': {'type_mission': type_mission}})
        if not cree:
            continue
        if type_mission == 'hors_pays':
            ExigencePiece.objects.create(type_demande=td, type_piece=TypePiece.objects.get(code='invitation'),
                                         moment='soumission', obligatoire=False)
        ExigencePiece.objects.create(type_demande=td, type_piece=TypePiece.objects.get(code='rapport_mission'),
                                     moment='cloture', obligatoire=True)
        v = VersionWorkflow.objects.create(
            type_demande=td, numero=1, etat='publiee', publiee_le=timezone.now(),
            commentaire_version='Circuit initial : N+1, DG, DAF, Chef comptable.')
        n1 = Etape.objects.create(version=v, ordre=1, code='n_plus_1', libelle='Validation du N+1',
                                  actions_autorisees=TOUTES, valideur_introuvable='sauter')
        RegleDesignation.objects.create(etape=n1, mode='relation', relation='n_plus_1')
        for ordre_etape, (code_etape, lib, resp, modifiables) in enumerate((
                ('dg', 'Validation du DG', 'DG', []),
                ('daf', 'Validation du DAF', 'DAF', ['montant_approuve']),
                ('chef_comptable', 'Visa du Chef comptable', 'CHEF_COMPTABLE', [])), start=2):
            e = Etape.objects.create(version=v, ordre=ordre_etape, code=code_etape, libelle=lib,
                                     actions_autorisees=TOUTES, champs_modifiables=modifiables)
            RegleDesignation.objects.create(etape=e, mode='responsabilite',
                                            responsabilite=Responsabilite.objects.get(code=resp))


class Migration(migrations.Migration):

    dependencies = [
        ('missions', '0001_initial'),
        ('baremes', '0001_initial'),
        ('demandes', '0004_demande_parametres_figes_typedemande_parametres'),
        ('workflow', '0002_workflow_frc'),
        ('api', '0005_parametresysteme'),
    ]

    operations = [
        migrations.RunPython(creer, migrations.RunPython.noop),
    ]
