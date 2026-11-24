// lib/core/services/souvenir_service.dart
//
// « Se souvenir de moi » : mémorise sur le téléphone le matricule (et le nom de
// la carte « Bon retour ») du dernier utilisateur qui l'a demandé. Le mot de
// passe n'est jamais enregistré. La déconnexion n'efface pas ce souvenir ;
// « Changer » ou la case décochée, si.

import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

class Souvenir {
  final String matricule;
  final String nom;
  const Souvenir(this.matricule, this.nom);

  /// « Fatou » pour « Bon retour, Fatou » (le nom affiché est « NOM Prénom »)
  String get prenom {
    final mots = nom.trim().split(RegExp(r'\s+')).where((m) => m.isNotEmpty).toList();
    return mots.length >= 2 ? mots.last : (mots.isEmpty ? '' : mots.first);
  }

  /// Initiales, prénom d'abord : « KONE Fatou » → « FK »
  String get initiales {
    final mots = nom.trim().split(RegExp(r'\s+')).where((m) => m.isNotEmpty).toList();
    if (mots.length >= 2) return (mots.last[0] + mots.first[0]).toUpperCase();
    return (mots.isNotEmpty ? mots.first[0] : (matricule.isNotEmpty ? matricule[0] : '?')).toUpperCase();
  }
}

class SouvenirService {
  static const _cle = 'ubiflow.souvenir';

  Future<Souvenir?> lire() async {
    try {
      final brut = (await SharedPreferences.getInstance()).getString(_cle);
      if (brut == null) return null;
      final m = jsonDecode(brut) as Map;
      final matricule = '${m['matricule'] ?? ''}';
      return matricule.isEmpty ? null : Souvenir(matricule, '${m['nom'] ?? ''}');
    } catch (_) {
      return null;
    }
  }

  Future<void> enregistrer(String matricule, String nom) async =>
      (await SharedPreferences.getInstance()).setString(_cle, jsonEncode({'matricule': matricule, 'nom': nom}));

  Future<void> oublier() async => (await SharedPreferences.getInstance()).remove(_cle);
}

final souvenirService = SouvenirService();
