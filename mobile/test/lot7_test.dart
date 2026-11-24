// Lot 7 : liens des notifications, fichiers, dates de mission, formulaire de demande.

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'package:ubiflow/core/api/api_client.dart';
import 'package:ubiflow/core/services/accueil_service.dart';
import 'package:ubiflow/core/widgets/remix.dart';
import 'package:ubiflow/core/services/souvenir_service.dart';
import 'package:ubiflow/features/accueil/accueil_screen.dart' show ilYA;
import 'package:ubiflow/features/demandes/demande_form_screen.dart';
import 'package:ubiflow/features/demandes/fichiers.dart';
import 'package:ubiflow/features/demandes/mission_saisie.dart';

void main() {
  setUpAll(() => initializeDateFormatting('fr_FR', null));

  test('trop de demandes de code : le délai du serveur est affiché', () {
    DioException erreur(dynamic corps) {
      final req = RequestOptions(path: '/users/forgot-password/');
      return DioException(requestOptions: req, response: Response(requestOptions: req, statusCode: 429, data: corps));
    }
    expect(messageErreurApi(erreur({'error': 'Trop de demandes de code pour ce matricule. Veuillez réessayer dans 30 minutes.'})),
        'Trop de demandes de code pour ce matricule. Veuillez réessayer dans 30 minutes.');
    expect(messageErreurApi(erreur(null)), 'Trop de tentatives. Réessayez dans quelques minutes.');
  });

  test('lien de notification vers la demande', () {
    expect(demandeDuLien('/demandes/12'), 12);
    expect(demandeDuLien('/demandes/12/cloture'), 12);
    expect(demandeDuLien('/demandes?statut=a_corriger'), isNull);
    expect(demandeDuLien(null), isNull);
  });

  test('icônes Remix : mêmes classes que le web', () {
    expect(Remix.deClasse('ri-road-map-line'), Remix.roadMap);
    expect(Remix.roadMap.fontFamily, 'Remixicon');
    expect(Remix.deClasse('ri-inconnue'), isNull);
  });

  test('se souvenir de moi : prénom et initiales de la carte « Bon retour »', () {
    const s = Souvenir('M004', 'KONE Fatou');
    expect(s.prenom, 'Fatou');
    expect(s.initiales, 'FK');
    expect(const Souvenir('M009', '').initiales, 'M');
  });

  test('ancienneté lisible', () {
    expect(ilYA(DateTime.now().subtract(const Duration(minutes: 20)).toIso8601String()), 'il y a 20 min');
    expect(ilYA(DateTime.now().subtract(const Duration(hours: 3)).toIso8601String()), 'il y a 3 h');
    expect(ilYA(DateTime.now().subtract(const Duration(days: 1, hours: 2)).toIso8601String()), 'hier');
    expect(ilYA(null), '');
  });

  test('taille lisible des pièces jointes', () {
    expect(tailleLisible(512), '512 o');
    expect(tailleLisible(2048), '2 Ko');
    expect(tailleLisible(3 * 1024 * 1024 + 200000), '3,2 Mo');
  });

  test('date et heure de mission au format de l\'API', () {
    expect(versIsoLocal(DateTime(2026, 12, 2, 8, 5)), '2026-12-02T08:05');
  });

  testWidgets('formulaire : champs du type, montant et boutons', (tester) async {
    const frc = {
      'id': 1, 'code': 'FRC', 'libelle': 'Frais de réception client', 'famille': 'simple', 'avec_montant': true,
      'description': 'Réception d\'un client', 'parametres': {},
      'champs': [
        {'code': 'client', 'libelle': 'Client', 'nature': 'texte', 'obligatoire': true, 'options': [], 'aide': ''},
        {'code': 'date_reception', 'libelle': 'Date de la réception', 'nature': 'date', 'obligatoire': true, 'options': [], 'aide': ''},
        {'code': 'mode', 'libelle': 'Mode', 'nature': 'liste', 'obligatoire': false, 'options': ['Virement', 'Chèque'], 'aide': ''},
      ],
    };
    await tester.pumpWidget(const MaterialApp(home: DemandeFormScreen(type: frc)));
    expect(find.text('Objet *'), findsOneWidget);
    expect(find.text('Montant demandé (XOF) *'), findsOneWidget);
    expect(find.text('Client *'), findsOneWidget);
    expect(find.text('Date de la réception *'), findsOneWidget);
    expect(find.text('Mode'), findsOneWidget);
    expect(find.text('Soumettre'), findsOneWidget);
    expect(find.text('Enregistrer le brouillon'), findsOneWidget);
  });

  testWidgets('formulaire : erreurs de l\'API sous les champs', (tester) async {
    const pai = {
      'id': 4, 'code': 'PAI', 'libelle': 'Demande de paiement', 'famille': 'simple', 'avec_montant': true, 'parametres': {},
      'champs': [{'code': 'beneficiaire', 'libelle': 'Bénéficiaire', 'nature': 'texte', 'obligatoire': true, 'options': [], 'aide': ''}],
    };
    await tester.pumpWidget(const MaterialApp(
      home: DemandeFormScreen(type: pai, erreurs: {'objet': "L'objet est obligatoire.", 'donnees': {'beneficiaire': ['Champ obligatoire.']}}),
    ));
    expect(find.text("L'objet est obligatoire."), findsOneWidget);
    expect(find.text('Champ obligatoire.'), findsOneWidget);
  });
}
