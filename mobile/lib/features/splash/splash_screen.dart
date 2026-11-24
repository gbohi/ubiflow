// lib/features/splash/splash_screen.dart
//
// Écran de démarrage (pendant la restauration de la session) : logo UbiPharm
// sur le marine de la marque, nom du produit, indicateur de chargement discret.

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../../shared/theme/app_theme.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});
  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 600))..forward();

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Scaffold(
        backgroundColor: AppColors.primary,
        body: SafeArea(
          child: FadeTransition(
            opacity: CurvedAnimation(parent: _ctrl, curve: Curves.easeOut),
            child: Column(children: [
              const Spacer(flex: 5),
              Image.asset('assets/images/ubipharm-logo-blanc.png', height: 64, semanticLabel: "UbiPharm Côte d'Ivoire"),
              const SizedBox(height: 18),
              Text('UBIFLOW · DEMANDES',
                  style: TextStyle(color: Colors.white.withOpacity(0.6), fontSize: 12, letterSpacing: 2, fontWeight: FontWeight.w500)),
              const Spacer(flex: 4),
              const SizedBox(
                width: 22,
                height: 22,
                child: CircularProgressIndicator(strokeWidth: 2.2, color: AppColors.accent, semanticsLabel: 'Chargement'),
              ),
              const SizedBox(height: 40),
            ]),
          ),
        ),
      ),
    );
  }
}
