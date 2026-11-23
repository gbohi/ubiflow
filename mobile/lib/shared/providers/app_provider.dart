// lib/shared/providers/app_provider.dart

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../core/api/api_client.dart';
import '../models/models.dart';
import '../../core/services/auth_service.dart';

// ══════════════════════════════════════════════════════════════
// THEME PROVIDER — avec persistance SharedPreferences
// ══════════════════════════════════════════════════════════════

class ThemeProvider extends ChangeNotifier {
  static const _key = 'theme_mode';

  ThemeMode _mode = ThemeMode.light;
  ThemeMode get mode => _mode;
  bool get isDark => _mode == ThemeMode.dark;

  ThemeProvider() {
    _loadTheme();
  }

  /// Charge le thème sauvegardé au démarrage
  Future<void> _loadTheme() async {
    final prefs = await SharedPreferences.getInstance();
    final isDark = prefs.getBool(_key) ?? false;
    _mode = isDark ? ThemeMode.dark : ThemeMode.light;
    notifyListeners();
  }

  /// Sauvegarde le thème à chaque changement
  Future<void> _saveTheme(bool isDark) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_key, isDark);
  }

  void toggle() {
    _mode = isDark ? ThemeMode.light : ThemeMode.dark;
    _saveTheme(_mode == ThemeMode.dark);
    notifyListeners();
  }

  void setMode(ThemeMode mode) {
    _mode = mode;
    _saveTheme(mode == ThemeMode.dark);
    notifyListeners();
  }
}

// ══════════════════════════════════════════════════════════════
// AUTH PROVIDER
// ══════════════════════════════════════════════════════════════

/// Résultat de la restauration de session au démarrage.
enum EtatSession { connecte, deconnecte, horsLigne }

class AuthProvider extends ChangeNotifier {
  AuthUser? _user;
  bool _loading = false;
  String? _error;

  AuthUser? get user => _user;
  bool get loading => _loading;
  String? get error => _error;
  bool get isLoggedIn => _user != null;

  /// Basé sur le NOM des rôles renvoyé par l'API (avant : IDs de groupe
  /// 3 et 4 codés en dur, faux dès que la base est recréée).
  bool get isGestionnaire => _user?.isGestionnaire ?? false;

  /// Tests : session ouverte sans serveur
  @visibleForTesting
  set utilisateurPourTest(AuthUser? u) {
    _user = u;
    notifyListeners();
  }

  AuthProvider() {
    // Refresh token refusé par le serveur → retour à l'écran de connexion
    apiClient.onSessionExpiree = () {
      if (_user != null) {
        _user = null;
        notifyListeners();
      }
    };
  }

  /// Au démarrage : si un jeton est stocké, recharge le profil.
  /// Avant, l'utilisateur retombait toujours sur l'écran de connexion
  /// au redémarrage de l'app malgré un jeton valide.
  /// Hors ligne (serveur injoignable) : les jetons sont conservés et
  /// l'écran propose de réessayer, au lieu de renvoyer à la connexion.
  Future<EtatSession> restoreSession() async {
    if (!await authService.isLoggedIn()) return EtatSession.deconnecte;
    try {
      _user = await authService.me();
      notifyListeners();
      return EtatSession.connecte;
    } on DioException catch (e) {
      final code = e.response?.statusCode;
      if (code == 401 || code == 403) {
        await authService.logout();
        return EtatSession.deconnecte;
      }
      return EtatSession.horsLigne;
    } catch (_) {
      return EtatSession.horsLigne;
    }
  }

  Future<bool> login(String username, String password) async {
    // Appui répété (bouton + touche « Entrée ») : une seule connexion
    if (_loading) return false;
    _loading = true;
    _error = null;
    notifyListeners();
    try {
      _user = await authService.login(username, password);

      _loading = false;
      notifyListeners();
      return true;
    } catch (e) {
      _error = _parseError(e);
      _loading = false;
      notifyListeners();
      return false;
    }
  }

  // ── Photo de profil ─────────────────────────────────────────
  bool _photoEnCours = false;
  bool get photoEnCours => _photoEnCours;

  /// null si tout s'est bien passé, sinon le message d'erreur à afficher.
  Future<String?> changerPhoto(List<int> octets, String nomFichier) =>
      _majPhoto(() => authService.envoyerPhoto(octets, nomFichier));

  Future<String?> retirerPhoto() => _majPhoto(authService.retirerPhoto);

  Future<String?> _majPhoto(Future<AuthUser> Function() appel) async {
    if (_photoEnCours) return null;
    final demandeur = _user?.id;
    _photoEnCours = true;
    notifyListeners();
    try {
      final profil = await appel();
      // Déconnexion ou changement de compte pendant l'envoi : on ignore
      if (_user?.id == demandeur) _user = profil;
      return null;
    } catch (e) {
      return messageErreurApi(e) ?? "L'envoi de la photo a échoué.";
    } finally {
      _photoEnCours = false;
      notifyListeners();
    }
  }

  bool _deconnexionEnCours = false;

  Future<void> logout() async {
    // Double appui / double confirmation : une seule déconnexion
    if (_deconnexionEnCours) return;
    _deconnexionEnCours = true;
    _loading = true;
    notifyListeners();
    try {
      await authService.logout();
    } finally {
      _deconnexionEnCours = false;
      _loading = false;
      _error = null;
      _user = null;
      notifyListeners();
    }
  }

  String _parseError(dynamic e) {
    if (e is DioException) {
      final code = e.response?.statusCode;
      // Message du serveur (« Matricule ou mot de passe incorrect, ou compte désactivé. »)
      if (code == 401) {
        return messageErreurApi(e) ?? 'Matricule ou mot de passe incorrect.';
      }
      if (code == 429) {
        return 'Trop de tentatives. Réessayez dans quelques minutes.';
      }
      if (e.response == null) return 'Impossible de contacter le serveur';
    }
    return messageErreurApi(e) ?? 'Une erreur est survenue';
  }
}
