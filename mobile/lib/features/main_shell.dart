// lib/features/main_shell.dart
//
// Coquille de l'application connectée : barre de navigation du bas.

import 'package:flutter/material.dart';
import 'accueil/accueil_screen.dart';
import 'demandes/a_valider_screen.dart';
import 'demandes/mes_demandes_screen.dart';
import 'profil/profil_screen.dart';

class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _index = 0;

  static const _ecrans = <Widget>[
    AccueilScreen(),
    MesDemandesScreen(),
    AValiderScreen(),
    ProfilScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      // Écran reconstruit à chaque changement d'onglet : listes à jour
      body: _ecrans[_index],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
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
