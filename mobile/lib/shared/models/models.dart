// lib/shared/models/models.dart

import '../../core/config.dart';

// ── Helper : rendre une URL absolue ──────────────────────────
String? _absoluteUrl(String? url) {
  if (url == null || url.isEmpty) return null;
  if (url.startsWith('http://') || url.startsWith('https://')) return url;
  return '${AppConfig.serverUrl}${url.startsWith('/') ? '' : '/'}$url';
}

// ══════════════════════════════════════════════════════════════
// AUTH
// ══════════════════════════════════════════════════════════════

class AuthUser {
  final int id;
  final String username;
  final String email;
  final String nom;
  final String prenom;
  final List<int> groups;

  /// Noms des rôles renvoyés par l'API : super_admin, admin, gestionnaire, employe
  final List<String> roles;
  final bool isActive;
  /// Département en cours (modèle « Service » de l'API)
  final String? dernierService;
  final String? derniereAgence;
  final String? dernierPoste;
  final int? derniereCategoriesalarieId;
  final String? derniereCategoriesalarieLibelle;
  final int? derniereAgenceId;

  /// Photo de profil (URL absolue) ; null → initiales
  final String? photoUrl;

  const AuthUser({
    required this.id,
    required this.username,
    required this.email,
    required this.nom,
    required this.prenom,
    required this.groups,
    this.roles = const [],
    required this.isActive,
    this.dernierService,
    this.derniereAgence,
    this.dernierPoste,
    this.derniereCategoriesalarieId,
    this.derniereCategoriesalarieLibelle,
    this.derniereAgenceId,
    this.photoUrl,
  });

  String get fullName => '$nom $prenom'.trim();

  /// Initiales (prénom puis nom), comme sur le web : « Fatou KONE » → « FK »
  String get initiales {
    final lettres = [prenom, nom]
        .where((m) => m.trim().isNotEmpty)
        .map((m) => m.trim()[0].toUpperCase())
        .join();
    return lettres.isNotEmpty
        ? lettres
        : (username.isNotEmpty ? username[0].toUpperCase() : 'U');
  }

  bool get isAdmin => roles.contains('super_admin') || roles.contains('admin');

  /// Gestionnaire (les administrateurs ont aussi ces droits)
  bool get isGestionnaire => isAdmin || roles.contains('gestionnaire');

  /// « Administrateur », « Gestionnaire » ou « Employé »
  String get libelleRole => isAdmin
      ? 'Administrateur'
      : isGestionnaire
          ? 'Gestionnaire'
          : 'Employé';

  factory AuthUser.fromJson(Map<String, dynamic> json) => AuthUser(
        id: json['id'],
        username: json['username'] ?? '',
        email: json['email'] ?? '',
        nom: json['nom'] ?? '',
        prenom: json['prenom'] ?? '',
        groups: List<int>.from(json['groups'] ?? []),
        roles: List<String>.from(json['roles'] ?? []),
        isActive: json['is_active'] ?? true,
        dernierService: json['dernier_service']?['service_libelle'],
        derniereAgence: json['derniere_agence']?['agence_nom'],
        dernierPoste: json['dernier_poste']?['poste_libelle'],
        derniereCategoriesalarieId: json['derniere_categoriesalarie']
            ?['categoriesalarie'],
        derniereCategoriesalarieLibelle: json['derniere_categoriesalarie']
            ?['categoriesalarie_libelle'],
        derniereAgenceId: json['derniere_agence']?['agence'],
        photoUrl: _absoluteUrl(json['photo_url'] as String?),
      );
}
