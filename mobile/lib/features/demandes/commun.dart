// lib/features/demandes/commun.dart
//
// Éléments partagés des écrans de demandes : pastille de statut, montant.

import 'package:flutter/material.dart';
import '../../core/widgets/common_widgets.dart';

export 'format.dart';

const Map<String, (String, TonPastille, IconData)> statutsDemande = {
  'brouillon': ('Brouillon', TonPastille.gris, Icons.edit_note_rounded),
  'en_validation': ('En validation', TonPastille.bleu, Icons.hourglass_top_rounded),
  'a_corriger': ('À corriger', TonPastille.or, Icons.undo_rounded),
  'rejetee': ('Rejetée', TonPastille.rouge, Icons.cancel_rounded),
  'approuvee': ('Approuvée', TonPastille.vert, Icons.check_circle_rounded),
  'en_attente_cloture': ('En attente de clôture', TonPastille.or, Icons.assignment_late_outlined),
  'cloturee': ('Clôturée', TonPastille.gris, Icons.lock_outline_rounded),
  'annulee': ('Annulée', TonPastille.gris, Icons.block_rounded),
};

class PastilleDemande extends StatelessWidget {
  final String statut;
  const PastilleDemande(this.statut, {super.key});

  @override
  Widget build(BuildContext context) {
    final s = statutsDemande[statut] ?? (statut, TonPastille.gris, Icons.circle_outlined);
    return PastilleStatut(label: s.$1, ton: s.$2, icone: s.$3);
  }
}
