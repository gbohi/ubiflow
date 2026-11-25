"""
Fiche PDF de présentation d'une demande (A4 portrait) : en-tête UbiFlow,
statut, montants, demandeur, contenu, mission et récapitulatif des frais,
circuit de validation, paiements, pièces jointes, commentaires.
"""
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as canvas_module
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from workflow import moteur

NAVY = colors.HexColor('#05253E')
NAVY2 = colors.HexColor('#0F3A6E')
VERT = colors.HexColor('#2FB46C')
GRIS = colors.HexColor('#5A7090')
FOND = colors.HexColor('#F4F7FB')
BORD = colors.HexColor('#DDE4EE')
COULEURS_STATUT = {
    'brouillon': ('#EEF1F5', '#5A7090'), 'en_validation': ('#E8F0FD', '#0F3A6E'), 'a_corriger': ('#FEF4E4', '#9A6510'),
    'rejetee': ('#FDE8E4', '#C4381F'), 'approuvee': ('#EAFBF1', '#1C7F45'), 'en_attente_cloture': ('#FEF4E4', '#9A6510'),
    'cloturee': ('#E7ECF3', '#092440'), 'annulee': ('#EEF1F5', '#5A7090'),
}
DECISIONS = {'approuvee': ('Approuvée', '#1C7F45'), 'rejetee': ('Rejetée', '#C4381F'), 'retournee': ('Retournée', '#9A6510')}

_POLICES = Path(__file__).resolve().parent / 'polices'
try:
    pdfmetrics.registerFont(TTFont('UbiSans', str(_POLICES / 'DejaVuSans.ttf')))
    pdfmetrics.registerFont(TTFont('UbiSans-Bold', str(_POLICES / 'DejaVuSans-Bold.ttf')))
    pdfmetrics.registerFontFamily('UbiSans', normal='UbiSans', bold='UbiSans-Bold', italic='UbiSans', boldItalic='UbiSans-Bold')
    POLICE, GRAS = 'UbiSans', 'UbiSans-Bold'
except Exception:  # police absente : polices standard (accents latins seulement)
    POLICE, GRAS = 'Helvetica', 'Helvetica-Bold'

S_NORMAL = ParagraphStyle('n', fontName=POLICE, fontSize=8.6, leading=11.5, textColor=NAVY)
S_PETIT = ParagraphStyle('p', parent=S_NORMAL, fontSize=7.4, leading=9.5, textColor=GRIS)
S_LIBELLE = ParagraphStyle('l', parent=S_PETIT, fontSize=7.6)
S_VALEUR = ParagraphStyle('v', parent=S_NORMAL, fontName=GRAS)
S_TITRE = ParagraphStyle('t', fontName=GRAS, fontSize=17, leading=21, textColor=NAVY)
S_SECTION = ParagraphStyle('s', fontName=GRAS, fontSize=10.5, leading=13, textColor=NAVY)
S_TUILE_LIB = ParagraphStyle('tl', parent=S_PETIT, alignment=1)
S_TUILE_VAL = ParagraphStyle('tv', fontName=GRAS, fontSize=11, leading=14, textColor=NAVY, alignment=1)
S_DROITE = ParagraphStyle('d', parent=S_NORMAL, alignment=TA_RIGHT)
S_DROITE_GRAS = ParagraphStyle('dg', parent=S_DROITE, fontName=GRAS)
S_ENTETE = ParagraphStyle('e', fontName=GRAS, fontSize=7.6, leading=9.5, textColor=colors.white)


def _txt(v):
    if v is None or v == '':
        return '—'
    return (str(v).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            .replace(' ', ' ').replace('\n', '<br/>'))


def _montant(v, devise=''):
    if v is None or v == '':
        return '—'
    from tresorerie.services import fmt
    return fmt(Decimal(str(v)), devise)


def _date(d, heure=False):
    if not d:
        return '—'
    if hasattr(d, 'hour'):
        d = timezone.localtime(d) if timezone.is_aware(d) else d
        return d.strftime('%d/%m/%Y %H:%M') if heure else d.strftime('%d/%m/%Y')
    return d.strftime('%d/%m/%Y') if hasattr(d, 'strftime') else str(d)


def _date_iso(v, heure=False):
    from datetime import date, datetime
    try:
        d = datetime.fromisoformat(str(v).replace('Z', '+00:00')) if heure or 'T' in str(v) else date.fromisoformat(str(v)[:10])
    except ValueError:
        return str(v)
    return _date(d, heure)


# ═══════════════════════════════════════════════════════════════
# BLOCS
# ═══════════════════════════════════════════════════════════════

def _section(titre):
    t = Table([['', Paragraph(_txt(titre), S_SECTION)]], colWidths=[1.2 * mm, None])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (0, 0), VERT), ('LEFTPADDING', (1, 0), (1, 0), 6),
                           ('LEFTPADDING', (0, 0), (0, 0), 0), ('RIGHTPADDING', (0, 0), (0, 0), 0),
                           ('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
                           ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    espace, apres = Spacer(1, 5 * mm), Spacer(1, 2.5 * mm)
    for f in (espace, t, apres):
        f.keepWithNext = True  # jamais de titre seul en bas de page
    return [espace, t, apres]


def _grille(paires, largeur, colonnes=2):
    """Libellé / valeur sur `colonnes` colonnes."""
    cellules, ligne = [], []
    for libelle, valeur in paires:
        ligne.append([Paragraph(_txt(libelle), S_LIBELLE), Paragraph(_txt(valeur), S_VALEUR)])
        if len(ligne) == colonnes:
            cellules.append(ligne)
            ligne = []
    if ligne:
        cellules.append(ligne + [''] * (colonnes - len(ligne)))
    if not cellules:
        return Spacer(1, 1)
    t = Table(cellules, colWidths=[largeur / colonnes] * colonnes)
    t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
    return t


def _tableau(entete, lignes, largeurs, droite=(), total=False):
    data = [[Paragraph(_txt(e), S_ENTETE) for e in entete]]
    for i, l in enumerate(lignes):
        gras = total and i == len(lignes) - 1
        data.append([c if not isinstance(c, (str, int, float, Decimal)) and c is not None else
                     Paragraph('' if c == '' else _txt(c), (S_DROITE_GRAS if gras else S_DROITE) if j in droite else
                               (S_VALEUR if gras else S_NORMAL)) for j, c in enumerate(l)])
    t = Table(data, colWidths=largeurs, repeatRows=1)
    style = [('BACKGROUND', (0, 0), (-1, 0), NAVY), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
             ('TOPPADDING', (0, 0), (-1, -1), 3.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
             ('LINEBELOW', (0, 1), (-1, -1), 0.4, BORD), ('ROUNDEDCORNERS', [3, 3, 0, 0])]
    for i in range(2, len(data), 2):
        style.append(('BACKGROUND', (0, i), (-1, i), FOND))
    if total:
        style += [('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#EAFBF1')),
                  ('LINEABOVE', (0, -1), (-1, -1), 0.8, VERT)]
    t.setStyle(TableStyle(style))
    return t


def _encadre(textes, fond, bord):
    t = Table([[Paragraph(_txt(x), S_NORMAL)] for x in textes], colWidths=[None])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(fond)),
                           ('LINEBEFORE', (0, 0), (0, -1), 2, colors.HexColor(bord)),
                           ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
    return t


def _badge(texte, statut):
    fond, encre = COULEURS_STATUT.get(statut, ('#EEF1F5', '#5A7090'))
    t = Table([[Paragraph(f'<font color="{encre}">{_txt(texte)}</font>',
                          ParagraphStyle('b', fontName=GRAS, fontSize=9, leading=11, alignment=1))]], colWidths=[38 * mm])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(fond)), ('ROUNDEDCORNERS', [7, 7, 7, 7]),
                           ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
    return t


def _qr(texte, taille=21 * mm):
    w = QrCodeWidget(texte)
    x1, y1, x2, y2 = w.getBounds()
    d = Drawing(taille, taille, transform=[taille / (x2 - x1), 0, 0, taille / (y2 - y1), 0, 0])
    d.add(w)
    return d


def _tuiles(valeurs, largeur):
    cellules = [[Paragraph(_txt(l), S_TUILE_LIB) for l, _ in valeurs], [Paragraph(_txt(v), S_TUILE_VAL) for _, v in valeurs]]
    t = Table(cellules, colWidths=[largeur / len(valeurs)] * len(valeurs))
    style = [('BACKGROUND', (0, 0), (-1, -1), FOND), ('TOPPADDING', (0, 0), (-1, 0), 6),
             ('BOTTOMPADDING', (0, -1), (-1, -1), 7), ('ROUNDEDCORNERS', [5, 5, 5, 5])]
    for i in range(1, len(valeurs)):
        style.append(('LINEBEFORE', (i, 0), (i, -1), 2, colors.white))
    t.setStyle(TableStyle(style))
    return t


# ═══════════════════════════════════════════════════════════════
# PAGE (en-tête, pied, numérotation « page x / y »)
# ═══════════════════════════════════════════════════════════════

class _Canevas(canvas_module.Canvas):
    def __init__(self, *args, entete=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._pages, self._entete = [], entete

    def showPage(self):
        self._pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._pages)
        for etat in self._pages:
            self.__dict__.update(etat)
            self._entete(self, total)
            super().showPage()
        super().save()


def _dessiner_cadre(demande, edite_par):
    from api.models import ParametreSysteme
    param = ParametreSysteme.charger()
    chemin_logo = None
    if param.logo:
        try:
            chemin_logo = param.logo.path if Path(param.logo.path).exists() else None
        except (ValueError, NotImplementedError):
            chemin_logo = None

    def dessiner(c, total):
        l, h = A4
        page = c.getPageNumber()
        # En-tête : logo de la société (Paramètres → Société), sinon sa raison sociale ; filet vert
        haut = h - 8 * mm
        if chemin_logo:
            try:
                c.drawImage(chemin_logo, 15 * mm, h - 17 * mm, width=48 * mm, height=10 * mm,
                            preserveAspectRatio=True, anchor='w', mask='auto')
            except Exception:  # image illisible : la raison sociale prend le relais
                c.setFillColor(NAVY)
                c.setFont(GRAS, 12.5)
                c.drawString(15 * mm, h - 13.5 * mm, (param.raison_sociale or 'Société').upper())
        if not chemin_logo:
            c.setFillColor(NAVY)
            c.setFont(GRAS, 12.5)
            c.drawString(15 * mm, h - 13.5 * mm, (param.raison_sociale or 'Société').upper())
        c.setFillColor(NAVY)
        c.setFont(GRAS, 10.5)
        c.drawRightString(l - 15 * mm, haut - 3 * mm, demande.reference or f'Brouillon n° {demande.pk}')
        c.setFont(POLICE, 7.5)
        c.setFillColor(GRIS)
        c.drawRightString(l - 15 * mm, haut - 7.5 * mm, demande.type_demande.libelle)
        c.setStrokeColor(VERT)
        c.setLineWidth(1.2)
        c.line(15 * mm, h - 20 * mm, l - 15 * mm, h - 20 * mm)
        # Pied
        c.setStrokeColor(BORD)
        c.setLineWidth(0.5)
        c.line(15 * mm, 13 * mm, l - 15 * mm, 13 * mm)
        c.setFont(POLICE, 6.8)
        c.setFillColor(GRIS)
        c.drawString(15 * mm, 9 * mm, f"Édité le {timezone.localtime().strftime('%d/%m/%Y à %H:%M')}"
                                      + (f' par {edite_par}' if edite_par else '') + ' — document généré par UbiFlow')
        c.drawRightString(l - 15 * mm, 9 * mm, f'Page {page} / {total}')
    return dessiner


# ═══════════════════════════════════════════════════════════════
# DOCUMENT
# ═══════════════════════════════════════════════════════════════

def _valeur_champ(champ, v):
    from django.contrib.auth import get_user_model
    if v in (None, ''):
        return '—'
    if champ.nature == 'booleen':
        return 'Oui' if v else 'Non'
    if champ.nature == 'date':
        return _date_iso(v)
    if champ.nature == 'datetime':
        return _date_iso(v, heure=True)
    if champ.nature == 'montant':
        return _montant(v)
    if champ.nature == 'collaborateur':
        u = get_user_model().objects.filter(pk=v).first()
        return moteur.nom(u) if u else f'#{v}'
    return str(v)


def generer(demande, user):
    tampon = BytesIO()
    marge = 15 * mm
    largeur = A4[0] - 2 * marge
    doc = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=marge, rightMargin=marge, topMargin=26 * mm,
                            bottomMargin=19 * mm, title=f"{demande.reference or 'Brouillon'} — {demande.type_demande.libelle}",
                            author='UbiFlow', subject=demande.objet)
    devise = demande.devise or demande.devise_reference
    h = []

    # ── Titre, statut, QR ──
    lien = getattr(settings, 'FRONTEND_URL', '') or ''
    qr = _qr(f"{lien.rstrip('/')}/demandes/{demande.pk}" if lien else
             f"UbiFlow {demande.reference or demande.pk} · {demande.get_statut_display()} · {timezone.localdate():%d/%m/%Y}")
    titre = [Paragraph(_txt(demande.type_demande.libelle), S_TITRE), Spacer(1, 1.5 * mm),
             Paragraph(_txt(demande.objet), ParagraphStyle('o', parent=S_NORMAL, fontSize=10, leading=13)),
             Spacer(1, 2.5 * mm), _badge(demande.get_statut_display(), demande.statut)]
    t = Table([[titre, qr]], colWidths=[largeur - 25 * mm, 25 * mm])
    t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0),
                           ('RIGHTPADDING', (0, 0), (-1, -1), 0), ('ALIGN', (1, 0), (1, 0), 'RIGHT')]))
    h += [t, Spacer(1, 5 * mm)]

    # ── Montants ──
    if demande.montant_demande is not None or demande.montant_approuve is not None:
        reste = 0 if demande.statut == 'annulee' else demande.solde
        h.append(_tuiles([('Montant demandé', _montant(demande.montant_demande, devise)),
                          ('Montant approuvé', _montant(demande.montant_approuve, devise)),
                          ('Payé', _montant(demande.montant_paye, devise)),
                          ('Reste à payer', _montant(reste, devise) if reste is not None else '—')], largeur))
        if demande.statut_financier != 'sans_objet':
            h += [Spacer(1, 1.5 * mm), Paragraph(f'Situation financière : <b>{_txt(demande.get_statut_financier_display())}</b>'
                                                 + (f' — contre-valeur {_montant(demande.montant_demande_ref, demande.devise_reference)}'
                                                    if demande.devise != demande.devise_reference and demande.montant_demande_ref else ''),
                                                 S_PETIT)]

    if demande.alertes and demande.statut != 'brouillon':
        h += [Spacer(1, 3 * mm), _encadre(["Points d'attention :"] + [x.get('message', '') for x in demande.alertes],
                                         '#FEF4E4', '#E8A33D')]

    # ── Demandeur ──
    u = demande.demandeur
    h += _section('Demandeur')
    h.append(_grille([(l, v) for l, v in [('Nom', moteur.nom(u)), ('Matricule', u.username),
                      ('Département', demande.departement.libelle_service if demande.departement_id else None),
                      ('Agence', demande.agence.nom_agence if demande.agence_id else None),
                      ('Catégorie', demande.categorie.libelle if demande.categorie_id else None),
                      ('Poste', demande.poste.libelle if demande.poste_id else None),
                      ('N+1 retenu', moteur.nom(demande.n_plus_1) if demande.n_plus_1_id else None),
                      ('Saisie par', moteur.nom(demande.cree_par) if demande.cree_par_id != u.pk else None)]
                     if v is not None or l in ('Département', 'Catégorie')], largeur, 3))

    # ── Informations ──
    h += _section('Informations de la demande')
    paires = [('Référence', demande.reference or 'Brouillon'), ('Type', demande.type_demande.libelle),
              ('Créée le', _date(demande.created_at, True)), ('Soumise le', _date(demande.soumise_le, True)),
              ('Approuvée le', _date(demande.approuvee_le, True))]
    if demande.cloturee_le:
        paires.append(('Clôturée le', _date(demande.cloturee_le, True)))
    if demande.annulee_le:
        paires.append(('Annulée le', _date(demande.annulee_le, True)))
    if demande.demande_parent_id:
        paires.append(('Rattachée à', f"{demande.demande_parent.reference} ({demande.demande_parent.type_demande.libelle})"))
    h.append(_grille(paires, largeur, 3))
    champs = [(c.libelle, _valeur_champ(c, (demande.donnees or {}).get(c.code)))
              for c in demande.type_demande.champs.filter(actif=True).order_by('ordre')]
    if champs:
        h += [Spacer(1, 1.5 * mm), _grille(champs, largeur, 2)]
    if demande.motif_annulation:
        h += [Spacer(1, 2 * mm), _encadre([f"Motif d'annulation : {demande.motif_annulation}"], '#EEF1F5', '#5A7090')]

    # ── Mission ──
    mission = (demande.donnees or {}).get('mission') if demande.type_demande.famille == 'mission' else None
    if mission:
        from missions.calcul import MOYENS
        h += _section('Mission')
        trajet = f"{mission.get('ville_depart_libelle', '—')} → {mission.get('ville_destination_libelle', '—')}"
        if mission.get('pays_destination_libelle') and (demande.type_demande.parametres or {}).get('type_mission') == 'hors_pays':
            trajet += f" ({mission['pays_destination_libelle']})"
        h.append(_grille([('Trajet', trajet),
                          ('Période', f"du {_date_iso(mission.get('depart_le'), True)} au {_date_iso(mission.get('retour_le'), True)}"
                                      + (f" — {mission['nombre_jours']} jour(s)" if mission.get('nombre_jours') else '')),
                          ('Transport', f"{MOYENS.get(mission.get('moyen_transport'), mission.get('moyen_transport') or '—')}, "
                                        f"{'aller simple' if mission.get('trajet') == 'aller_simple' else 'aller-retour'}"),
                          ('Motif', mission.get('motif'))], largeur, 2))
        calcul = demande.version_courante.calcul if demande.version_courante_id else None
        if calcul and calcul.get('lignes'):
            from missions.calcul import RUBRIQUES_FRAIS
            rubriques = {'per_diem': 'Indemnités journalières', 'transport': 'Transport', **RUBRIQUES_FRAIS}
            ref = calcul.get('devise_reference', devise)
            devises = any(l['devise'] != ref for l in calcul['lignes'])
            lignes = [[rubriques.get(l['rubrique'], l['rubrique']), l['libelle']]
                      + ([_montant(l['montant'], l['devise']) if l['devise'] != ref else ''] if devises else [])
                      + [_montant(l['montant_ref'], ref)] for l in calcul['lignes']]
            lignes.append(['Total prévisionnel', ''] + ([''] if devises else []) + [_montant(calcul.get('total_ref'), ref)])
            entete = ['Rubrique', 'Détail'] + (["Devise d'origine"] if devises else []) + [f'Montant ({ref})']
            largeurs = ([33 * mm, largeur - 93 * mm, 30 * mm, 30 * mm] if devises else [33 * mm, largeur - 63 * mm, 30 * mm])
            h += [Spacer(1, 2 * mm), Paragraph(f"Récapitulatif des frais — barèmes du {_date_iso(calcul.get('date_baremes'))}"
                                               + (f", catégorie {calcul['categorie']}" if calcul.get('categorie') else ''), S_PETIT),
                  Spacer(1, 1.5 * mm),
                  _tableau(entete, lignes, largeurs, droite=(len(entete) - 2, len(entete) - 1) if devises else (2,),
                           total=True)]
            if calcul.get('signalements'):
                h += [Spacer(1, 2 * mm), _encadre(['À l\'attention des valideurs :'] + calcul['signalements'], '#FEF4E4', '#E8A33D')]

    # ── Circuit de validation ──
    instances = list(demande.instances.order_by('cycle'))
    if instances:
        h += _section('Circuit de validation')
        for inst in instances:
            lignes = []
            for ei in inst.etapes.select_related('etape').order_by('ordre'):
                taches = list(ei.taches.select_related('valideur', 'traitee_par').order_by('ordre'))
                if ei.etat == 'sautee':
                    lignes.append([str(ei.ordre), ei.etape.libelle, '—',
                                   Paragraph('<font color="#5A7090">Sautée</font>', S_NORMAL), '', ei.motif_saut or ''])
                    continue
                for t in taches or [None]:
                    if t is None:
                        lignes.append([str(ei.ordre), ei.etape.libelle, '—', ei.get_etat_display(), '', ''])
                        continue
                    action = t.actions.filter(type__in=('approbation', 'auto_approbation', 'rejet', 'retour')).last()
                    libelle, couleur = DECISIONS.get(t.decision, (t.get_etat_display() if t.etat != 'en_attente' else 'En attente', '#0F3A6E'))
                    valideur = moteur.nom(t.valideur)
                    if t.traitee_par_id and t.traitee_par_id != t.valideur_id:
                        valideur += f' (par {moteur.nom(t.traitee_par)})'
                    lignes.append([str(ei.ordre), ei.etape.libelle, valideur,
                                   Paragraph(f'<font color="{couleur}"><b>{_txt(libelle)}</b></font>', S_NORMAL),
                                   _date(t.traitee_le, True) if t.traitee_le else '', action.motif if action else ''])
            if len(instances) > 1:
                h += [Paragraph(f"Cycle {inst.cycle} — {inst.get_etat_display().lower()}", S_PETIT), Spacer(1, 1 * mm)]
            h += [_tableau(['N°', 'Étape', 'Valideur', 'Décision', 'Date', 'Commentaire'], lignes,
                           [9 * mm, 38 * mm, 36 * mm, 22 * mm, 29 * mm, largeur - 134 * mm]), Spacer(1, 2 * mm)]

    # ── Paiements ──
    reglements = list(demande.reglements.select_related('enregistre_par').order_by('date_paiement', 'id'))
    reversements = list(demande.reversements.order_by('cree_le'))
    if reglements or reversements:
        h += _section('Paiements')
        if reglements:
            h.append(_tableau(['Date', 'Mode', 'Référence', 'Bénéficiaire', 'Montant'],
                              [[_date(r.date_paiement), r.get_mode_display() + (' (annulé)' if r.annule else ''), r.reference,
                                r.beneficiaire, _montant(r.montant, r.devise)] for r in reglements],
                              [24 * mm, 32 * mm, 36 * mm, largeur - 124 * mm, 32 * mm], droite=(4,)))
        for rv in reversements:
            etat = rv.get_etat_display().lower() + (f' le {_date(rv.percu_le)}' if rv.percu_le else '')
            h += [Spacer(1, 2 * mm), _encadre([f"Reversement de {_montant(rv.montant_du, rv.devise)} — {rv.get_origine_display()} : {etat}"
                                                + (f" ({rv.motif_abandon})" if rv.motif_abandon else '')],
                                               '#FEF4E4' if rv.etat == 'a_percevoir' else '#F4F7FB', '#E8A33D')]

    # ── Demandes rattachées ──
    rattachees = list(demande.demandes_rattachees.exclude(statut='brouillon').select_related('type_demande'))
    if rattachees:
        h += _section('Demandes rattachées')
        h.append(_tableau(['Référence', 'Type', 'Objet', 'Statut', 'Montant'],
                          [[d.reference, d.type_demande.libelle, d.objet, d.get_statut_display(),
                            _montant(d.montant_approuve or d.montant_demande, d.devise) if (d.montant_approuve or d.montant_demande) else '—']
                           for d in rattachees], [34 * mm, 38 * mm, largeur - 130 * mm, 28 * mm, 30 * mm], droite=(4,)))

    # ── Pièces jointes ──
    documents = list(demande.documents.select_related('type_piece', 'ajoute_par').order_by('ajoute_le'))
    if documents:
        h += _section('Pièces jointes')
        h.append(_tableau(['Pièce', 'Fichier', 'Ajoutée par', 'Le'],
                          [[d.type_piece.libelle if d.type_piece_id else 'Autre', d.nom_origine + (' (retirée)' if d.retire else ''),
                            moteur.nom(d.ajoute_par), _date(d.ajoute_le, True)] for d in documents],
                          [40 * mm, largeur - 108 * mm, 40 * mm, 28 * mm]))

    # ── Commentaires ──
    commentaires = list(demande.commentaires.select_related('auteur').order_by('creee_le'))
    if commentaires:
        h += _section('Commentaires')
        for c in commentaires:
            h.append(KeepTogether([Paragraph(f"<b>{_txt(moteur.nom(c.auteur))}</b> — {_date(c.creee_le, True)}", S_PETIT),
                                   Paragraph(_txt(c.texte), S_NORMAL), Spacer(1, 2 * mm)]))

    h += [Spacer(1, 6 * mm), Paragraph("Ce document présente les informations enregistrées dans UbiFlow à la date d'édition. "
                                       "Il ne remplace pas les pièces justificatives.", S_PETIT)]

    edite_par = moteur.nom(user) if user else ''
    doc.build(h, canvasmaker=lambda *a, **k: _Canevas(*a, entete=_dessiner_cadre(demande, edite_par), **k))
    return tampon.getvalue()
