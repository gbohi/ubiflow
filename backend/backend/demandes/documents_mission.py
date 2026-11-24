"""
Documents de mission au format de la société (en plus de la fiche PDF de
présentation, demandes/pdf.py) :
- ordre de mission (attestation signée par le DAF) ;
- note de frais de mission (formulaire qualité, ex. ENR-CPT-016 « hors Côte
  d'Ivoire »), remplie avec le prévisionnel tant que la mission n'est pas
  clôturée, puis avec les dépenses réelles déclarées à la clôture.
Informations de la société : Paramètres → Société (ParametreSysteme).
"""
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from api import organisation as org
from api.models import ParametreSysteme
from workflow import moteur
from workflow.erreurs import ErreurMetier

from .pdf import GRAS, POLICE, _qr, _txt

_POLICES = Path(__file__).resolve().parent / 'polices'
try:
    pdfmetrics.registerFont(TTFont('UbiSerif', str(_POLICES / 'DejaVuSerif.ttf')))
    pdfmetrics.registerFont(TTFont('UbiSerif-Bold', str(_POLICES / 'DejaVuSerif-Bold.ttf')))
    SERIF, SERIF_GRAS = 'UbiSerif', 'UbiSerif-Bold'
except Exception:
    SERIF, SERIF_GRAS = 'Times-Roman', 'Times-Bold'

MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre',
        'décembre']
NOIR = colors.HexColor('#1A1A1A')
STATUTS_MISSION_VALIDEE = {'approuvee', 'en_attente_cloture', 'cloturee'}


def _date_longue(d, majuscule_mois=True):
    mois = MOIS[d.month - 1]
    return f"{d.day} {mois.capitalize() if majuscule_mois else mois} {d.year}"


def periode(debut, fin):
    """« du 21 au 25 Juillet 2026 », « du 28 Juillet au 2 Août 2026 », « du 30 Décembre 2026 au 3 Janvier 2027 »."""
    if debut == fin:
        return f"le {_date_longue(debut)}"
    if (debut.year, debut.month) == (fin.year, fin.month):
        return f"du {debut.day} au {_date_longue(fin)}"
    if debut.year == fin.year:
        return f"du {debut.day} {MOIS[debut.month - 1].capitalize()} au {_date_longue(fin)}"
    return f"du {_date_longue(debut)} au {_date_longue(fin)}"


def _jour(iso):
    from missions.calcul import _date_heure
    return timezone.localtime(_date_heure(iso)).date()


def _dates_mission(demande, m):
    """Dates réelles déclarées à la clôture, sinon dates prévues."""
    c = getattr(demande, 'cloture', None) if hasattr(demande, 'cloture') else None
    if c is not None and c.depart_reel and c.retour_reel:
        return c.depart_reel, c.retour_reel
    return _jour(m['depart_le']), _jour(m['retour_le'])


def _logo(param, largeur, hauteur):
    """Logo téléversé (Paramètres → Société), sinon la raison sociale en toutes lettres."""
    if param.logo:
        try:
            img = Image(param.logo.path)
            ratio = img.imageWidth / img.imageHeight
            w, h = (hauteur * ratio, hauteur) if hauteur * ratio <= largeur else (largeur, largeur / ratio)
            img.drawWidth, img.drawHeight = w, h
            img.hAlign = 'LEFT'
            return img
        except Exception:
            pass
    return Paragraph(f'<font color="#3C3C3C"><b>{_txt(param.raison_sociale or "Société")}</b></font>',
                     ParagraphStyle('lg', fontName=GRAS, fontSize=14, leading=17))


def _nom_complet(u):
    return f"{(u.nom or '').upper()} {(u.prenom or '').upper()}".strip() or u.username


def _signataire(demande, param):
    regle = (param.formulaires or {}).get('ordre_mission', {})
    code = regle.get('responsabilite_signataire') or 'DAF'
    d = timezone.localtime(demande.approuvee_le).date() if demande.approuvee_le else timezone.localdate()
    personnes = org.titulaires(code, d)
    titre = regle.get('titre_signataire') or 'Le Directeur Administratif & Financier'
    return (personnes[0] if personnes else None), titre


def _controler(demande):
    if demande.type_demande.famille != 'mission':
        raise ErreurMetier("Ce document ne concerne que les missions.")
    if not (demande.donnees or {}).get('mission'):
        raise ErreurMetier("La mission n'est pas renseignée.")


# ═══════════════════════════════════════════════════════════════
# ORDRE DE MISSION
# ═══════════════════════════════════════════════════════════════

def ordre_de_mission(demande, user):
    _controler(demande)
    if demande.statut not in STATUTS_MISSION_VALIDEE:
        raise ErreurMetier("L'ordre de mission est délivré une fois la mission approuvée.")
    param = ParametreSysteme.charger()
    m = demande.donnees['mission']
    tampon = BytesIO()
    marge = 22 * mm
    doc = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=marge, rightMargin=marge, topMargin=14 * mm,
                            bottomMargin=16 * mm, title=f"Ordre de mission {demande.reference}", author='UbiFlow')
    largeur = A4[0] - 2 * marge
    corps = ParagraphStyle('c', fontName=SERIF, fontSize=12.5, leading=19, textColor=NOIR, alignment=TA_JUSTIFY,
                           firstLineIndent=12 * mm)
    simple = ParagraphStyle('s', parent=corps, firstLineIndent=0, alignment=0)
    h = [_logo(param, 70 * mm, 22 * mm), Spacer(1, 26 * mm)]

    titre = Table([[Paragraph('ORDRE DE MISSION', ParagraphStyle('t', fontName=SERIF_GRAS, fontSize=22, leading=26,
                                                                  alignment=TA_CENTER, textColor=NOIR))]],
                  colWidths=[118 * mm])
    titre.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 1.2, NOIR), ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#E6E6E6')),
                               ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 7)]))
    h += [titre, Spacer(1, 22 * mm)]

    signataire, titre_signataire = _signataire(demande, param)
    nom_sign = _nom_complet(signataire) if signataire else '…………………………'
    fonction = titre_signataire.replace('Le ', '', 1) if titre_signataire.lower().startswith('le ') else titre_signataire
    societe = '<br/>'.join(x for x in [f"Société {_txt((param.raison_sociale or '').upper())}" if param.raison_sociale else '',
                                       _txt(param.adresse)] if x and x != '—')
    t = Table([[Paragraph('Nous soussigné :', simple),
                Paragraph(f"{_txt(nom_sign)}, {_txt(fonction)} de la {societe}", simple)]],
              colWidths=[42 * mm, largeur - 42 * mm])
    t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))
    h += [t, Spacer(1, 14 * mm)]

    u = demande.demandeur
    civilite = {'M': 'Monsieur', 'Mme': 'Madame'}.get(u.civilite, 'Monsieur/Madame')
    destination = (m.get('ville_destination_libelle') or '').upper()
    if (demande.type_demande.parametres or {}).get('type_mission') == 'hors_pays' and m.get('pays_destination_libelle'):
        destination += f" ({m['pays_destination_libelle']})"
    objet = (demande.objet or m.get('motif') or '').strip().rstrip('.')
    texte = (f"Attestons par la présente que {civilite} <b>{_txt(_nom_complet(u))}</b>, effectuera une mission à "
             f"{_txt(destination)} {periode(_jour(m['depart_le']), _jour(m['retour_le']))} dans le cadre de : "
             f"{_txt(objet[:1].lower() + objet[1:] if objet else '')}.")
    h += [Paragraph(texte, corps), Spacer(1, 10 * mm),
          Paragraph("En foi de quoi, le présent ordre de mission lui est délivré, pour servir et valoir ce que de droit.", corps),
          Spacer(1, 24 * mm)]
    fait_le = timezone.localtime(demande.approuvee_le).date() if demande.approuvee_le else timezone.localdate()
    h += [Paragraph(f"Fait à {_txt(param.ville or '…………')}, le {_date_longue(fait_le)}", simple), Spacer(1, 18 * mm),
          Paragraph(_txt(titre_signataire.upper()), simple), Spacer(1, 22 * mm)]

    # Validation électronique (traçabilité)
    validation = Table([[Paragraph(f"Mission <b>{_txt(demande.reference)}</b> approuvée électroniquement dans UbiFlow le "
                                   f"{timezone.localtime(demande.approuvee_le):%d/%m/%Y à %H:%M}." if demande.approuvee_le else '',
                                   ParagraphStyle('v', fontName=POLICE, fontSize=7.5, leading=10, textColor=colors.HexColor('#5A7090'))),
                         _qr(f"UbiFlow {demande.reference} · ordre de mission · {_nom_complet(u)}", 16 * mm)]],
                       colWidths=[largeur - 20 * mm, 20 * mm])
    validation.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'BOTTOM'), ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                    ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
    h.append(validation)
    doc.build(h)
    return tampon.getvalue()


# ═══════════════════════════════════════════════════════════════
# NOTE DE FRAIS DE MISSION
# ═══════════════════════════════════════════════════════════════

def lignes_note_frais(demande):
    """
    Montants par rubrique du formulaire, en devise de référence. Dépenses réelles
    déclarées à la clôture si elles existent (lot 5), sinon prévisionnel figé.
    """
    reel = ((demande.parametres_figes or {}).get('cloture') or {}).get('note_frais')
    if reel:
        return {**reel, 'source': 'reel'}
    calcul = demande.version_courante.calcul if demande.version_courante_id else {}
    r = {'hotel': Decimal('0'), 'transport': Decimal('0'), 'indemnites': Decimal('0'), 'telephone': Decimal('0'),
         'divers': Decimal('0'), 'reception': Decimal('0'), 'detaxe': Decimal('0'), 'a_refacturer': Decimal('0'),
         'divers_detail': [], 'jours': None, 'tarif_jour': None, 'devise_tarif': '', 'source': 'previsionnel'}
    for l in (calcul or {}).get('lignes', []):
        montant = Decimal(l.get('montant_ref') or '0')
        if l['rubrique'] == 'per_diem':
            r['indemnites'] += montant
            r['jours'], r['tarif_jour'], r['devise_tarif'] = l.get('base'), l.get('tarif'), l.get('devise')
        elif l['rubrique'] == 'hebergement':
            r['hotel'] += montant
        elif l['rubrique'] == 'transport':
            r['transport'] += montant
        else:  # visa, billet d'avion, autres frais
            r['divers'] += montant
            r['divers_detail'].append(l['libelle'])
    return r


def note_de_frais(demande, user):
    from tresorerie.services import fmt
    _controler(demande)
    param = ParametreSysteme.charger()
    hors_pays = (demande.type_demande.parametres or {}).get('type_mission') == 'hors_pays'
    pays = param.pays or 'Côte d\'Ivoire'
    formulaire = (param.formulaires or {}).get('note_frais_hors_pays' if hors_pays else 'note_frais_pays', {})
    societe_court = (param.raison_sociale or 'la société').upper().replace("CÔTE D'IVOIRE", 'CI').replace(" COTE D'IVOIRE", '-CI')
    societe_court = societe_court.replace(' CI', '-CI')
    ref = demande.devise_reference or param.devise_reference
    v = lignes_note_frais(demande)
    D = lambda k: Decimal(str(v.get(k) or 0))
    total_charges = D('hotel') + D('transport') + D('indemnites') + D('telephone') + D('divers') + D('reception') - D('detaxe')
    total_refacturer = D('a_refacturer')
    total = total_charges + total_refacturer
    # Avance reçue : mission et frais complémentaires payés (calculée à la clôture), sinon le payé de la mission
    avance = Decimal(str(v['avance'])) if v.get('source') == 'reel' and v.get('avance') is not None \
        else Decimal(str(demande.montant_paye or 0))
    a_rembourser = max(avance - total, Decimal('0'))   # le salarié rend la différence à la société
    a_reverser = max(total - avance, Decimal('0'))     # la société doit la différence au salarié

    tampon = BytesIO()
    marge = 14 * mm
    doc = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=marge, rightMargin=marge, topMargin=12 * mm,
                            bottomMargin=12 * mm, title=f"Note de frais {demande.reference}", author='UbiFlow')
    L = A4[0] - 2 * marge
    n = ParagraphStyle('n', fontName=POLICE, fontSize=9, leading=12, textColor=NOIR)
    nb = ParagraphStyle('nb', parent=n, fontName=GRAS)
    c = ParagraphStyle('c', parent=n, alignment=TA_CENTER)
    d = ParagraphStyle('d', parent=n, alignment=TA_RIGHT)
    db = ParagraphStyle('db', parent=d, fontName=GRAS)
    ligne = 0.6
    h = []

    # En-tête du formulaire
    titre = f"NOTE DE FRAIS DE MISSION<br/>{'HORS' if hors_pays else 'EN'} {_txt(pays.upper())}"
    ident = (f"Identification : <b>{_txt(formulaire.get('identification') or '—')}</b><br/>"
             f"Version : <b>{_txt(formulaire.get('version') or '—')}</b><br/>Date : <b>{_txt(formulaire.get('date') or '—')}</b><br/>"
             f"Page : 1/1")
    t = Table([[_logo(param, 48 * mm, 13 * mm), Paragraph(titre, ParagraphStyle('t', fontName=SERIF_GRAS, fontSize=12.5,
                                                                              leading=16, alignment=TA_CENTER)),
                Paragraph(ident, ParagraphStyle('i', fontName=SERIF, fontSize=8.6, leading=11.5))]],
              colWidths=[56 * mm, L - 56 * mm - 52 * mm, 52 * mm])
    t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.9, NOIR), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                           ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
    h += [t, Spacer(1, 6 * mm)]

    # Identification du salarié
    u = demande.demandeur
    m = demande.donnees.get('mission', {})
    date_note = timezone.localtime(demande.cloturee_le).date() if demande.cloturee_le else timezone.localdate()
    objet = f"{demande.objet} — {m.get('ville_destination_libelle', '')}" + \
            (f" ({m.get('pays_destination_libelle')})" if hors_pays and m.get('pays_destination_libelle') else '') + \
            f", {periode(*_dates_mission(demande, m))} — réf. {demande.reference}"
    info = Table([[Paragraph(f"<b>NOM :</b> {_txt(_nom_complet(u))}", n), Paragraph(f"<b>DATE :</b> {date_note:%d/%m/%Y}", n)],
                  [Paragraph(f"<b>SERVICE :</b> {_txt(demande.departement.libelle_service if demande.departement_id else '')}", n), ''],
                  [Paragraph(f"<b>OBJET :</b> {_txt(objet)}", n), '']], colWidths=[L - 50 * mm, 50 * mm])
    info.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), ligne, NOIR), ('SPAN', (0, 1), (1, 1)), ('SPAN', (0, 2), (1, 2)),
                              ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                              ('LEFTPADDING', (0, 0), (-1, -1), 7)]))
    h += [info]

    # Tableau des dépenses
    M = lambda x: fmt(x, ref) if x else ''
    ij = 'INDEMNITÉS JOURNALIÈRES :<br/>Nbre de jours : ' + (
        f"{v['jours']} à {fmt(Decimal(str(v['tarif_jour'])), v.get('devise_tarif') or ref)}" if v.get('jours') else '……… à ………')
    detail = v.get('divers_detail') or []
    detail = ' ; '.join(detail) if isinstance(detail, list) else str(detail)
    divers = 'DIVERS :' + (f"<br/><font size='7.5'>{_txt(detail)}</font>" if detail else '')
    lignes = [
        ['DESCRIPTION', 'MONTANT', 'CONTRÔLE'],
        [f"CHARGES {_txt(societe_court)}", '', ''],
        ["FRAIS D'HÔTEL<br/>Forfait petit déjeuner", M(D('hotel')), ''],
        ['TRANSPORT : location de véhicule', M(D('transport')), ''],
        [ij, M(D('indemnites')), ''],
        ['FRAIS TÉLÉPHONE :', M(D('telephone')), ''],
        [f"{divers}<br/><br/>RÉCEPTION :", f"{M(D('divers'))}<br/><br/>{M(D('reception'))}", ''],
        ['DÉTAXE (à reverser) :', M(D('detaxe')), ''],
        [f"TOTAL CHARGES {_txt(societe_court)} :", fmt(total_charges, ref), ''],
        ['AUTRE À REFACTURER', '', ''],
        ['DIVERS À PRÉCISER :' + (f"<br/>{_txt(v.get('a_refacturer_detail'))}" if v.get('a_refacturer_detail') else ''),
         M(total_refacturer), ''],
        ['TOTAL À REFACTURER :', fmt(total_refacturer, ref), ''],
        ['TOTAL DÉPENSES :', fmt(total, ref), ''],
        ['AVANCE REÇUE :', fmt(avance, ref), ''],
        [f"SOLDE À REMBOURSER À {_txt(societe_court)} :", M(a_rembourser), ''],
        ['SOLDE À REVERSER :', M(a_reverser), ''],
    ]
    gras = {0, 1, 8, 9, 11, 12, 13, 14, 15}
    data = []
    for i, (a, b, cc) in enumerate(lignes):
        if i == 0:
            data.append([Paragraph(a, c), Paragraph(b, c), Paragraph(cc, c)])
        else:
            data.append([Paragraph(a, nb if i in gras else n), Paragraph(b, db if i in gras else d), Paragraph(cc, d)])
    hauteurs = [None, None, 15 * mm, 14 * mm, 16 * mm, 13 * mm, 24 * mm, 10 * mm, None, None, 18 * mm, None, None, None,
                None, None]
    tab = Table(data, colWidths=[L * 0.36, L * 0.34, L * 0.30], rowHeights=hauteurs)
    tab.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), ligne, NOIR), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                             ('SPAN', (0, 1), (-1, 1)), ('SPAN', (0, 9), (-1, 9)),
                             ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
    h += [tab, Spacer(1, 7 * mm)]

    # Signatures : noms des valideurs du circuit (DAF, DG) quand ils ont approuvé
    def valideur(code):
        from workflow.models import Tache
        t = (Tache.objects.filter(etape_instance__instance__demande=demande, etape_instance__etape__code=code,
                                  decision='approuvee').select_related('traitee_par').order_by('-traitee_le').first())
        return f"{moteur.nom(t.traitee_par)}<br/><font size='7'>approuvé le {timezone.localtime(t.traitee_le):%d/%m/%Y}</font>" \
            if t and t.traitee_par_id else ''
    sig = Table([[Paragraph('DEMANDEUR', c), Paragraph('DAF', c), Paragraph('DIRECTEUR GÉNÉRAL', c)],
                 [Paragraph(_txt(moteur.nom(u)), c), Paragraph(valideur('daf'), c), Paragraph(valideur('dg'), c)]],
                colWidths=[L / 3] * 3, rowHeights=[None, 20 * mm])
    sig.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), ligne, NOIR), ('VALIGN', (0, 1), (-1, 1), 'BOTTOM'),
                             ('FONTNAME', (0, 0), (-1, 0), SERIF)]))
    h.append(sig)
    if v.get('source') != 'reel':
        h += [Spacer(1, 3 * mm), Paragraph("Établie à partir du prévisionnel de la demande : les dépenses réelles sont "
                                           "déclarées à la clôture de la mission. Montants en " + _txt(ref) + '.',
                                           ParagraphStyle('p', fontName=POLICE, fontSize=7.5, leading=10,
                                                          textColor=colors.HexColor('#5A7090')))]
    doc.build(h)
    return tampon.getvalue()
