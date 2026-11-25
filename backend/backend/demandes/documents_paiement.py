"""
Demande de paiement au format de la société (modèle papier « DEMANDE DE PAIEMENT ») :
en-tête des formulaires qualité, mentions de la société, identification du
demandeur (nom et prénoms, matricule, service), montant en chiffres et en lettres,
motif, bénéficiaire, cadre « À remplir obligatoirement » (repris du règlement),
signatures Demandeur / Chef comptable / Approbation DAF / Signataire / Bénéficiaire.
Sert aux demandes de paiement, de remboursement, aux frais de réception client
(client et lieu en plus) et aux autres types simples avec montant.
"""
from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from api.models import ParametreSysteme
from workflow import moteur
from workflow.erreurs import ErreurMetier
from workflow.models import Tache

from .documents_mission import NOIR, SERIF, SERIF_GRAS, _nom_complet, entete_formulaire
from .lettres import montant_en_lettres
from .pdf import POLICE, _txt

TITRES = {'RMB': 'DEMANDE DE REMBOURSEMENT'}
FORMULAIRES = {'RMB': 'demande_remboursement'}


def _valeur(demande, code):
    v = (demande.donnees or {}).get(code)
    return '' if v in (None, '') else str(v)


def _date_fr(iso):
    try:
        a, m, j = str(iso)[:10].split('-')
        return f"{j}/{m}/{a}"
    except ValueError:
        return str(iso)


def _approbateur(demande, *codes):
    t = (Tache.objects.filter(etape_instance__instance__demande=demande, etape_instance__etape__code__in=codes,
                              decision='approuvee').select_related('traitee_par').order_by('-traitee_le').first())
    if t and t.traitee_par_id:
        return f"{moteur.nom(t.traitee_par)}<br/><font size='7'>approuvé le {timezone.localtime(t.traitee_le):%d/%m/%Y}</font>"
    return ''


def demande_de_paiement(demande, user):
    from tresorerie.services import fmt
    td = demande.type_demande
    if td.famille != 'simple' or not td.avec_montant:
        raise ErreurMetier("Ce document concerne les demandes de paiement, de remboursement et de frais de réception.")
    if not demande.reference:
        raise ErreurMetier("La demande doit d'abord être soumise.")
    param = ParametreSysteme.charger()
    formulaire = (param.formulaires or {}).get(FORMULAIRES.get(td.code, 'demande_paiement'), {})
    societe_court = (param.raison_sociale or 'la société').upper().replace(" CÔTE D'IVOIRE", ' CI').replace(" COTE D'IVOIRE", ' CI')
    u = demande.demandeur
    montant = demande.montant_approuve if demande.montant_approuve is not None else demande.montant_demande
    devise = demande.devise

    # Bénéficiaire : le tiers (demande de paiement) ou le demandeur (remboursement, réception, autres)
    tiers = _valeur(demande, 'beneficiaire')
    beneficiaire = tiers or _nom_complet(u)
    motif = ' — '.join(x for x in [demande.objet, _valeur(demande, 'nature_depense'), _valeur(demande, 'motif'),
                                   _valeur(demande, 'justification')] if x)
    if _valeur(demande, 'reference_initiale'):
        motif += f" (réf. {_valeur(demande, 'reference_initiale')})"
    if demande.demande_parent_id:
        motif += f" — rattachée à {demande.demande_parent.reference}"

    tampon = BytesIO()
    marge = 14 * mm
    doc = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=marge, rightMargin=marge, topMargin=12 * mm, bottomMargin=12 * mm,
                            title=f"{TITRES.get(td.code, 'Demande de paiement').capitalize()} {demande.reference}", author='UbiFlow')
    L = A4[0] - 2 * marge
    n = ParagraphStyle('n', fontName=SERIF, fontSize=10.5, leading=15, textColor=NOIR)
    nb = ParagraphStyle('nb', parent=n, fontName=SERIF_GRAS)
    petit = ParagraphStyle('p', fontName=POLICE, fontSize=8, leading=10.5, textColor=colors.HexColor('#3C3C3C'))
    c = ParagraphStyle('c', parent=n, alignment=TA_CENTER, fontSize=9.5, leading=12)
    h = []

    # En-tête du formulaire, mentions de la société et référence
    h.append(entete_formulaire(param, TITRES.get(td.code, 'DEMANDE DE PAIEMENT')
                               + (f"<br/><font size='9'>{_txt(td.libelle)}</font>" if td.code not in ('PAI', 'RMB') else ''),
                               formulaire, L))
    mentions = '<br/>'.join(x for x in [f"Tél : {param.telephone}" if param.telephone else '',
                                        f"Fax : {param.fax}" if param.fax else '',
                                        f"CDI : {param.centre_impots}" if param.centre_impots else '',
                                        f"Régime d'imposition : {param.regime_imposition}" if param.regime_imposition else ''] if x)
    ref = Table([[Paragraph(f"Réf. : <b>{_txt(demande.reference)}</b>", ParagraphStyle('r', fontName=POLICE, fontSize=9.5, alignment=TA_CENTER))]],
                colWidths=[52 * mm])
    ref.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 0.9, NOIR), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    t = Table([[Paragraph(mentions, petit), ref]], colWidths=[L - 52 * mm, 52 * mm])
    t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0)]))
    h += [Spacer(1, 3 * mm), t, Spacer(1, 4 * mm)]

    # Identification du demandeur
    date_doc = timezone.localtime(demande.approuvee_le or demande.soumise_le).date()
    info = Table([[Paragraph(f"<b>NOM ET PRÉNOMS :</b> {_txt(_nom_complet(u))}", n), Paragraph(f"<b>MATRICULE :</b> {_txt(u.username)}", n),
                   Paragraph(f"<b>DATE :</b> {date_doc:%d/%m/%Y}", n)],
                  [Paragraph(f"<b>SERVICE :</b> {_txt(demande.departement.libelle_service if demande.departement_id else '')}", n), '', '']],
                 colWidths=[L - 92 * mm, 48 * mm, 44 * mm])
    info.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 0.6, NOIR), ('SPAN', (0, 1), (2, 1)), ('LEFTPADDING', (0, 0), (-1, -1), 7),
                              ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
    h += [info, Spacer(1, 5 * mm)]

    # Corps : lignes à gauche, montant et cadre de la comptabilité à droite
    lignes = [('MONTANT EN LETTRES', montant_en_lettres(montant, devise)), ('MOTIF', motif), ('BÉNÉFICIAIRE', beneficiaire)]
    if td.code == 'FRC':
        lignes += [('CLIENT', _valeur(demande, 'client')), ('LIEU', _valeur(demande, 'lieu'))]
        if _valeur(demande, 'date_reception'):
            lignes.append(('DATE DE LA RÉCEPTION', _date_fr(_valeur(demande, 'date_reception'))))
        if _valeur(demande, 'nombre_participants'):
            lignes.append(('PARTICIPANTS', _valeur(demande, 'nombre_participants')))
    gauche = []
    for libelle, valeur in lignes:
        gauche += [Paragraph(f"<b>{libelle} :</b> {_txt(valeur)}", n), Spacer(1, 3 * mm)]

    boite_montant = Table([[Paragraph('MONTANT', c)], [Paragraph(f"<b>{_txt(fmt(montant, devise))}</b>",
                                                                ParagraphStyle('m', parent=nb, alignment=TA_CENTER, fontSize=12.5, leading=16))]],
                          colWidths=[62 * mm], rowHeights=[None, 16 * mm])
    boite_montant.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 0.9, NOIR), ('LINEBELOW', (0, 0), (-1, 0), 0.6, NOIR),
                                       ('VALIGN', (0, 1), (-1, 1), 'MIDDLE')]))
    r = demande.reglements.filter(annule=False).order_by('-date_paiement', '-id').first()
    cheque = r.reference if r and r.mode == 'cheque' else ''
    piece = r.reference if r and r.mode != 'cheque' else ''
    cadre = [('BANQUE', r.get_mode_display() if r else ''), ('N° Chèque', cheque), ('Date', f"{r.date_paiement:%d/%m/%Y}" if r else ''),
             ('Compte à débiter', ''), ('N° de pièce', piece)]
    boite_compta = Table([[Paragraph('<b>À remplir obligatoirement</b>', c)]] +
                         [[Paragraph(f"{lib} : {_txt(v) if v else ''}", ParagraphStyle('k', parent=n, fontSize=9.5, leading=12))] for lib, v in cadre],
                         colWidths=[62 * mm])
    boite_compta.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 0.9, NOIR), ('LINEBELOW', (0, 0), (-1, -2), 0.4, NOIR),
                                      ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
    corps = Table([[gauche, [boite_montant, Spacer(1, 5 * mm), boite_compta]]], colWidths=[L - 68 * mm, 68 * mm])
    corps.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (0, 0), 0),
                               ('ALIGN', (1, 0), (1, 0), 'RIGHT'), ('RIGHTPADDING', (1, 0), (1, 0), 0)]))
    h += [corps, Spacer(1, 9 * mm)]

    # Signatures : noms repris du circuit et du règlement
    chef = _approbateur(demande, 'chef_comptable')
    if not chef and r:
        chef = f"{moteur.nom(r.enregistre_par)}<br/><font size='7'>payé le {r.date_paiement:%d/%m/%Y}</font>"
    sig = Table([[Paragraph(x, c) for x in ('DEMANDEUR', 'CHEF COMPTABLE', 'APPROBATION DAF', 'SIGNATAIRE', 'BÉNÉFICIAIRE')],
                 [Paragraph(_txt(moteur.nom(u)), c), Paragraph(chef, c), Paragraph(_approbateur(demande, 'daf'), c),
                  Paragraph(_approbateur(demande, 'dg'), c), Paragraph('' if tiers else _txt(moteur.nom(u)), c)]],
                colWidths=[L / 5] * 5, rowHeights=[None, 24 * mm])
    sig.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.9, NOIR), ('VALIGN', (0, 1), (-1, 1), 'BOTTOM')]))
    h += [sig, Spacer(1, 2 * mm),
          Paragraph(f"NB : Déchargez et retournez ce document à {_txt(societe_court.title().replace(' Ci', ' CI'))}",
                    ParagraphStyle('nb2', fontName=SERIF, fontSize=10, leading=13))]
    doc.build(h)
    return tampon.getvalue()
