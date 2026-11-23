from django.db import migrations

TYPES_PIECES = [
    ('ordre_mission', 'Ordre de mission'), ('invitation', 'Invitation'), ('facture', 'Facture'),
    ('recu', 'Reçu'), ('billet', 'Billet de transport'), ('rapport_mission', 'Rapport de mission'),
    ('justificatif_depense', 'Justificatif de dépense'), ('justificatif_paiement', 'Justificatif de paiement'),
    ('document_comptable', 'Document comptable'), ('proforma', 'Facture proforma / devis'),
    ('autre', 'Autre document'),
]

# Frais de réception client : (code, libellé, nature, obligatoire, sensible, condition, aide)
CHAMPS_FRC = [
    ('date_reception', 'Date de la réception', 'date', True, True, False, ''),
    ('client', 'Client ou entreprise concernée', 'texte', True, False, False, ''),
    ('nombre_participants', 'Nombre de participants', 'entier', True, True, True, 'Collaborateurs et invités'),
    ('lieu', 'Lieu', 'texte', True, False, False, 'Restaurant, hôtel…'),
    ('justification', 'Justification', 'texte_long', True, False, False,
     'Intérêt commercial de la réception'),
]


def creer(apps, schema_editor):
    TypePiece = apps.get_model('demandes', 'TypePiece')
    for code, libelle in TYPES_PIECES:
        TypePiece.objects.get_or_create(code=code, defaults={'libelle': libelle})

    TypeDemande = apps.get_model('demandes', 'TypeDemande')
    ChampType = apps.get_model('demandes', 'ChampType')
    ExigencePiece = apps.get_model('demandes', 'ExigencePiece')
    frc, cree = TypeDemande.objects.get_or_create(code='FRC', defaults={
        'libelle': 'Frais de réception client', 'famille': 'simple', 'prefixe_reference': 'FRC',
        'icone': 'ri-restaurant-line', 'ordre': 30, 'avec_montant': True, 'paiement_fractionne_autorise': False,
        'mode_cloture': 'automatique', 'annulation_demandeur': ['en_validation', 'a_corriger'],
        'description': "Prise en charge d'une réception (repas, collation…) organisée pour un client.",
    })
    if cree:
        for i, (code, libelle, nature, obligatoire, sensible, condition, aide) in enumerate(CHAMPS_FRC, start=1):
            ChampType.objects.create(type_demande=frc, code=code, libelle=libelle, nature=nature, ordre=i,
                                     obligatoire=obligatoire, sensible=sensible,
                                     utilisable_en_condition=condition, aide=aide)
        ExigencePiece.objects.create(type_demande=frc, type_piece=TypePiece.objects.get(code='proforma'),
                                     moment='soumission', obligatoire=False)


class Migration(migrations.Migration):

    dependencies = [
        ('demandes', '0002_initial'),
    ]

    operations = [
        migrations.RunPython(creer, migrations.RunPython.noop),
    ]
