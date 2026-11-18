"""
Rapport mensuel de la cantine (PDF) pour la direction : chiffres clés du
mois comparés au mois précédent, montants, agences, plats, desserts,
participation, affluence, comptes repas, prestataires et contrôle du comptoir.

  - GET /statistiques/rapport-mensuel/?annee=&mois=   (gestionnaires : leurs agences)
  - envoi automatique : le 1er du mois, une notification aux administrateurs
    (tâches planifiées) avec le lien de téléchargement du mois écoulé.
"""
from io import BytesIO
from types import SimpleNamespace
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Spacer, Table, TableStyle

from . import facturation as fact
from . import indicateurs as ind
from . import statistiques as stats
from . import statistiques_plus as plus
from .models import Agence, Commande
from .pdf_factures import (
    G500, ORANGE, UTILE, _canvas, _doc, _entete, _h2, _meta, _p, _style_tableau, _styles, fcfa,
)

MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre',
        'novembre', 'décembre']
PALETTE = ['#0F3A6E', '#3EC970', '#F7B84B', '#2F80ED', '#F06548', '#7B61FF', '#9AA9BE', '#14B8A6']


def donnees_rapport(annee, mois, geres=None):
    """Toutes les données du rapport (geres : agences du gestionnaire, None = toutes)."""
    debut, fin = fact.bornes_mois(annee, mois)
    pa, pm = (annee, mois - 1) if mois > 1 else (annee - 1, 12)
    d_prec, f_prec = fact.bornes_mois(pa, pm)
    auj = timezone.localdate()

    def commandes(d, f):
        qs = Commande.objects.filter(menu__date_menu__gte=d, menu__date_menu__lte=f)
        return qs.filter(menu__agence_id__in=geres) if geres is not None else qs

    qs, qs_prec = commandes(debut, fin), commandes(d_prec, f_prec)
    repas = qs.filter(commande_principale__isnull=True)
    per = SimpleNamespace(debut=debut, fin=fin, agence=None, geres=geres, typeequipe=None)
    agences = (sorted(Agence.objects.filter(id__in=geres).values_list('nom_agence', flat=True))
               if geres is not None else [])
    return {
        'annee': annee, 'mois': mois, 'libelle': f"{MOIS[mois - 1].capitalize()} {annee}",
        'libelle_prec': f"{MOIS[pm - 1]} {pa}", 'debut': debut, 'fin': fin, 'agences': agences,
        'kpis': stats.kpis(repas, auj), 'kpis_prec': stats.kpis(qs_prec.filter(commande_principale__isnull=True), auj),
        'plats': ind.plats(qs, debut, fin), 'montants': ind.montants(qs, debut, fin),
        'montants_prec': ind.montants(qs_prec, d_prec, f_prec),
        **plus.complements(per),
    }


def _evol(v, p):
    if not p:
        return ''
    e = (v - p) / p * 100
    return f"{'+' if e >= 0 else ''}{e:.0f} % vs mois préc.".replace('.', ',')


def _cases(chiffres, st, par_ligne=4):
    largeur = (UTILE - 3 * mm * (par_ligne - 1)) / par_ligne
    lignes, courante = [], []
    for libelle, valeur, note in chiffres:
        case = Table([[_p(libelle, st['kpi'])], [_p(valeur, st['kpi_v'])],
                      [_p(note, ParagraphStyle('kn', parent=st['kpi'], fontSize=6.8, textColor=G500))]],
                     colWidths=[largeur], cornerRadii=[2 * mm] * 4)
        case.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), .3 * mm, colors.HexColor('#E4E7EC')),
                                  ('LEFTPADDING', (0, 0), (-1, -1), 3 * mm), ('TOPPADDING', (0, 0), (-1, 0), 2.2 * mm),
                                  ('BOTTOMPADDING', (0, -1), (-1, -1), 2.2 * mm), ('TOPPADDING', (0, 1), (-1, -1), 0),
                                  ('BOTTOMPADDING', (0, 0), (-1, -2), .3 * mm)]))
        courante += ([''] if courante else []) + [case]
        if len(courante) == par_ligne * 2 - 1:
            lignes.append(courante)
            courante = []
    if courante:
        while len(courante) < par_ligne * 2 - 1:
            courante += ['', '']
        lignes.append(courante[:par_ligne * 2 - 1])
    t = Table(lignes, colWidths=([largeur, 3 * mm] * par_ligne)[:-1])
    t.setStyle(TableStyle([('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5 * mm)]))
    return t


def _tableau(entete, lignes, droite_depuis=1, total=False, largeurs=None):
    t = Table([entete] + lignes, colWidths=largeurs, repeatRows=1)
    t.setStyle(TableStyle(_style_tableau(len(lignes) + 1, droite_depuis, total=total, taille=8)))
    return t


def _barres_h(libelles, valeurs, largeur, couleur='#0F3A6E', format_=lambda v: f"{v:,.0f}".replace(',', ' ')):
    h = max(60, 18 * len(libelles) + 20)
    d = Drawing(largeur, h)
    c = HorizontalBarChart()
    c.x, c.y, c.width, c.height = 95, 10, largeur - 150, h - 20
    c.data = [list(reversed(valeurs))]
    c.categoryAxis.categoryNames = list(reversed([l[:22] for l in libelles]))
    c.categoryAxis.labels.fontSize = 7
    c.categoryAxis.labels.fontName = 'Helvetica'
    c.valueAxis.valueMin = 0
    c.valueAxis.visible = False
    c.bars[0].fillColor = colors.HexColor(couleur)
    c.bars[0].strokeColor = None
    c.barLabelFormat = format_
    c.barLabels.fontSize = 7
    c.barLabels.fontName = 'Helvetica'
    c.barLabels.dx = 4
    c.barLabels.boxAnchor = 'w'
    d.add(c)
    return d


def _barres_v(libelles, series, noms, largeur, hauteur=150):
    d = Drawing(largeur, hauteur)
    c = VerticalBarChart()
    c.x, c.y, c.width, c.height = 40, 30, largeur - 60, hauteur - 50
    c.data = series
    c.categoryAxis.categoryNames = libelles
    c.categoryAxis.labels.fontSize = 6.5
    c.categoryAxis.labels.fontName = 'Helvetica'
    c.valueAxis.labels.fontName = 'Helvetica'
    c.categoryAxis.labels.angle = 45 if len(libelles) > 12 else 0
    c.categoryAxis.labels.boxAnchor = 'ne' if len(libelles) > 12 else 'n'
    c.valueAxis.valueMin = 0
    c.valueAxis.labels.fontSize = 7
    for i in range(len(series)):
        c.bars[i].fillColor = colors.HexColor(PALETTE[i])
        c.bars[i].strokeColor = None
    d.add(c)
    for i, n in enumerate(noms):
        d.add(String(40 + i * 120, hauteur - 10, f"■ {n}", fontSize=7, fontName='Helvetica', fillColor=colors.HexColor(PALETTE[i])))
    return d


def _camembert(libelles, valeurs, largeur, hauteur=130):
    d = Drawing(largeur, hauteur)
    total = sum(valeurs) or 1
    p = Pie()
    p.x, p.y, p.width, p.height = 10, 10, hauteur - 20, hauteur - 20
    p.data = valeurs or [1]
    p.labels = None
    p.slices.strokeColor = colors.white
    for i in range(len(valeurs)):
        p.slices[i].fillColor = colors.HexColor(PALETTE[i % len(PALETTE)])
    d.add(p)
    for i, (l, v) in enumerate(zip(libelles, valeurs)):
        y = hauteur - 20 - i * 13
        d.add(String(hauteur + 5, y, f"■", fontSize=9, fontName='Helvetica', fillColor=colors.HexColor(PALETTE[i % len(PALETTE)])))
        d.add(String(hauteur + 16, y, f"{l[:26]} · {v / total * 100:.0f} %".replace('.', ','), fontSize=7.5,
                     fontName='Helvetica'))
    return d


def generer_rapport_mensuel(r, societe):
    st = _styles()
    k, kp, m, mp = r['kpis'], r['kpis_prec'], r['montants'], r['montants_prec']
    pl, de, pa, af, cr, ct = r['plats'], r['desserts'], r['participation'], r['affluence'], r['comptes_repas'], r['controle']
    elements = []
    meta = _meta([('Mois', r['libelle'], None),
                  ('Agences', escape(', '.join(r['agences'])) if r['agences'] else 'toutes', None),
                  ('État', 'Mois en cours (provisoire)' if r['fin'] >= timezone.localdate() else 'Mois terminé',
                   ORANGE if r['fin'] >= timezone.localdate() else colors.HexColor('#219653')),
                  ('Édité le', f"{timezone.localtime():%d/%m/%Y à %H:%M}", None)], st)
    elements += [_entete(societe, 'RAPPORT MENSUEL', f"Cantine · {r['libelle']}", meta, st,
                         sous_ligne_societe='Service gestion de la cantine'), Spacer(1, 5 * mm)]

    elements.append(_h2('Chiffres clés', f"comparés à {r['libelle_prec']}", st, avant=0))
    elements.append(_cases([
        ('Repas commandés', f"{k['commandes']}", _evol(k['commandes'], kp['commandes'])),
        ('Taux de retrait', f"{k['taux_retrait'] or 0:.1f} %".replace('.', ','), f"{k['non_retires']} non retirés"),
        ('Facturé aux employés', f"{fcfa(m['total_employes'])} F", _evol(m['total_employes'], mp['total_employes'])),
        ('Dû aux prestataires', f"{fcfa(m['total_prestataires'])} F", _evol(m['total_prestataires'], mp['total_prestataires'])),
        ('Participation', f"{pa['taux_participation'] or 0:.0f} %".replace('.', ','),
         f"{pa['commandeurs']} employés sur {pa['effectif']}"),
        ('Repas avec dessert', f"{de['part_avec_dessert'] or 0:.0f} %".replace('.', ','),
         f"préféré : {de['prefere'] or '—'}"),
        ('Heure de pointe', af['pointe']['tranche'] if af['pointe'] else '—',
         f"{af['nb_retraits']} retraits sur {af['jours']} jours"),
        ('Note des employés', f"{k['note_moyenne'] or 0:.1f} / 5".replace('.', ',') if k['note_moyenne'] else '—',
         f"{k['nb_avis']} avis"),
    ], st))

    # Montants par agence
    if m['par_agence']:
        elements.append(_h2('Montants par agence', 'facturé aux employés et dû aux prestataires', st))
        elements.append(_tableau(['Agence', 'Repas', 'Desserts', 'Facturé employés', 'Dû prestataires'],
                                 [[a['agence'], str(a['repas']), str(a['supplements']), f"{fcfa(a['employes'])} F",
                                   f"{fcfa(a['prestataires'])} F"] for a in m['par_agence']]
                                 + [['TOTAL', str(sum(a['repas'] for a in m['par_agence'])),
                                     str(sum(a['supplements'] for a in m['par_agence'])),
                                     f"{fcfa(m['total_employes'])} F", f"{fcfa(m['total_prestataires'])} F"]],
                                 total=True, largeurs=[UTILE - 120 * mm, 22 * mm, 22 * mm, 38 * mm, 38 * mm]))

    # Plats
    if pl['par_plat']:
        top = pl['par_plat'][:8]
        elements.append(KeepTogether([
            _h2('Popularité des plats', f"plus commandé : {pl['kpis']['plat_plus']['plat']}"
                + (f" · moins commandé : {pl['kpis']['plat_moins']['plat']}" if pl['kpis']['plat_moins'] else ''), st),
            _barres_h([p['plat'] for p in top], [p['commandes'] for p in top], UTILE,
                      format_=lambda v: f"{int(v)}"),
            _p(f"{pl['kpis']['nb_menus']} menus · {pl['kpis']['moyenne_par_menu']} commandes par menu en moyenne"
               .replace('.', ','), st['petit']),
        ]))
    if m['par_type']:
        elements.append(KeepTogether([_h2('Répartition par type de plat', 'montant dû aux prestataires, desserts compris', st),
                                      _camembert([t['type_plat'] for t in m['par_type']],
                                                 [t['prestataires'] for t in m['par_type']], UTILE)]))
    if de['par_dessert']:
        elements.append(_h2('Desserts', f"{de['nb_desserts']} desserts · coût des desserts offerts {fcfa(de['cout_offerts'])} F", st))
        elements.append(_tableau(['Dessert', 'Choisis', 'Servis', 'Part'],
                                 [[x['plat'], str(x['choisis']), str(x['servis']), f"{x['part'] or 0:.0f} %"]
                                  for x in de['par_dessert']], largeurs=[UTILE - 75 * mm, 25 * mm, 25 * mm, 25 * mm]))

    # Participation
    if pa['par_agence']:
        elements.append(_h2('Participation des employés', f"{pa['nb_jamais']} employé(s) n'ont jamais commandé", st))
        elements.append(_tableau(['Agence', 'Effectif', 'Ont commandé', 'Participation', 'Repas / employé'],
                                 [[x['agence'], str(x['effectif']), str(x['commandeurs']),
                                   f"{x['taux_participation'] or 0:.0f} %", f"{x['repas_par_employe']}".replace('.', ',')]
                                  for x in pa['par_agence']],
                                 largeurs=[UTILE - 112 * mm, 25 * mm, 29 * mm, 29 * mm, 29 * mm]))

    # Affluence
    if af['tranches']:
        elements.append(KeepTogether([
            _h2('Affluence au comptoir', 'retraits moyens par tranche de 15 minutes', st),
            _barres_v([t['tranche'] for t in af['tranches']], [[t['moyenne'] for t in af['tranches']]],
                      ['Retraits par jour (moyenne)'], UTILE)]))

    # Comptes repas
    elements.append(_h2('Comptes repas', f"solde total {fcfa(cr['solde_total'])} F · {cr['nb_soldes_bas']} solde(s) bas", st))
    elements.append(_tableau(['Recharges', 'Nombre', 'Repas débités', 'Repas payés par compte', 'Repas en retenue'],
                             [[f"{fcfa(cr['recharges'])} F", str(cr['nb_recharges']), f"{fcfa(cr['debits'])} F",
                               str(sum(x['repas_compte'] for x in cr['par_mois'])),
                               str(sum(x['repas_retenue'] for x in cr['par_mois']))]], droite_depuis=0))

    # Prestataires
    if r['prestataires']:
        elements.append(_h2('Prestataires', 'taux de retrait, note, contestations, coût moyen', st))
        elements.append(_tableau(['Prestataire', 'Repas', 'Retrait', 'Note', 'Contest.', 'Coût moyen'],
                                 [[x['prestataire'], str(x['repas']), f"{x['taux_retrait'] or 0:.0f} %",
                                   f"{x['note']:.1f}".replace('.', ',') if x['note'] is not None else '—',
                                   str(x['contestations']),
                                   f"{fcfa(x['cout_moyen_repas'])} F" if x['cout_moyen_repas'] else '—']
                                  for x in r['prestataires']],
                                 largeurs=[UTILE - 115 * mm, 20 * mm, 20 * mm, 20 * mm, 22 * mm, 33 * mm]))

    # Contrôle
    elements.append(_h2('Contrôle du comptoir', '', st))
    elements.append(_p(f"{ct['contestations']} contestation(s) de retrait, dont {ct['acceptees']} acceptée(s) et "
                       f"{ct['ouvertes']} en attente · {ct['badges_perdus']} badge(s) déclaré(s) perdu(s) · "
                       f"{k['annulees']} commande(s) annulée(s).", st['n']))
    j = r['jeux']
    if j['parties'] or j['gagnants']:
        elements.append(_h2('Jeux', '', st))
        elements.append(_p(f"{j['parties']} partie(s) jouée(s) par {j['joueurs']} employé(s) · {j['gagnants']} gagnant(s)"
                           + (f" · coût des lots {fcfa(j['cout'])} F" if j['cout'] is not None else ''), st['n']))

    tampon = BytesIO()
    doc = _doc(tampon, f"Rapport mensuel — {r['libelle']}", societe.nom or 'Ubifood')
    doc.build(elements, canvasmaker=_canvas(societe, f"Rapport mensuel {r['mois']:02d}/{r['annee']}"))
    return tampon.getvalue()


def notifier_rapport_mensuel():
    """
    Le 1er du mois (à partir de 7 h) : notification aux administrateurs avec le
    rapport du mois écoulé (une seule fois par mois). Appelé par les tâches planifiées.
    """
    from .fcm_service import envoyer_notification_user
    from .models import Notification, User
    maintenant = timezone.localtime()
    if maintenant.day != 1 or maintenant.hour < 7:
        return 0
    a, mo = (maintenant.year, maintenant.month - 1) if maintenant.month > 1 else (maintenant.year - 1, 12)
    cle = f"{a}-{mo:02d}"
    admins = User.objects.filter(is_active=True, groups__name__in=('admin', 'super_admin')).distinct()
    n = 0
    for u in admins:
        if Notification.objects.filter(user=u, donnees__rapport_mensuel=cle).exists():
            continue
        envoyer_notification_user(user=u, titre=f"📊 Rapport mensuel · {MOIS[mo - 1]} {a}",
                                  message=f"Le rapport de la cantine de {MOIS[mo - 1]} {a} est prêt : "
                                          "Statistiques › Rapport du mois (PDF).",
                                  type_notif='info', donnees={'rapport_mensuel': cle, 'ecran': 'statistiques'})
        n += 1
    return n
