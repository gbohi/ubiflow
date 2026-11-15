// Suppléments (desserts) : ligne de commande, fiche, comptoir.

import 'package:cantine_app/features/commandes/commandes_screen.dart';
import 'package:cantine_app/shared/models/models.dart';
import 'package:cantine_app/shared/models/prestataire_models.dart';
import 'package:cantine_app/shared/providers/app_provider.dart';
import 'package:cantine_app/shared/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:provider/provider.dart';

Commande _commande(
        {List<Map<String, dynamic>> supplements = const [],
        int disponibles = 0}) =>
    Commande.fromJson({
      'id': 9,
      'statut': 'en_attente',
      'date_commande': '2099-11-01T09:00:00Z',
      'plat_detail': {
        'id': 7,
        'nom': 'Garba',
        'type_plat_libelle': 'Plat principal',
        'images': []
      },
      'menu_detail': {
        'id': 40,
        'date_menu': '2099-11-19',
        'agence_id': 1,
        'agence_nom': 'Yopougon',
        'typeequipe_id': 1,
        'typeequipe_libelle': 'Jour',
        'menu_plats': [],
        'date_limite_annulation': '2099-11-17T00:00:00Z',
      },
      'user_nom': 'KONÉ Ibrahim',
      'mode_paiement': 'retenue',
      'mode_paiement_modifiable': true,
      'supplements': supplements,
      'supplements_disponibles': disponibles,
    });

final _salade = {
  'id': 10,
  'statut': 'en_attente',
  'mode_paiement': 'offert',
  'famille_id': 1,
  'famille': 'Dessert',
  'inclus': true,
  'plat_detail': {'id': 31, 'nom': 'Salade de fruits', 'images': []},
};

Widget _app(Widget w) => MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => CommandeProvider()),
        ChangeNotifierProvider(create: (_) => FacturationProvider()),
      ],
      child: MaterialApp(
          theme: AppTheme.light(),
          home: Scaffold(body: SingleChildScrollView(child: w))),
    );

void main() {
  setUpAll(() => initializeDateFormatting('fr_FR'));

  test('modèles : supplément de commande, comptoir', () {
    final c = _commande(supplements: [_salade]);
    expect(c.supplements.single.platDetail?.nom, 'Salade de fruits');
    expect(c.supplements.single.inclus, isTrue);
    final cpt = CommandeComptoir.fromJson(
        {'commande_id': 10, 'plat': 'Salade de fruits', 'famille': 'Dessert'});
    expect(cpt.famille, 'Dessert');
    expect(
        CommandeComptoir.fromJson({'commande_id': 9, 'plat': 'Garba'}).famille,
        isNull);
  });

  for (final largeur in [390.0, 320.0]) {
    testWidgets(
        'mes commandes : dessert sous le plat, fiche « Changer de dessert » ($largeur px)',
        (tester) async {
      tester.view.physicalSize = Size(largeur, 1600);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final c = _commande(supplements: [_salade]);
      await tester.pumpWidget(_app(Column(children: [
        LigneCommande(commande: c),
        LigneCommande(commande: _commande(disponibles: 2)),
        SizedBox(
            height: 900,
            child: DetailCommandeSheet(commandeId: c.id, initiale: c)),
      ])));
      await tester.pump(const Duration(milliseconds: 300));
      expect(tester.takeException(), isNull);
      expect(find.byKey(const Key('ligne-dessert-10')), findsOneWidget);
      expect(find.byKey(const Key('bloc-dessert')), findsOneWidget);
      expect(find.text('Changer de dessert'), findsOneWidget);
      expect(find.text('inclus'), findsWidgets);
    });
  }
}
