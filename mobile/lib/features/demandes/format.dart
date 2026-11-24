// lib/features/demandes/format.dart
//
// Formatage des montants et des dates (sans dépendance d'interface : testable seul).

import 'package:intl/intl.dart';

String montant(dynamic valeur, [String devise = '']) {
  if (valeur == null || valeur == '') return '—';
  final n = num.tryParse(valeur.toString());
  if (n == null) return valeur.toString();
  final texte = NumberFormat.decimalPattern('fr_FR').format(n).replaceAll(' ', ' ');
  return devise.isEmpty ? texte : '$texte $devise';
}

String dateCourte(dynamic iso) {
  if (iso == null || iso == '') return '—';
  final d = DateTime.tryParse(iso.toString());
  return d == null ? iso.toString() : DateFormat('dd/MM/yyyy HH:mm', 'fr_FR').format(d.toLocal());
}

// ── Missions (lot 3) ──────────────────────────────────────────

const rubriquesMission = {
  'per_diem': 'Indemnités journalières', 'transport': 'Transport', 'visa': 'Frais de visa',
  'aerien': 'Transport aérien', 'hebergement': 'Hébergement', 'autres': 'Autres frais',
};

const moyensTransport = {
  'transport_commun': 'Transport en commun', 'vehicule_personnel': 'Véhicule personnel',
  'vehicule_service': 'Véhicule de service', 'avion': 'Avion', 'autre': 'Autre',
};

/// Lignes « libellé / valeur » décrivant la mission saisie.
List<(String, String)> resumeMission(Map mission) {
  final pays = mission['pays_destination_libelle'];
  final trajet = '${mission['ville_depart_libelle'] ?? '—'} → ${mission['ville_destination_libelle'] ?? '—'}';
  final jours = mission['nombre_jours'];
  return [
    ('Motif', '${mission['motif'] ?? '—'}'),
    ('Trajet', mission['type_mission'] == 'hors_pays' && pays != null ? '$trajet ($pays)' : trajet),
    ('Période', 'du ${dateCourte(mission['depart_le'])} au ${dateCourte(mission['retour_le'])}'
        '${jours != null ? ' · $jours jour(s)' : ''}'),
    ('Transport', '${moyensTransport[mission['moyen_transport']] ?? mission['moyen_transport'] ?? '—'}'
        ' · ${mission['trajet'] == 'aller_simple' ? 'aller simple' : 'aller-retour'}'),
  ];
}

/// Récapitulatif figé : (rubrique, détail, montant en devise de référence).
List<(String, String, String)> lignesRecap(Map calcul) {
  final ref = calcul['devise_reference'] as String? ?? '';
  return [
    for (final l in List<Map>.from(calcul['lignes'] as List? ?? []))
      (rubriquesMission[l['rubrique']] ?? '${l['rubrique']}', '${l['libelle']}', montant(l['montant_ref'], ref)),
  ];
}

// ── Paiements (lot 4) ─────────────────────────────────────────

/// Synthèse des paiements : (libellé, valeur) — approuvé, payé, reste, puis un
/// libellé par règlement (les règlements annulés sont signalés).
List<(String, String)> resumePaiements(Map d) {
  final devise = d['devise'] as String? ?? '';
  final annulee = d['statut'] == 'annulee';
  final lignes = <(String, String)>[
    ('Statut', '${d['statut_financier_libelle'] ?? '—'}'),
    ('Approuvé', montant(d['montant_approuve'] ?? d['montant_demande'], devise)),
    ('Payé', montant(d['montant_paye'] ?? 0, devise)),
    ('Reste à payer', montant(annulee ? 0 : (d['solde'] ?? 0), devise)),
  ];
  for (final r in List<Map>.from(d['reglements'] as List? ?? [])) {
    final ref = (r['reference'] as String? ?? '').isEmpty ? '' : ' · ${r['reference']}';
    lignes.add(('${r['annule'] == true ? 'Paiement annulé' : 'Paiement'} du ${dateCourte(r['date_paiement']).split(' ').first}',
        '${montant(r['montant'], r['devise'] as String? ?? devise)} · ${r['mode_libelle']}$ref'));
  }
  for (final r in List<Map>.from(d['reversements'] as List? ?? [])) {
    lignes.add(('Reversement (${'${r['etat_libelle']}'.toLowerCase()})', montant(r['montant_du'], r['devise'] as String? ?? devise)));
  }
  return lignes;
}

bool aDesPaiements(Map d) =>
    d['statut_financier'] != 'sans_objet' ||
    (d['reglements'] as List? ?? []).isNotEmpty ||
    (d['reversements'] as List? ?? []).isNotEmpty;
