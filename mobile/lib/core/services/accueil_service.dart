// lib/core/services/accueil_service.dart
//
// Accueil de synthèse (même API que le web) et notifications in-app.

import '../api/api_client.dart';

class AccueilService {
  /// Vue de synthèse : profil choisi (collaborateur, valideur, direction, finances)
  /// ou, à défaut, celui que le serveur retient pour l'utilisateur.
  Future<Map<String, dynamic>> accueil({String? profil}) async {
    final res = await apiClient.get('/accueil/', params: {if (profil != null) 'profil': profil});
    return Map<String, dynamic>.from(res.data as Map);
  }

  Future<List<Map<String, dynamic>>> notifications({bool nonLues = false, int page = 1}) async {
    final res = await apiClient.get('/notifications/', params: {if (nonLues) 'non_lues': 1, 'page': page});
    final data = res.data;
    return List<Map<String, dynamic>>.from((data is Map ? data['results'] : data) as List? ?? const []);
  }

  Future<int> nonLues() async {
    final res = await apiClient.get('/notifications/compteur/');
    return (res.data as Map)['non_lues'] as int? ?? 0;
  }

  Future<void> lire(int id) => apiClient.post('/notifications/$id/lire/', data: {});

  Future<void> toutLire() => apiClient.post('/notifications/tout-lire/', data: {});
}

final accueilService = AccueilService();

/// Identifiant de la demande visée par un lien du web (« /demandes/12 ») ou null.
int? demandeDuLien(String? lien) {
  final m = RegExp(r'^/demandes/(\d+)').firstMatch(lien ?? '');
  return m == null ? null : int.tryParse(m.group(1)!);
}
