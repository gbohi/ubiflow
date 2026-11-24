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
  new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun({ text: 'Règles de gestion et utilisation d\'UbiFlow' })] }),
  p('Support de formation — web et application mobile — mis à jour le 24/11/2026', { run: { color: GRIS } }),
  p('Ce document présente, pour les demandeurs, les valideurs, la direction, la comptabilité et les administrateurs, l\'utilisation d\'UbiFlow et les règles qu\'il applique : créer et suivre une demande, la valider, l\'annuler, la payer, récupérer un trop-perçu, clôturer une mission, suivre les délais et l\'activité.'),
  tableau(['Profil', 'Sections utiles'], [
    ['Demandeur (tout collaborateur)', '1, 2, 3, 7, 9, 11, 12'],
    ['Valideur (N+1, DG, DAF, chef comptable…)', '1, 3, 6, 8, 9, 12'],
    ['Comptabilité', '1, 4, 5, 7, 10, 11'],
    ['Direction générale', '1, 6, 10'],
    ['Administrateur', 'Toutes, en particulier 3, 6, 8, 10'],
  ], [4300, 5000]),

  h1('Se connecter'),
  puce('Le matricule et le mot de passe sont les mêmes sur le web et sur l\'application mobile.'),
  puce([b('Se souvenir de moi : '), 'cochée, cette case mémorise le matricule sur cet appareil (navigateur ou téléphone). À la connexion suivante, même après une déconnexion, l\'écran affiche « Bon retour » avec le nom et le matricule : il ne reste qu\'à saisir le mot de passe. Le mot de passe n\'est jamais mémorisé.']),
  puce([b('Changer : '), 'sur un poste partagé, ce bouton efface le matricule mémorisé et réaffiche le formulaire complet. Décocher la case avant de se connecter l\'efface aussi.']),

  h1('1. La page d\'accueil'),
  p('À la connexion, la page d\'accueil présente une synthèse adaptée au profil de l\'utilisateur, avec une phrase qui résume la situation (« 3 demandes attendent une action de votre part »). Une personne qui a plusieurs profils (par exemple la DAF, qui est aussi valideuse et demandeuse) change de vue avec les boutons en haut à droite.'),
  tableau(['Vue', 'Les 4 indicateurs', 'Listes et graphiques'], [
    ['Collaborateur', 'Toutes mes demandes, En cours de validation, Approuvées, Actions attendues', 'Mes dernières demandes, prochaines missions, demandes retournées pour correction, rapports de mission à soumettre'],
    ['Valideur', 'À valider, En retard, Validées aujourd\'hui, Retournées ou rejetées', 'Mes validations en attente, avec un bouton « À valider »'],
    ['Direction générale', 'Total des demandes, En attente de validation, Missions en cours, Budget total approuvé', 'Répartition par catégorie, dépenses approuvées des 6 derniers mois, demandes nécessitant une attention particulière'],
    ['DAF / chef comptable', 'Montant total approuvé, En attente de paiement, Montant payé, Demandes à traiter', 'Demandes approuvées à payer (en tête), paiements récents, missions avec frais complémentaires, répartition par département'],
  ], [1900, 3600, 3800]),
  espace(),
  puce([b('À faire maintenant : '), 'tout ce qui attend une action de l\'utilisateur, quelle que soit la vue choisie : validations, paiements, clôtures à contrôler, demandes à corriger, missions à clôturer, reversements à effectuer. Les retards apparaissent en premier, puis les plus anciens ; chaque ligne a son bouton (Valider, Payer, Contrôler, Corriger, Déclarer mes dépenses).']),
  puce([b('Barre d\'actions : '), '« Nouvelle demande » et les types les plus courants (Mission locale, Mission hors pays, Remboursement), puis les accès propres au rôle (À payer, Reversements, Tableaux de bord).']),
  puce([b('Colonne de droite : '), 'notifications récentes et activité récente, regroupée par demande (par exemple « Clôture ×3, Reversement ×2 »).']),
  puce([b('Recherche : '), 'le champ en haut de chaque écran retrouve une demande par sa référence, son objet ou le nom ou le matricule du demandeur (touche « / » pour y accéder). Seules les demandes que l\'utilisateur a le droit de voir apparaissent : les siennes, celles qu\'il valide ou a validées et, pour les profils de gestion, celles de leur périmètre ; jamais les brouillons des autres.']),

  h1('2. Créer et suivre une demande'),
  puce('Menu « Nouvelle demande » (ou une action rapide) : choisir le type (étape 1/2), puis remplir le formulaire (étape 2/2).'),
  puce('Le formulaire reprend les champs propres au type : client, lieu et participants pour une réception client, bénéficiaire et mode de paiement pour une demande de paiement, date et nature de la dépense pour un remboursement…'),
  puce([b('Missions : '), 'ville de départ, destination, dates et heures, moyen de transport, autres frais (hébergement, visa, billet d\'avion). L\'estimation des frais (indemnités journalières, transport, frais) est recalculée pendant la saisie avec les barèmes en vigueur.']),
  puce([b('Frais complémentaires et demande d\'annulation : '), 'choisir la demande concernée dans la liste proposée.']),
  puce('« Enregistrer le brouillon » garde la demande modifiable ; « Soumettre » l\'envoie dans le circuit de validation. Les pièces exigées à la soumission doivent être jointes avant.'),
  puce('Après soumission, la fiche montre le statut, le circuit (étape en cours et valideurs prévus), l\'historique et les commentaires. Une demande retournée pour correction redevient modifiable : le demandeur la corrige puis clique sur « Soumettre à nouveau ».'),

  h1('3. Annuler une demande'),
  h2('3.1 Selon le statut de la demande'),
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
  h2('3.2 Autres règles'),
  puce('Une seule demande d\'annulation en cours par demande.'),
  puce('Tant qu\'une demande d\'annulation est en cours, la demande d\'origine ne peut pas être payée.'),
  puce('Une demande d\'annulation ne peut pas elle-même faire l\'objet d\'une demande d\'annulation ; le demandeur peut l\'annuler directement tant qu\'elle est en validation.'),
  puce('Un valideur ne peut pas annuler : il approuve, retourne (motif) ou rejette (motif).'),
  puce([b('Décision n° 1 : '), 'un administrateur peut annuler la demande d\'un autre collaborateur (absence, doublon, départ), avec un motif obligatoire tracé dans l\'historique.']),

  h1('4. Payer une demande'),
  puce('La comptabilité paie depuis l\'écran « À payer » (Trésorerie) ou depuis la fiche de la demande.'),
  puce('Paiement en plusieurs fois si le type l\'autorise, sinon en une fois ; jamais plus que le reste à payer.'),
  puce('Chaque paiement indique la date, le mode (virement, chèque, espèces, mobile money), la référence, le bénéficiaire et, si exigé par le type, le justificatif.'),
  puce('Statut financier : à payer → partiellement payée → payée → soldée, ou « reversement attendu ».'),
  puce('Les demandes en clôture automatique (réception client, paiement, remboursement, frais complémentaires) sont clôturées dès qu\'elles sont payées.'),
  puce('Un paiement saisi par erreur est annulé par un administrateur des finances, avec un motif ; il reste visible, barré.'),
  puce([b('Décision n° 3 : '), 'aucune interdiction n\'est appliquée lorsqu\'un comptable paie sa propre demande ou enregistre son propre reversement. La séparation approbation / paiement reste paramétrable par type de demande.']),

  h1('5. Reversements'),
  p('Un reversement est une somme que le demandeur doit rendre à la société : annulation après paiement, ou clôture d\'une mission dont les dépenses réelles sont inférieures au montant payé.'),
  puce('La comptabilité enregistre la perception (date, mode, référence, justificatif) dans l\'écran « Reversements ».'),
  puce('Un administrateur des finances peut abandonner un reversement, avec un motif obligatoire.'),
  puce([b('Décision n° 4 : '), 'un administrateur des finances ne peut pas abandonner un reversement qui le concerne.']),

  h1('6. Décisions complémentaires du 24/11/2026'),
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

  h1('7. Clôturer une mission'),
  puce('Une mission approuvée passe « En attente de clôture ». Elle peut être payée pendant ce temps.'),
  puce('Au retour, le demandeur ouvre la fiche et remplit « Clôture de la mission » : dates réelles, dépenses réelles (hôtel, transport, téléphone, divers, réception, détaxe, autres frais à refacturer) et observations. Les indemnités journalières sont calculées : jours réels × tarif de la mission.'),
  puce('Sur le web, la saisie est enregistrée automatiquement au fur et à mesure ; sur mobile, bouton « Déclarer mes dépenses réelles » puis « Enregistrer et recalculer ». Le solde (à rembourser à la société ou reste dû au demandeur) s\'affiche aussitôt.'),
  puce('Il joint le rapport de mission (obligatoire) — sur mobile, bouton « Joindre » à côté de la pièce, photo ou fichier — puis clique sur « Soumettre la clôture ». La soumission est refusée tant qu\'une pièce obligatoire manque.'),
  puce('La comptabilité contrôle depuis « Clôtures à contrôler » : elle valide, ou retourne au demandeur avec un motif.'),
  puce('À la validation : si l\'avance reçue dépasse les dépenses réelles, un reversement est créé ; si elle est inférieure, le reste est payé au demandeur ; au-delà de l\'engagé, le demandeur fait une demande de frais complémentaires.'),
  puce('La mission est clôturée quand elle est payée et qu\'aucun reversement n\'est attendu. La note de frais est alors remplie avec les montants réels.'),

  h1('8. Délais, rappels et escalades'),
  puce('Chaque étape d\'un circuit peut avoir un délai de traitement, un rappel et une escalade, exprimés en heures ouvrées (24 heures par jour ouvré). Réglage : Paramètres → Circuits de validation, fiche de l\'étape.'),
  puce('Les week-ends et les jours fériés ne comptent pas. Les jours ouvrés et le calendrier des jours fériés se gèrent dans Paramètres → Calendrier ; les fêtes à date variable (fêtes musulmanes) sont à saisir chaque année.'),
  puce([b('Rappel : '), 'le valideur reçoit un rappel une fois le délai de rappel passé, puis un par jour tant que la validation attend.']),
  puce([b('Escalade : '), 'une fois le délai d\'escalade passé, le N+1 du valideur, l\'administrateur ou une personne désignée est prévenu (une seule fois, tracé dans l\'historique). La validation reste au valideur ; l\'administrateur peut la réaffecter.']),
  puce('Les validations en retard sont signalées dans « À valider » et comptées dans les tableaux de bord.'),
  puce([b('Rappel de clôture : '), 'quelques jours après la date de retour, le demandeur d\'une mission non clôturée reçoit un rappel, puis un par semaine.']),

  h1('9. Notifications et délégations'),
  h2('9.1 Notifications'),
  puce('Chaque événement (validation attendue, demande approuvée, retournée, rejetée, paiement effectué, clôture attendue, reversement…) crée une notification dans l\'application (cloche en haut de l\'écran).'),
  puce('Selon l\'événement, elle est aussi envoyée par e-mail et en notification push sur le téléphone. Un appui sur la notification ouvre directement la demande.'),
  puce('Chacun choisit ses canaux dans « Préférences de notification » (icône réglages de la cloche ou du bloc « Notifications » de l\'accueil). « Validation attendue » et « Rappel de validation » ne peuvent pas être désactivés.'),
  puce('L\'administrateur active ou coupe les canaux e-mail et push pour toute la société (Paramètres → Société).'),
  h2('9.2 Délégations'),
  puce('Un valideur absent confie ses validations à un collègue pour une période : menu « Délégations » (web) ou Profil → Mes délégations (mobile).'),
  puce('Sur le web, la délégation peut être limitée à certains types de demande ou à certaines responsabilités ; sur mobile, elle couvre toutes les validations.'),
  puce('Le délégataire voit les validations dans son « À valider », avec la mention « pour le compte de ». La délégation peut être révoquée à tout moment.'),

  h1('10. Tableaux de bord'),
  puce('Menu « Tableaux de bord » : Mes demandes, Mes validations, Direction, Comptabilité, Administration, selon les droits.'),
  puce('Filtres : période, et pour la direction : statut, département, agence, catégorie, demandeur. Chaque graphique a une vue « Tableau ».'),
  puce('Chaque tableau de bord s\'exporte en Excel (une feuille par bloc) et en PDF.'),
  puce([b('Périmètres de consultation : '), 'un contrôleur ou un profil de consultation ne voit que les départements ou agences qui lui sont attribués (Paramètres → Périmètres de consultation).']),

  h1('11. Documents et exports'),
  puce('Chaque liste a un bouton « Exporter » (Excel ou PDF) qui reprend toutes les lignes correspondant aux filtres, numérotées.'),
  puce('Chaque demande se télécharge en PDF de présentation (menu « Documents » de la fiche) : statut, montants, demandeur, contenu, circuit de validation, paiements, pièces.'),
  puce('Pour les missions, le même menu propose l\'ordre de mission (une fois la mission approuvée) et la note de frais (nom, matricule et date sur la même ligne), au format de la société.'),
  puce([b('Demande de paiement / de remboursement : '), 'pour les demandes de paiement, de remboursement et de frais de réception client, le menu « Documents » produit le formulaire papier de la société : nom et prénoms, matricule, service, montant en chiffres et en lettres, motif, bénéficiaire, cadre « À remplir obligatoirement » repris du règlement, signatures. Pour une réception client, le client, le lieu, la date et le nombre de participants y figurent.']),
  puce('Les mentions de ces documents (logo, téléphone, fax, centre des impôts, régime d\'imposition, références qualité des formulaires) se règlent dans Paramètres → Société.'),

  h1('12. L\'application mobile'),
  p('L\'application UbiFlow (Android et iPhone) se connecte avec le même matricule et le même mot de passe que le web. Elle comporte quatre onglets : Accueil, Demandes, À valider, Profil.'),
  tableau(['Je veux…', 'Sur mobile'], [
    ['Voir ma synthèse', 'Onglet Accueil : mêmes indicateurs que sur le web, puis « À faire » avec un bouton par action, mes demandes en cours et les notifications.'],
    ['Créer une demande', 'Action rapide de l\'accueil ou bouton « Nouvelle demande » de l\'onglet Demandes ; pour une mission, l\'estimation des frais s\'affiche pendant la saisie.'],
    ['Joindre un justificatif', 'Fiche de la demande → « Ajouter une pièce » : prendre une photo, choisir dans la galerie ou choisir un fichier (PDF, Word, Excel).'],
    ['Télécharger un document', 'Icône PDF en haut de la fiche : fiche, ordre de mission, note de frais, demande de paiement.'],
    ['Valider', 'Onglet À valider → fiche → Approuver, Retourner pour correction ou Rejeter (commentaire obligatoire pour retourner ou rejeter).'],
    ['Clôturer une mission', 'Fiche → « Déclarer mes dépenses réelles » → joindre le rapport → « Soumettre la clôture ».'],
    ['Être prévenu', 'Notifications push (à autoriser au premier lancement) et cloche de l\'accueil.'],
    ['Déléguer mes validations', 'Onglet Profil → Mes délégations → Déléguer.'],
  ], [2600, 6700]),
  espace(),
  p([b('Restent sur le web : '), 'l\'administration et le paramétrage (types, circuits, barèmes, calendrier, société), la trésorerie (paiements, reversements, contrôle des clôtures), la correction d\'un montant par un valideur, la délégation limitée à certains types et les tableaux de bord détaillés avec leurs exports.']),
];


const doc = new Document({
  creator: 'UbiFlow', title: 'Règles de gestion et utilisation d\'UbiFlow',
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
      new TextRun({ text: 'UbiFlow — support de formation — page ', font: F, size: 16, color: GRIS }),
      new TextRun({ children: [PageNumber.CURRENT], font: F, size: 16, color: GRIS })] })] }) },
    children: contenu,
  }],
});
Packer.toBuffer(doc).then(buf => fs.writeFileSync(process.argv[2], buf));
