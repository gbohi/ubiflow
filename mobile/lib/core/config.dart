// lib/core/config.dart
//
// ⚠️ SEUL FICHIER À MODIFIER pour changer l'URL du serveur.
// Par défaut : backend local vu depuis l'émulateur Android (10.0.2.2:8000).

class AppConfig {
  // URL de base du serveur Django (sans slash final)
  static const serverUrl = 'http://10.0.2.2:8000';

  // Base URL pour les appels API DRF
  static const apiBaseUrl = '$serverUrl/api/api';

  // Endpoint JWT (hors /api/api)
  static const tokenUrl = '$apiBaseUrl/token/';
  static const refreshUrl = '$apiBaseUrl/token/refresh/';
}
