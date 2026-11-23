// lib/features/accueil/accueil_screen.dart
//
// Accueil de l'application : message de bienvenue et informations du compte.
// Les modules métier de la plateforme viendront s'y ajouter.

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../shared/providers/app_provider.dart';
import '../../core/widgets/common_widgets.dart';

class AccueilScreen extends StatelessWidget {
  const AccueilScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().user;
    final prenom = (user?.prenom.isNotEmpty ?? false)
        ? user!.prenom
        : (user?.username ?? '');
    final affectation = [
      if (user?.dernierPoste != null) user!.dernierPoste!,
      if (user?.dernierService != null) user!.dernierService!,
      if (user?.derniereAgence != null) user!.derniereAgence!,
    ].join(' · ');

    return Scaffold(
      body: ListView(
        padding: EdgeInsets.zero,
        children: [
          EnTeteMarine(
            titre: 'Bonjour $prenom',
            sousTitre: affectation.isNotEmpty ? affectation : null,
          ),
          const Padding(
            padding: EdgeInsets.fromLTRB(14, 40, 14, 40),
            child: EmptyState(
              icon: Icons.dashboard_customize_outlined,
              title: 'Bienvenue sur UbiFlow',
              subtitle: 'Les modules de la plateforme seront bientôt disponibles.',
            ),
          ),
        ],
      ),
    );
  }
}
