// lib/core/services/push_service.dart
//
// Notifications push (Firebase Cloud Messaging).
//
// La configuration Firebase est passée à la compilation, sans fichier
// google-services.json ni GoogleService-Info.plist :
//
//   flutter run --dart-define=FIREBASE_API_KEY=... \
//               --dart-define=FIREBASE_APP_ID=... \
//               --dart-define=FIREBASE_SENDER_ID=... \
//               --dart-define=FIREBASE_PROJECT_ID=...
//
// Sans ces valeurs, le push est simplement désactivé (les notifications
// restent visibles dans l'application). Un appui sur une notification ouvre
// la demande concernée.

import 'dart:io' show Platform;
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import '../api/api_client.dart';

class PushService {
  static const _apiKey = String.fromEnvironment('FIREBASE_API_KEY');
  static const _appId = String.fromEnvironment('FIREBASE_APP_ID');
  static const _senderId = String.fromEnvironment('FIREBASE_SENDER_ID');
  static const _projectId = String.fromEnvironment('FIREBASE_PROJECT_ID');

  bool _pret = false;
  String? _jeton;

  /// Appelé à l'ouverture d'une notification avec l'identifiant de la demande.
  void Function(int demande)? surOuverture;

  bool get configure => _apiKey.isNotEmpty && _appId.isNotEmpty && _senderId.isNotEmpty && _projectId.isNotEmpty;

  Future<void> _initialiser() async {
    if (_pret || !configure || kIsWeb) return;
    await Firebase.initializeApp(
      options: const FirebaseOptions(apiKey: _apiKey, appId: _appId, messagingSenderId: _senderId, projectId: _projectId),
    );
    FirebaseMessaging.onMessageOpenedApp.listen(_ouvrir);
    final initial = await FirebaseMessaging.instance.getInitialMessage();
    if (initial != null) _ouvrir(initial);
    FirebaseMessaging.instance.onTokenRefresh.listen(_enregistrer);
    _pret = true;
  }

  void _ouvrir(RemoteMessage m) {
    final id = int.tryParse('${m.data['demande'] ?? ''}');
    if (id != null) surOuverture?.call(id);
  }

  Future<void> _enregistrer(String jeton) async {
    _jeton = jeton;
    await apiClient.post('/notifications/appareils/',
        data: {'jeton': jeton, 'plateforme': Platform.isIOS ? 'ios' : 'android'});
  }

  /// Après la connexion : autorisation, jeton, enregistrement de l'appareil.
  Future<void> activer() async {
    try {
      await _initialiser();
      if (!_pret) return;
      final reglages = await FirebaseMessaging.instance.requestPermission();
      if (reglages.authorizationStatus == AuthorizationStatus.denied) return;
      final jeton = await FirebaseMessaging.instance.getToken();
      if (jeton != null) await _enregistrer(jeton);
    } catch (e) {
      debugPrint('Push indisponible : $e');
    }
  }

  /// À la déconnexion : l'appareil ne reçoit plus les notifications du compte.
  Future<void> desactiver() async {
    final jeton = _jeton;
    if (jeton == null) return;
    try {
      await apiClient.delete('/notifications/appareils/', params: {'jeton': jeton});
    } catch (_) {}
    _jeton = null;
  }
}

final pushService = PushService();
