// lib/core/services/demandes_service.dart
//
// Demandes : consultation, création et modification (brouillon, correction),
// soumission, pièces jointes, documents PDF, clôture des missions, validations,
// commentaires, délégations.

import 'package:dio/dio.dart';
import '../api/api_client.dart';

List<Map<String, dynamic>> _liste(dynamic data) =>
    List<Map<String, dynamic>>.from((data is Map ? data['results'] : data) as List? ?? const []);

Map<String, dynamic> _objet(dynamic data) => Map<String, dynamic>.from(data as Map);

class DemandesService {
  // ── Consultation ──────────────────────────────────────────

  /// Mes demandes (page 1, les plus récentes), filtrées par statut si besoin.
  Future<List<Map<String, dynamic>>> mesDemandes({String statut = '', String famille = ''}) async {
    final res = await apiClient.get('/demandes/', params: {
      'vue': 'mes', if (statut.isNotEmpty) 'statut': statut, if (famille.isNotEmpty) 'famille': famille, 'page_size': 50});
    return _liste(res.data);
  }

  Future<Map<String, dynamic>> demande(int id) async => _objet((await apiClient.get('/demandes/$id/')).data);

  Future<List<Map<String, dynamic>>> historique(int id) async =>
      _liste((await apiClient.get('/demandes/$id/historique/')).data);

  Future<Map<String, dynamic>> compteurs() async => _objet((await apiClient.get('/demandes/compteurs/')).data);

  // ── Création et modification ──────────────────────────────

  /// Types de demande ouverts à la création (circuit publié).
  Future<List<Map<String, dynamic>>> types() async {
    final res = await apiClient.get('/types-demande/');
    return _liste(res.data).where((t) => t['circuit_publie'] != null && t['actif'] != false).toList();
  }

  Future<List<Map<String, dynamic>>> parentsPossibles(int typeDemande) async =>
      _liste((await apiClient.get('/demandes/parents-possibles/', params: {'type_demande': typeDemande})).data);

  Future<Map<String, dynamic>> creer(Map<String, dynamic> d) async =>
      _objet((await apiClient.post('/demandes/', data: d)).data);

  Future<Map<String, dynamic>> modifier(int id, Map<String, dynamic> d) async =>
      _objet((await apiClient.patch('/demandes/$id/', data: d)).data);

  Future<Map<String, dynamic>> soumettre(int id) async =>
      _objet((await apiClient.post('/demandes/$id/soumettre/', data: {'motif': ''})).data);

  Future<void> supprimer(int id) => apiClient.delete('/demandes/$id/');

  Future<Map<String, dynamic>> annuler(int id, String motif) async =>
      _objet((await apiClient.post('/demandes/$id/annuler/', data: {'motif': motif})).data);

  Future<void> commenter(int id, String texte) => apiClient.post('/demandes/$id/commentaires/', data: {'texte': texte});

  // ── Missions ──────────────────────────────────────────────

  Future<List<Map<String, dynamic>>> villes() async => _liste((await apiClient.get('/villes/')).data);

  /// Estimation des frais (sans enregistrement), recalculée pendant la saisie.
  Future<Map<String, dynamic>> calculer(int typeDemande, Map<String, dynamic> mission, {int? demande}) async =>
      _objet((await apiClient.post('/missions/calculer/',
              data: {'type_demande': typeDemande, 'mission': mission, 'demande': demande}))
          .data);

  // ── Pièces jointes et documents ───────────────────────────

  Future<List<Map<String, dynamic>>> typesPieces() async => _liste((await apiClient.get('/types-pieces/')).data);

  Future<void> ajouterDocument(int id, String chemin, String nom, {int? typePiece}) async {
    final form = FormData.fromMap({
      'fichier': await MultipartFile.fromFile(chemin, filename: nom),
      if (typePiece != null) 'type_piece': typePiece,
    });
    await apiClient.post('/demandes/$id/documents/', data: form);
  }

  Future<void> retirerDocument(int id, int doc, String motif) =>
      apiClient.post('/demandes/$id/documents/$doc/retirer/', data: {'motif': motif});

  Future<List<int>> fichierDocument(int id, int doc) => apiClient.getBytes('/demandes/$id/documents/$doc/fichier/');

  /// pdf (fiche) | ordre-mission | note-frais | demande-paiement
  Future<List<int>> pdf(int id, String document) => apiClient.getBytes('/demandes/$id/$document/');

  // ── Clôture des missions ──────────────────────────────────

  Future<Map<String, dynamic>> enregistrerCloture(int id, Map<String, dynamic> d) async =>
      _objet((await apiClient.patch('/demandes/$id/cloture/', data: d)).data);

  Future<Map<String, dynamic>> soumettreCloture(int id) async =>
      _objet((await apiClient.post('/demandes/$id/cloture/soumettre/', data: {'motif': ''})).data);

  // ── Validations ───────────────────────────────────────────

  /// Validations en attente (les miennes et celles reçues par délégation).
  Future<List<Map<String, dynamic>>> aValider() async =>
      _liste((await apiClient.get('/taches/', params: {'etat': 'en_attente', 'page_size': 100})).data);

  /// approuver | rejeter | retourner (motif obligatoire pour les deux derniers).
  Future<String> agir(int tache, String action, String motif) async {
    final res = await apiClient.post('/taches/$tache/$action/', data: {'motif': motif});
    return (res.data as Map)['statut_libelle'] as String? ?? '';
  }

  // ── Délégations ───────────────────────────────────────────

  /// sens : '' (toutes), 'donnees', 'recues'
  Future<List<Map<String, dynamic>>> delegations({String sens = ''}) async =>
      _liste((await apiClient.get('/delegations/', params: {if (sens.isNotEmpty) 'sens': sens})).data);

  Future<void> creerDelegation(Map<String, dynamic> d) => apiClient.post('/delegations/', data: d);

  Future<void> revoquerDelegation(int id) => apiClient.post('/delegations/$id/revoquer/', data: {});

  /// Collaborateurs actifs (id, matricule, libellé) : choix du délégataire.
  Future<List<Map<String, dynamic>>> annuaire() async => _liste((await apiClient.get('/annuaire/')).data);
}

final demandesService = DemandesService();
