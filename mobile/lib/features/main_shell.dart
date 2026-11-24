// lib/features/main_shell.dart
//
// Coquille de l'application connectée : barre de navigation du bas,
// activation du push (ouverture directe de la demande notifiée).

import 'package:flutter/material.dart';
import '../core/services/push_service.dart';
import '../main.dart' show navigatorKey;
import 'accueil/accueil_screen.dart';
import 'demandes/a_valider_screen.dart';
import 'demandes/demande_detail_screen.dart';
import 'demandes/mes_demandes_screen.dart';
import 'profil/profil_screen.dart';

class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _index = 0;

  @override
  void initState() {
    super.initState();
    pushService.surOuverture = (id) => navigatorKey.currentState
        ?.push(MaterialPageRoute(builder: (_) => DemandeDetailScreen(id: id)));
    pushService.activer();
  }

  void _onglet(int i) => setState(() => _index = i);

  @override
  Widget build(BuildContext context) {
    // Écran reconstruit à chaque changement d'onglet : listes à jour
    final ecran = switch (_index) {
      0 => AccueilScreen(onOnglet: _onglet),
      1 => const MesDemandesScreen(),
      2 => const AValiderScreen(),
      _ => const ProfilScreen(),
    };
    return Scaffold(
      body: ecran,
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: _onglet,
        destinations: const [
          NavigationDestination(
              icon: Icon(Icons.home_outlined),
              selectedIcon: Icon(Icons.home_rounded),
              label: 'Accueil'),
          NavigationDestination(
              icon: Icon(Icons.description_outlined),
              selectedIcon: Icon(Icons.description_rounded),
              label: 'Demandes'),
          NavigationDestination(
              icon: Icon(Icons.task_alt_outlined),
              selectedIcon: Icon(Icons.task_alt_rounded),
              label: 'À valider'),
          NavigationDestination(
              icon: Icon(Icons.person_outline_rounded),
              selectedIcon: Icon(Icons.person_rounded),
              label: 'Profil'),
        ],
      ),
    );
  }
}
