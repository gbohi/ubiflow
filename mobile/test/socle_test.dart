// Socle de l'application : profil utilisateur et rôles.

import 'package:flutter_test/flutter_test.dart';
import 'package:ubiflow/shared/models/models.dart';

void main() {
  AuthUser u(Map<String, dynamic> json) =>
      AuthUser.fromJson({'id': 1, 'username': 'agent1', ...json});

  test('rôles et libellé', () {
    expect(u({'roles': ['employe']}).libelleRole, 'Employé');
    expect(u({'roles': ['gestionnaire']}).isGestionnaire, isTrue);
    expect(u({'roles': ['admin']}).isAdmin, isTrue);
    expect(u({'roles': ['admin']}).isGestionnaire, isTrue);
    expect(u({'roles': ['super_admin']}).libelleRole, 'Administrateur');
    expect(u({'roles': ['employe']}).isGestionnaire, isFalse);
  });

  test('affectations en cours lues dans le profil', () {
    final user = u({
      'nom': 'KONE',
      'prenom': 'Fatou',
      'derniere_agence': {'agence': 3, 'agence_nom': 'Abidjan'},
      'dernier_service': {'service_libelle': 'Finances'},
      'dernier_poste': {'poste_libelle': 'Comptable'},
    });
    expect(user.fullName, 'KONE Fatou');
    expect(user.initiales, 'FK');
    expect(user.derniereAgence, 'Abidjan');
    expect(user.derniereAgenceId, 3);
    expect(user.dernierService, 'Finances');
    expect(user.dernierPoste, 'Comptable');
  });
}
