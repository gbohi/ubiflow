// lib/features/demandes/commun.dart
//
// Éléments partagés des écrans de demandes : pastille de statut, montant.

import 'package:flutter/material.dart';
import '../../core/widgets/common_widgets.dart';
import '../../core/widgets/remix.dart';

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

/// Pictogramme et teinte d'un type de demande : mêmes icônes Remix et mêmes
/// teintes que sur le web (fond pâle, pictogramme foncé).
const Map<String, (IconData, Color, Color)> typesDemande = {
  'MLO': (Remix.roadMap, Color(0xFF1F9D5C), Color(0xFFE8F9F0)),
  'MHP': (Remix.flightTakeoff, Color(0xFF1D5FA8), Color(0xFFEAF2FC)),
  'FRC': (Remix.restaurant, Color(0xFFA15C07), Color(0xFFFFF4E0)),
  'PAI': (Remix.bankCard, Color(0xFFC93B3B), Color(0xFFFDECEC)),
  'RMB': (Remix.refund2, Color(0xFF1F9D5C), Color(0xFFE8F9F0)),
  'FCM': (Remix.addBox, Color(0xFF1D5FA8), Color(0xFFEAF2FC)),
  'ANN': (Remix.closeCircle, Color(0xFF5B6B7D), Color(0xFFEEF1F5)),
};

class IconeTypeDemande extends StatelessWidget {
  final String? code;
  final double taille;
  const IconeTypeDemande(this.code, {super.key, this.taille = 38});

  @override
  Widget build(BuildContext context) {
    final t = typesDemande[code] ?? (Remix.fileText, const Color(0xFF5B6B7D), const Color(0xFFEEF1F5));
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      width: taille, height: taille,
      decoration: BoxDecoration(color: isDark ? t.$2.withAlpha(40) : t.$3, borderRadius: BorderRadius.circular(taille * 0.28)),
      child: Icon(t.$1, color: isDark ? t.$3 : t.$2, size: taille * 0.5),
    );
  }
}

/// Carte d'une demande dans une liste, lisible d'un coup d'œil :
/// référence et montant sur la première ligne, objet sur la deuxième,
/// puis une ligne discrète (type, demandeur, étape) et le statut.
class CarteListeDemande extends StatelessWidget {
  final String? typeCode;
  final String reference;
  final String montant;
  final String objet;
  final String details;
  final Widget? statut;
  final List<Widget> alertes;
  final VoidCallback onTap;
  const CarteListeDemande({super.key, required this.typeCode, required this.reference, required this.montant,
      required this.objet, required this.details, this.statut, this.alertes = const [], required this.onTap});

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final secondaire = Theme.of(context).textTheme.bodySmall?.color ?? Colors.grey;
    return Card(
      margin: EdgeInsets.zero,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            IconeTypeDemande(typeCode),
            const SizedBox(width: 12),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(child: Text(reference, maxLines: 1, overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14.5))),
                const SizedBox(width: 8),
                Text(montant, style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5, color: cs.onSurface)),
              ]),
              const SizedBox(height: 3),
              Text(objet.isEmpty ? '—' : objet, maxLines: 2, overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontSize: 14, color: cs.onSurface, height: 1.3)),
              const SizedBox(height: 3),
              Text(details, maxLines: 2, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 12.5, color: secondaire)),
              ...alertes,
              if (statut != null) ...[const SizedBox(height: 8), statut!],
            ])),
          ]),
        ),
      ),
    );
  }
}
