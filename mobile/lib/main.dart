// lib/main.dart

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:intl/date_symbol_data_local.dart';
import 'shared/theme/app_theme.dart';
import 'shared/providers/app_provider.dart';
import 'features/auth/login_screen.dart';
import 'features/main_shell.dart';
import 'features/splash/splash_screen.dart';

final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await initializeDateFormatting('fr_FR', null);

  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.light,
  ));

  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  runApp(const UbiFlowApp());
}

class UbiFlowApp extends StatelessWidget {
  const UbiFlowApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => ThemeProvider()),
        ChangeNotifierProvider(create: (_) => AuthProvider()),
      ],
      child: Consumer<ThemeProvider>(
        builder: (_, theme, __) => MaterialApp(
          navigatorKey: navigatorKey,
          title: 'UbiFlow',
          debugShowCheckedModeBanner: false,
          theme: AppTheme.light(),
          darkTheme: AppTheme.dark(),
          themeMode: theme.mode,
          home: const _AuthGate(),
        ),
      ),
    );
  }
}

// ── Auth gate ──────────────────────────────────────────────────
class _AuthGate extends StatefulWidget {
  const _AuthGate();
  @override
  State<_AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<_AuthGate> {
  bool _checking = true;
  bool _horsLigne = false;
  bool _etaitConnecte = false;

  @override
  void initState() {
    super.initState();
    _checkAuth();
  }

  Future<void> _checkAuth() async {
    // restoreSession() recharge le profil si un jeton est stocké :
    // l'utilisateur reste connecté entre deux lancements de l'app.
    // Quoi qu'il arrive, l'écran de démarrage laisse la place à la connexion.
    EtatSession etat = EtatSession.deconnecte;
    try {
      final results = await Future.wait([
        context.read<AuthProvider>().restoreSession(),
        Future.delayed(const Duration(milliseconds: 1500)),
      ]).timeout(const Duration(seconds: 60));
      etat = results[0] as EtatSession;
    } catch (e) {
      debugPrint('⚠️ Restauration de session impossible : $e');
    }

    if (!mounted) return;
    setState(() {
      _checking = false;
      _horsLigne = etat == EtatSession.horsLigne;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_checking) return const SplashScreen();

    if (_horsLigne) {
      return _HorsLigneScreen(onReessayer: () {
        setState(() {
          _checking = true;
          _horsLigne = false;
        });
        _checkAuth();
      });
    }

    return Consumer<AuthProvider>(
      builder: (_, auth, __) {
        // Déconnexion ou session expirée : fermer les écrans ouverts par-dessus
        if (_etaitConnecte && !auth.isLoggedIn) {
          WidgetsBinding.instance.addPostFrameCallback(
              (_) => navigatorKey.currentState?.popUntil((r) => r.isFirst));
        }
        _etaitConnecte = auth.isLoggedIn;
        return auth.isLoggedIn ? const MainShell() : const LoginScreen();
      },
    );
  }
}

/// Serveur injoignable au démarrage alors qu'une session existe :
/// on propose de réessayer au lieu de déconnecter l'utilisateur.
class _HorsLigneScreen extends StatelessWidget {
  final VoidCallback onReessayer;
  const _HorsLigneScreen({required this.onReessayer});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              const Icon(Icons.wifi_off_rounded, size: 56, color: Colors.grey),
              const SizedBox(height: 16),
              Text('Serveur injoignable',
                  style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 8),
              Text(
                  'Vérifiez votre connexion internet puis réessayez. '
                  'Vous restez connecté.',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyMedium),
              const SizedBox(height: 24),
              FilledButton.icon(
                onPressed: onReessayer,
                icon: const Icon(Icons.refresh_rounded),
                label: const Text('Réessayer'),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}
