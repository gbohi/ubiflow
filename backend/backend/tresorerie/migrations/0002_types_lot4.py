"""
Types du lot 4 et leur circuit initial :
- PAI demande de paiement (tiers), RMB remboursement de frais avancés,
- FCM frais complémentaires de mission (rattachée à une mission approuvée),
- ANN demande d'annulation (rattachée à une demande approuvée, §4.3).
Rôle « comptable » : déjà créé au lot 1.
"""
from django.db import migrations
from django.utils import timezone

TOUTES = ['approuver', 'rejeter', 'retourner']
STATUTS_PARENT = ['approuvee', 'en_attente_cloture']  # + 'cloturee' pour ANN (migration 0003)

# code, libellé, famille, icône, ordre, description, avec_montant, fractionné, paramètres,
# champs (code, libellé, nature, obligatoire, sensible, options, aide),
# pièces (code, moment, obligatoire), circuit (code, libellé, responsabilité | None = N+1, champs modifiables, condition)
TYPES = [
    ('PAI', 'Demande de paiement', 'simple', 'ri-bank-card-line', 40,
     "Paiement à un tiers (fournisseur, prestataire) sur facture ou devis.", True, True, {},
     [('beneficiaire', 'Bénéficiaire', 'texte', True, True, [], 'Fournisseur, prestataire…'),
      ('mode_paiement', 'Mode de paiement souhaité', 'liste', True, False,
       ['Virement', 'Chèque', 'Espèces', 'Mobile money'], ''),
      ('reference_initiale', 'Référence de la facture ou du devis', 'texte', False, False, [], ''),
      ('motif', 'Motif', 'texte_long', True, False, [], 'Objet de la dépense, intérêt pour la société')],
     [('facture', 'soumission', False), ('justificatif_paiement', 'paiement', True)],
     [('n_plus_1', 'Validation du N+1', None, [], None),
      ('daf', 'Validation du DAF', 'DAF', ['montant_approuve'], None),
      ('dg', 'Validation du DG', 'DG', [], {'et': [{'champ': 'montant_demande_ref', 'op': '>', 'valeur': 1000000}]})]),
    ('RMB', 'Demande de remboursement', 'simple', 'ri-refund-2-line', 50,
     "Remboursement de frais avancés par le salarié pour le compte de la société.", True, False, {},
     [('date_depense', 'Date de la dépense', 'date', True, True, [], ''),
      ('nature_depense', 'Nature de la dépense', 'texte', True, False, [], 'Fournitures, carburant, taxi…'),
      ('justification', 'Justification', 'texte_long', True, False, [], '')],
     [('justificatif_depense', 'soumission', True)],
     [('n_plus_1', 'Validation du N+1', None, [], None),
      ('daf', 'Validation du DAF', 'DAF', ['montant_approuve'], None)]),
    ('FCM', 'Frais complémentaires de mission', 'simple', 'ri-add-box-line', 25,
     "Dépenses supplémentaires d'une mission approuvée (prolongation, imprévus).", True, True,
     {'parent': {'types': ['MLO', 'MHP'], 'statuts': STATUTS_PARENT}, 'complement': True},
     [('motif', 'Motif des frais complémentaires', 'texte_long', True, True, [], '')],
     [('justificatif_depense', 'soumission', True)],
     [('n_plus_1', 'Validation du N+1', None, [], None),
      ('daf', 'Validation du DAF', 'DAF', ['montant_approuve'], None)]),
    ('ANN', "Demande d'annulation", 'annulation', 'ri-close-circle-line', 90,
     "Annulation d'une demande déjà approuvée ; si elle a été payée, le montant est à reverser.", False, False,
     {'parent': {'types': '*', 'statuts': STATUTS_PARENT, 'unique_en_cours': True}},
     [('motif', "Motif de l'annulation", 'texte_long', True, False, [], '')],
     [],
     [('n_plus_1', 'Validation du N+1', None, [], None),
      ('daf', 'Validation du DAF', 'DAF', [], None)]),
]


def creer(apps, schema_editor):
    TypeDemande = apps.get_model('demandes', 'TypeDemande')
    ChampType = apps.get_model('demandes', 'ChampType')
    TypePiece = apps.get_model('demandes', 'TypePiece')
    ExigencePiece = apps.get_model('demandes', 'ExigencePiece')
    VersionWorkflow = apps.get_model('workflow', 'VersionWorkflow')
    Etape = apps.get_model('workflow', 'Etape')
    RegleDesignation = apps.get_model('workflow', 'RegleDesignation')
    Responsabilite = apps.get_model('api', 'Responsabilite')
    for (code, libelle, famille, icone, ordre, description, avec_montant, fractionne, parametres,
         champs, pieces, circuit) in TYPES:
        td, cree = TypeDemande.objects.get_or_create(code=code, defaults={
            'libelle': libelle, 'famille': famille, 'prefixe_reference': code, 'icone': icone, 'ordre': ordre,
            'description': description, 'avec_montant': avec_montant, 'paiement_fractionne_autorise': fractionne,
            'mode_cloture': 'automatique', 'annulation_demandeur': ['en_validation', 'a_corriger'],
            'parametres': parametres})
        if not cree:
            continue
        for i, (c, lib, nature, obligatoire, sensible, options, aide) in enumerate(champs, start=1):
            ChampType.objects.create(type_demande=td, code=c, libelle=lib, nature=nature, obligatoire=obligatoire,
                                     sensible=sensible, options=options, aide=aide, ordre=i)
        for piece, moment, obligatoire in pieces:
            ExigencePiece.objects.create(type_demande=td, type_piece=TypePiece.objects.get(code=piece), moment=moment,
                                         obligatoire=obligatoire)
        v = VersionWorkflow.objects.create(type_demande=td, numero=1, etat='publiee', publiee_le=timezone.now(),
                                           commentaire_version='Circuit initial.')
        for i, (c, lib, resp, modifiables, condition) in enumerate(circuit, start=1):
            e = Etape.objects.create(version=v, ordre=i, code=c, libelle=lib, actions_autorisees=TOUTES,
                                     champs_modifiables=modifiables, condition=condition,
                                     valideur_introuvable='sauter' if resp is None else 'bloquer')
            if resp is None:
                RegleDesignation.objects.create(etape=e, mode='relation', relation='n_plus_1')
            else:
                RegleDesignation.objects.create(etape=e, mode='responsabilite',
                                                responsabilite=Responsabilite.objects.get(code=resp))


class Migration(migrations.Migration):

    dependencies = [
        ('tresorerie', '0001_initial'),
        ('demandes', '0005_alter_typedemande_famille'),
        ('workflow', '0003_alter_action_type'),
        ('missions', '0002_donnees_initiales'),
    ]

    operations = [
        migrations.RunPython(creer, migrations.RunPython.noop),
    ]
