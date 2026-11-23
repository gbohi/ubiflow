// lib/core/services/auth_service.dart
//
// Authentification JWT et profil de l'utilisateur connecté.

import 'package:dio/dio.dart';
import '../api/api_client.dart';
import '../config.dart';
import '../../shared/models/models.dart';

class AuthService {
  Future<AuthUser> login(String username, String password) async {
    final tokenRes = await Dio(BaseOptions(
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 15),
    )).post(AppConfig.tokenUrl, data: {
      'username': username,
      'password': password,
    });
    await apiClient.saveTokens(
      tokenRes.data['access'],
      tokenRes.data['refresh'],
    );
    try {
      return await me();
    } catch (_) {
      // Profil illisible : pas de demi-connexion au prochain lancement
      await apiClient.clearTokens();
      rethrow;
    }
  }

  /// Profil de l'utilisateur connecté (sert aussi à restaurer la session).
  Future<AuthUser> me() async {
    final meRes = await apiClient.get('/users/me/');
    return AuthUser.fromJson(meRes.data);
  }

  /// Envoie la photo de profil (le serveur la vérifie et la réduit).
  Future<AuthUser> envoyerPhoto(List<int> octets, String nomFichier) async {
    final res = await apiClient.post('/users/me/photo/',
        data: FormData.fromMap({
          'photo': MultipartFile.fromBytes(octets, filename: nomFichier),
        }));
    return AuthUser.fromJson(res.data);
  }

  Future<AuthUser> retirerPhoto() async {
    final res = await apiClient.delete('/users/me/photo/');
    return AuthUser.fromJson(res.data);
  }

  /// Révoque le refresh token côté serveur puis efface les jetons locaux.
  Future<void> logout() async {
    try {
      final refresh = await apiClient.getRefreshToken();
      if (refresh != null) {
        // Hors ligne : on n'attend pas plus de 5 s pour déconnecter
        await apiClient.post('/users/logout/',
            data: {'refresh': refresh}).timeout(const Duration(seconds: 5));
      }
    } catch (_) {
      // Hors ligne ou session déjà expirée : la déconnexion locale suffit.
    }
    await apiClient.logout();
  }

  Future<bool> isLoggedIn() => apiClient.hasToken();
}

final authService = AuthService();
