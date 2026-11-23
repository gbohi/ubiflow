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
