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
}
