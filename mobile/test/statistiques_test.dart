import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:cantine_app/features/statistiques/statistiques_screen.dart';

DonneesStats _donnees() => const DonneesStats(
      resume: {
        'kpis': {'taux_retrait': 93.5, 'non_retires': 4}
      },
      indicateurs: {
        'kpis': {'nb_repas': 120, 'nb_supplements': 80},
        'par_plat': [
          {'plat': 'Garba', 'commandes': 60, 'popularite': 50.0},
          {'plat': 'Attiéké poisson', 'commandes': 40, 'popularite': 33.3},
        ],
        'montants': {
          'total_employes': 120000,
          'total_prestataires': 132000,
          'par_mois': [
            {
              'libelle': 'Novembre 2026',
              'court': 'nov. 26',
              'employes': 120000,
              'prestataires': 132000
            },
          ],
        },
      },
      complements: {
        'desserts': {
          'part_avec_dessert': 66.7,
          'par_dessert': [
            {'plat': 'Salade de fruits', 'choisis': 50, 'part': 62.5}
          ]
        },
        'participation': {
          'taux_participation': 75.0,
          'commandeurs': 30,
          'effectif': 40,
          'par_agence': [
            {'agence': 'Yopougon', 'taux_participation': 75.0, 'repas': 120}
          ]
        },
        'affluence': {
          'nb_retraits': 110,
          'pointe': {'tranche': '12:15'}
        },
      },
    );

void main() {
  setUpAll(() => initializeDateFormatting('fr_FR'));

  Future<void> monter(WidgetTester tester, {bool prestataire = false}) async {
    tester.view.physicalSize = const Size(1080, 2600);
    tester.view.devicePixelRatio = 2.5;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(MaterialApp(
        home: StatistiquesScreen(
            prestataire: prestataire,
            chargeur: (_, __, ___) async => _donnees())));
    await tester.pumpAndSettle();
  }

  testWidgets('gestionnaire : chiffres clés, plats, participation',
      (tester) async {
    await monter(tester);
    expect(find.text('Taux de retrait'), findsOneWidget);
    expect(find.text('Participation'), findsOneWidget);
    expect(find.text('12:15'), findsOneWidget);
    expect(find.text('Garba'), findsOneWidget);
    await tester.dragUntilVisible(find.text('Yopougon'),
        find.byType(ListView).first, const Offset(0, -200));
    expect(find.text('Yopougon'), findsOneWidget);
  });

  testWidgets('prestataire : sans montants des employés', (tester) async {
    await monter(tester, prestataire: true);
    expect(find.text('Montant dû'), findsOneWidget);
    expect(find.text('Facturé aux employés'), findsNothing);
    expect(find.text('Participation par agence'), findsNothing);
  });
}
