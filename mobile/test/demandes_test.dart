// Écrans de demandes : formatage des montants et des dates.

import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:ubiflow/features/demandes/format.dart';

void main() {
  setUpAll(() => initializeDateFormatting('fr_FR', null));

  test('montant au format français', () {
    expect(montant('1500000.00', 'XOF'), '1 500 000 XOF');
    expect(montant(250), '250');
    expect(montant(null), '—');
    expect(montant('abc'), 'abc');
  });

  test('date courte', () {
    expect(dateCourte(null), '—');
    expect(dateCourte('2026-12-10T08:30:00'), '10/12/2026 08:30');
  });

  test('récapitulatif de mission', () {
    final calcul = {
      'devise_reference': 'XOF', 'total_ref': '190000.00',
      'lignes': [
        {'rubrique': 'per_diem', 'libelle': '4 jour(s) × 25 000 XOF', 'montant_ref': '100000.00'},
        {'rubrique': 'transport', 'libelle': 'Tarif ville', 'montant_ref': '30000.00'},
      ],
    };
    final lignes = lignesRecap(calcul);
    expect(lignes.length, 2);
    expect(lignes.first.$1, 'Indemnités journalières');
    expect(lignes.first.$3, montant(100000, 'XOF'));
    final resume = resumeMission({'ville_depart_libelle': 'Abidjan', 'ville_destination_libelle': 'Bouaké',
                                  'nombre_jours': 4, 'moyen_transport': 'transport_commun', 'trajet': 'aller_retour'});
    expect(resume[1].$2, 'Abidjan → Bouaké');
    expect(resume[3].$2, 'Transport en commun · aller-retour');
  });

  test('paiements', () {
    final d = {
      'statut': 'approuvee', 'statut_financier': 'partiellement_payee', 'statut_financier_libelle': 'Partiellement payée',
      'devise': 'XOF', 'montant_approuve': '190000.00', 'montant_paye': '100000.00', 'solde': '90000.00',
      'reglements': [{'date_paiement': '2026-11-24', 'montant': '100000.00', 'devise': 'XOF', 'mode_libelle': 'Virement',
                      'reference': 'VIR-1', 'annule': false}],
      'reversements': [],
    };
    expect(aDesPaiements(d), isTrue);
    final lignes = resumePaiements(d);
    expect(lignes[3].$2, montant(90000, 'XOF'));
    expect(lignes[4].$1, 'Paiement du 24/11/2026');
    expect(lignes[4].$2, '${montant(100000, 'XOF')} · Virement · VIR-1');
    expect(aDesPaiements({'statut_financier': 'sans_objet'}), isFalse);
  });
}
