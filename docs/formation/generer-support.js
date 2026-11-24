const fs = require('fs');
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType, AlignmentType,
        HeadingLevel, LevelFormat, BorderStyle, Footer, PageNumber, Header } = require('docx');

const NAVY = '092440', VERT = '2FB46C', GRIS = '5A7090';
const F = 'Arial';
const p = (texte, o = {}) => new Paragraph({ spacing: { after: 120 }, ...o.para, children: [].concat(texte).map(t => typeof t === 'string' ? new TextRun({ text: t, font: F, size: 22, ...o.run }) : t) });
const b = t => new TextRun({ text: t, font: F, size: 22, bold: true });
const puce = (texte) => new Paragraph({ numbering: { reference: 'puces', level: 0 }, spacing: { after: 80 }, children: [].concat(texte).map(t => typeof t === 'string' ? new TextRun({ text: t, font: F, size: 22 }) : t) });
const h1 = t => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t })] });
const h2 = t => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: t })] });

const bord = { style: BorderStyle.SINGLE, size: 4, color: 'C9D3E0' };
const bords = { top: bord, bottom: bord, left: bord, right: bord };
function tableau(entetes, lignes, largeurs) {
  const total = largeurs.reduce((a, x) => a + x, 0);
  const cell = (t, i, entete, fond) => new TableCell({
    width: { size: largeurs[i], type: WidthType.DXA }, borders: bords,
    shading: entete ? { fill: NAVY, type: ShadingType.CLEAR, color: 'auto' } : fond ? { fill: fond, type: ShadingType.CLEAR, color: 'auto' } : undefined,
    margins: { top: 70, bottom: 70, left: 100, right: 100 },
    children: [].concat(t).map(x => new Paragraph({ children: [new TextRun({ text: x, font: F, size: entete ? 19 : 20, bold: entete, color: entete ? 'FFFFFF' : '1F2D3D' })] })),
  });
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: largeurs,
    rows: [new TableRow({ tableHeader: true, children: entetes.map((e, i) => cell(e, i, true)) }),
           ...lignes.map((l, j) => new TableRow({ children: l.map((c, i) => cell(c, i, false, j % 2 ? 'F4F7FB' : undefined)) }))],
  });
}
const espace = () => new Paragraph({ spacing: { after: 60 }, children: [] });

const contenu = [
  new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: 'UbiFlow', font: F, size: 26, bold: true, color: VERT })] }),
  new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun({ text: 'Annulations, paiements et contrôles des demandes' })] }),
  p('Support de formation — règles de gestion validées le 24/11/2026', { run: { color: GRIS } }),
  p('Ce document présente, pour les demandeurs, les valideurs, la comptabilité et les administrateurs, les règles appliquées par UbiFlow pour annuler une demande, la payer, récupérer un trop-perçu et repérer les situations à risque.'),

  h1('1. Annuler une demande'),
  h2('1.1 Selon le statut de la demande'),
  tableau(['Statut', 'Annulation', 'Comment'], [
    ['Brouillon (jamais soumis)', 'Pas d\'annulation : suppression', 'Bouton « Supprimer le brouillon ».'],
    ['En validation', 'Oui, directement', 'Bouton « Annuler la demande », motif obligatoire. Les validations en cours sont arrêtées et les valideurs prévenus.'],
    ['À corriger', 'Oui, directement', 'Même bouton, motif obligatoire.'],
    ['Approuvée (payée ou non)', 'Oui, par une demande d\'annulation (ANN)', 'Bouton « Demander l\'annulation ». Circuit : N+1 puis DAF. Si un paiement a eu lieu, un reversement du montant payé est créé.'],
    ['En attente de clôture', 'Oui, par une demande d\'annulation', 'Même procédure.'],
    ['Clôturée', 'Oui, par une demande d\'annulation (décision n° 2)', 'Le montant payé devient un reversement à percevoir.'],
    ['Rejetée, Annulée', 'Non', 'Définitive. Seule action possible : « Dupliquer en nouvelle demande ».'],
  ], [2300, 2500, 4500]),
  espace(),
  p([b('Paramétrage. '), 'Les statuts où le demandeur annule lui-même sa demande se règlent par type (Paramètres → Types de demande). Par défaut : en validation et à corriger.']),
  h2('1.2 Autres règles'),
  puce('Une seule demande d\'annulation en cours par demande.'),
  puce('Tant qu\'une demande d\'annulation est en cours, la demande d\'origine ne peut pas être payée.'),
  puce('Une demande d\'annulation ne peut pas elle-même faire l\'objet d\'une demande d\'annulation ; le demandeur peut l\'annuler directement tant qu\'elle est en validation.'),
  puce('Un valideur ne peut pas annuler : il approuve, retourne (motif) ou rejette (motif).'),
  puce([b('Décision n° 1 : '), 'un administrateur peut annuler la demande d\'un autre collaborateur (absence, doublon, départ), avec un motif obligatoire tracé dans l\'historique.']),

  h1('2. Payer une demande'),
  puce('La comptabilité paie depuis l\'écran « À payer » (Trésorerie) ou depuis la fiche de la demande.'),
  puce('Paiement en plusieurs fois si le type l\'autorise, sinon en une fois ; jamais plus que le reste à payer.'),
  puce('Chaque paiement indique la date, le mode (virement, chèque, espèces, mobile money), la référence, le bénéficiaire et, si exigé par le type, le justificatif.'),
  puce('Statut financier : à payer → partiellement payée → payée → soldée, ou « reversement attendu ».'),
  puce('Les demandes en clôture automatique (réception client, paiement, remboursement, frais complémentaires) sont clôturées dès qu\'elles sont payées.'),
  puce('Un paiement saisi par erreur est annulé par un administrateur des finances, avec un motif ; il reste visible, barré.'),
  puce([b('Décision n° 3 : '), 'aucune interdiction n\'est appliquée lorsqu\'un comptable paie sa propre demande ou enregistre son propre reversement. La séparation approbation / paiement reste paramétrable par type de demande.']),

  h1('3. Reversements'),
  p('Un reversement est une somme que le demandeur doit rendre à la société : annulation après paiement, ou clôture d\'une mission dont les dépenses réelles sont inférieures au montant payé.'),
  puce('La comptabilité enregistre la perception (date, mode, référence, justificatif) dans l\'écran « Reversements ».'),
  puce('Un administrateur des finances peut abandonner un reversement, avec un motif obligatoire.'),
  puce([b('Décision n° 4 : '), 'un administrateur des finances ne peut pas abandonner un reversement qui le concerne.']),

  h1('4. Décisions complémentaires du 24/11/2026'),
  tableau(['N°', 'Situation', 'Décision'], [
    ['1', 'Annulation par un administrateur', 'Autorisée, motif obligatoire, tracée.'],
    ['2', 'Demande clôturée mais erronée', 'Demande d\'annulation possible ; le montant payé devient un reversement.'],
    ['3', 'Comptable qui paie sa propre demande', 'Pas d\'interdiction.'],
    ['4', 'Abandon d\'un reversement qui concerne l\'administrateur des finances', 'Interdit.'],
    ['5', 'Mission annulée avec des frais complémentaires approuvés ou en cours', 'Les frais complémentaires sont annulés automatiquement ; reversement s\'ils ont été payés.'],
    ['6', 'Vue « Toutes les demandes »', 'Les brouillons des autres collaborateurs sont masqués.'],
    ['7', 'Valideur désactivé avec des validations en attente', 'Désactivation bloquée tant que les validations ne sont pas réaffectées ; l\'administrateur voit la liste à réaffecter.'],
    ['8', 'Deux missions du même collaborateur sur des dates qui se chevauchent', 'Signalé aux valideurs, sans bloquer.'],
    ['9', 'Mission saisie après la date de retour (régularisation)', 'Autorisée, signalée aux valideurs : « mission déjà effectuée ».'],
    ['10', 'Doublon probable (même type, même montant, même date ou même client)', 'Signalé aux valideurs et à la comptabilité, sans bloquer.'],
    ['11', 'Montant approuvé erroné découvert après l\'approbation', 'Correction motivée par le DAF tant que rien n\'est payé ; sinon demande d\'annulation puis nouvelle demande.'],
  ], [700, 3900, 4700]),
  espace(),
  p('Toutes ces décisions sont appliquées par UbiFlow depuis le lot 5.', { run: { color: GRIS } }),
  h2('Où les retrouver dans l\'application'),
  puce([b('Annulation par un administrateur, correction du montant approuvé : '), 'encadré « Administration » de la fiche de la demande.']),
  puce([b('Réaffectation d\'une validation : '), 'lien « réaffecter » à côté du valideur en attente, dans le circuit de la fiche.']),
  puce([b('Points d\'attention (doublon, chevauchement, régularisation) : '), 'bandeau orange en haut de la fiche et icône dans la liste « À payer ».']),

  h1('5. Clôturer une mission'),
  puce('Une mission approuvée passe « En attente de clôture ». Elle peut être payée pendant ce temps.'),
  puce('Au retour, le demandeur ouvre la fiche et remplit « Clôture de la mission » : dates réelles, dépenses réelles (hôtel, transport, téléphone, divers, réception, détaxe, autres frais à refacturer) et observations. Les indemnités journalières sont calculées : jours réels × tarif de la mission.'),
  puce('Il joint le rapport de mission (obligatoire) dans « Pièces jointes », puis clique sur « Soumettre la clôture ». La saisie est enregistrée automatiquement au fur et à mesure.'),
  puce('La comptabilité contrôle depuis « Clôtures à contrôler » : elle valide, ou retourne au demandeur avec un motif.'),
  puce('À la validation : si l\'avance reçue dépasse les dépenses réelles, un reversement est créé ; si elle est inférieure, le reste est payé au demandeur ; au-delà de l\'engagé, le demandeur fait une demande de frais complémentaires.'),
  puce('La mission est clôturée quand elle est payée et qu\'aucun reversement n\'est attendu. La note de frais est alors remplie avec les montants réels.'),

  h1('6. Documents et exports'),
  puce('Chaque liste a un bouton « Exporter » (Excel ou PDF) qui reprend toutes les lignes correspondant aux filtres, numérotées.'),
  puce('Chaque demande se télécharge en PDF de présentation (menu « Documents » de la fiche) : statut, montants, demandeur, contenu, circuit de validation, paiements, pièces.'),
  puce('Le même menu propose, pour les missions, l\'ordre de mission (une fois la mission approuvée) et la note de frais de mission, au format de la société (Paramètres → Société).'),
];

const doc = new Document({
  creator: 'UbiFlow', title: 'Annulations, paiements et contrôles des demandes',
  styles: {
    default: { document: { run: { font: F, size: 22 } } },
    paragraphStyles: [
      { id: 'Title', name: 'Title', basedOn: 'Normal', run: { font: F, size: 40, bold: true, color: NAVY }, paragraph: { spacing: { before: 0, after: 80 } } },
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: F, size: 30, bold: true, color: NAVY }, paragraph: { spacing: { before: 320, after: 140 }, keepNext: true, outlineLevel: 0, border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: VERT, space: 4 } } } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: F, size: 24, bold: true, color: '0F3A6E' }, paragraph: { spacing: { before: 200, after: 100 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: 'puces', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] }] },
  sections: [{
    properties: { page: { margin: { top: 1300, bottom: 1200, left: 1300, right: 1300 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [
      new TextRun({ text: 'UbiFlow — règles de gestion — page ', font: F, size: 16, color: GRIS }),
      new TextRun({ children: [PageNumber.CURRENT], font: F, size: 16, color: GRIS })] })] }) },
    children: contenu,
  }],
});
Packer.toBuffer(doc).then(buf => fs.writeFileSync(process.argv[2], buf));
