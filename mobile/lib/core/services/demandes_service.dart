// lib/core/services/demandes_service.dart
//
// Demandes et validations (lot 2) : consultation et décisions des valideurs.

import '../api/api_client.dart';

class DemandesService {
  /// Mes demandes (page 1, les plus récentes), filtrées par statut si besoin.
  Future<List<Map<String, dynamic>>> mesDemandes({String statut = ''}) async {
    final res = await apiClient.get('/demandes/',
        params: {'vue': 'mes', if (statut.isNotEmpty) 'statut': statut, 'page_size': 50});
    return List<Map<String, dynamic>>.from(res.data['results'] as List);
  }

  Future<Map<String, dynamic>> demande(int id) async {
    final res = await apiClient.get('/demandes/$id/');
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<List<Map<String, dynamic>>> historique(int id) async {
    final res = await apiClient.get('/demandes/$id/historique/');
    return List<Map<String, dynamic>>.from(res.data as List);
  }

  /// Validations en attente (les miennes et celles reçues par délégation).
  Future<List<Map<String, dynamic>>> aValider() async {
    final res = await apiClient.get('/taches/', params: {'etat': 'en_attente', 'page_size': 100});
    return List<Map<String, dynamic>>.from(res.data['results'] as List);
  }

  Future<Map<String, dynamic>> compteurs() async {
    final res = await apiClient.get('/demandes/compteurs/');
    return Map<String, dynamic>.from(res.data as Map);
  }

  /// approuver | rejeter | retourner (motif obligatoire pour les deux derniers).
  Future<String> agir(int tache, String action, String motif) async {
    final res = await apiClient.post('/taches/$tache/$action/', data: {'motif': motif});
    return (res.data as Map)['statut_libelle'] as String? ?? '';
  }
}

final demandesService = DemandesService();
