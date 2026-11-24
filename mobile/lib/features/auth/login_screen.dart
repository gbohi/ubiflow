// lib/features/auth/login_screen.dart

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../../shared/theme/app_theme.dart';
import '../../shared/providers/app_provider.dart';
import 'forgot_password_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen>
    with TickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _usernameCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  bool _obscure = true;
  late AnimationController _fadeCtrl;
  late AnimationController _slideCtrl;
  late Animation<double> _fadeAnim;
  late Animation<Offset> _slideAnim;

  @override
  void initState() {
    super.initState();
    _fadeCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 800));
    _slideCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 600));
    _fadeAnim = CurvedAnimation(parent: _fadeCtrl, curve: Curves.easeOut);
    _slideAnim = Tween<Offset>(begin: const Offset(0, 0.3), end: Offset.zero)
        .animate(
            CurvedAnimation(parent: _slideCtrl, curve: Curves.easeOutCubic));
    _fadeCtrl.forward();
    Future.delayed(const Duration(milliseconds: 200), () {
      if (mounted) _slideCtrl.forward();
    });
  }

  @override
  void dispose() {
    _fadeCtrl.dispose();
    _slideCtrl.dispose();
    _usernameCtrl.dispose();
    _passwordCtrl.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    final auth = context.read<AuthProvider>();
    // Connexion déjà en cours (touche « Entrée » pendant le chargement)
    if (auth.loading) return;
    if (!_formKey.currentState!.validate()) return;
    await auth.login(_usernameCtrl.text.trim(), _passwordCtrl.text);
    // Navigation gérée automatiquement par Consumer<AuthProvider> dans main.dart
  }

  // L'erreur du serveur est masquée dès que l'utilisateur corrige sa saisie
  bool _erreurMasquee = false;

  void _onSaisie(String _) {
    if (!_erreurMasquee) setState(() => _erreurMasquee = true);
  }

  Future<void> _soumettre() async {
    setState(() => _erreurMasquee = false);
    await _login();
  }

  // Champs translucides sur le marine (bordure verte au focus)
  InputDecoration _decoration(String indice, IconData icone, bool erreur, {Widget? suffixe}) {
    final rayon = BorderRadius.circular(14);
    OutlineInputBorder bord(Color c, [double l = 1]) =>
        OutlineInputBorder(borderRadius: rayon, borderSide: BorderSide(color: c, width: l));
    final normal = erreur ? const Color(0xFFFF8A80) : Colors.white.withOpacity(0.14);
    return InputDecoration(
      hintText: indice,
      hintStyle: TextStyle(color: Colors.white.withOpacity(0.45)),
      filled: true,
      fillColor: Colors.white.withOpacity(0.06),
      prefixIcon: Icon(icone, color: const Color(0xFF8EA3B8)),
      suffixIcon: suffixe,
      contentPadding: const EdgeInsets.symmetric(vertical: 17),
      enabledBorder: bord(normal),
      border: bord(normal),
      focusedBorder: bord(erreur ? const Color(0xFFFF8A80) : AppColors.accent, 1.5),
      errorBorder: bord(const Color(0xFFFF8A80)),
      focusedErrorBorder: bord(const Color(0xFFFF8A80), 1.5),
      errorStyle: const TextStyle(color: Color(0xFFFF8A80)),
    );
  }

  static const _etiquette = TextStyle(color: Color(0xFFA9BBCD), fontSize: 12.5, fontWeight: FontWeight.w500);

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final erreur = auth.error != null && !_erreurMasquee ? auth.error : null;

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Scaffold(
        backgroundColor: AppColors.primary,
        body: Stack(children: [
          // Pictogramme UbiPharm, très grand et presque invisible
          Positioned(
            right: -170,
            top: -60,
            child: ExcludeSemantics(
              child: Opacity(
                opacity: 0.06,
                child: Image.asset('assets/images/ubipharm-monogramme-vert.png', width: 470),
              ),
            ),
          ),
          SafeArea(
            child: FadeTransition(
              opacity: _fadeAnim,
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(24, 30, 24, 24),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Padding(
                    padding: const EdgeInsets.only(left: 4),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Image.asset('assets/images/ubipharm-logo-blanc.png', height: 40, semanticLabel: "UbiPharm Côte d'Ivoire"),
                      const SizedBox(height: 10),
                      Text('UBIFLOW · DEMANDES',
                          style: TextStyle(color: Colors.white.withOpacity(0.55), fontSize: 10.5, letterSpacing: 1.6,
                              fontWeight: FontWeight.w500)),
                      const SizedBox(height: 48),
                      Semantics(
                        header: true,
                        child: const Text('Connexion',
                            style: TextStyle(color: Colors.white, fontSize: 30, fontWeight: FontWeight.w600, letterSpacing: -0.6)),
                      ),
                    ]),
                  ),
                  const SizedBox(height: 28),

                  SlideTransition(
                    position: _slideAnim,
                    child: Form(
                      key: _formKey,
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        // Erreur du serveur (identifiants, réseau…)
                        if (erreur != null)
                          Container(
                            margin: const EdgeInsets.only(bottom: 16),
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: const Color(0xFFFF8A80).withOpacity(0.12),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: const Color(0xFFFF8A80).withOpacity(0.4)),
                            ),
                            child: Row(children: [
                              const Icon(Icons.error_outline_rounded, color: Color(0xFFFF8A80), size: 18),
                              const SizedBox(width: 10),
                              Expanded(child: Text(erreur, style: const TextStyle(color: Colors.white, fontSize: 13))),
                            ]),
                          ),

                        const Text('Matricule', style: _etiquette),
                        const SizedBox(height: 7),
                        TextFormField(
                          controller: _usernameCtrl,
                          keyboardType: TextInputType.text,
                          textInputAction: TextInputAction.next,
                          autocorrect: false,
                          onChanged: _onSaisie,
                          style: const TextStyle(color: Colors.white, fontSize: 15),
                          cursorColor: AppColors.accent,
                          decoration: _decoration('Votre matricule', Icons.person_outline_rounded, erreur != null),
                          validator: (v) => (v == null || v.trim().isEmpty) ? 'Le matricule est requis' : null,
                        ),
                        const SizedBox(height: 16),

                        const Text('Mot de passe', style: _etiquette),
                        const SizedBox(height: 7),
                        TextFormField(
                          controller: _passwordCtrl,
                          obscureText: _obscure,
                          textInputAction: TextInputAction.done,
                          onChanged: _onSaisie,
                          onFieldSubmitted: (_) => _soumettre(),
                          style: const TextStyle(color: Colors.white, fontSize: 15),
                          cursorColor: AppColors.accent,
                          decoration: _decoration(
                            'Votre mot de passe',
                            Icons.lock_outline_rounded,
                            erreur != null,
                            suffixe: IconButton(
                              tooltip: _obscure ? 'Afficher le mot de passe' : 'Masquer le mot de passe',
                              icon: Icon(_obscure ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                                  color: const Color(0xFF8EA3B8)),
                              onPressed: () => setState(() => _obscure = !_obscure),
                            ),
                          ),
                          validator: (v) => (v == null || v.isEmpty) ? 'Le mot de passe est requis' : null,
                        ),

                        Align(
                          alignment: Alignment.centerRight,
                          child: TextButton(
                            onPressed: () =>
                                Navigator.push(context, MaterialPageRoute(builder: (_) => const ForgotPasswordScreen())),
                            child: const Text('Mot de passe oublié ?',
                                style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: AppColors.accent)),
                          ),
                        ),
                        const SizedBox(height: 8),

                        SizedBox(
                          width: double.infinity,
                          height: 56,
                          child: FilledButton(
                            onPressed: auth.loading ? null : _soumettre,
                            style: FilledButton.styleFrom(
                              backgroundColor: AppColors.accent,
                              disabledBackgroundColor: AppColors.accent.withOpacity(0.7),
                              foregroundColor: AppColors.primary,
                              disabledForegroundColor: AppColors.primary,
                              elevation: 0,
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                            ),
                            child: auth.loading
                                ? const SizedBox(
                                    width: 22,
                                    height: 22,
                                    child: CircularProgressIndicator(
                                        strokeWidth: 2.4, color: AppColors.primary, semanticsLabel: 'Connexion en cours'))
                                : const Row(mainAxisSize: MainAxisSize.min, children: [
                                    Text('Se connecter', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                                    SizedBox(width: 8),
                                    Icon(Icons.arrow_forward_rounded, size: 20),
                                  ]),
                          ),
                        ),

                        const SizedBox(height: 24),
                        Center(
                          child: Row(mainAxisSize: MainAxisSize.min, children: [
                            const Icon(Icons.verified_user_outlined, size: 15, color: AppColors.accent),
                            const SizedBox(width: 6),
                            Text("Connexion sécurisée · UbiPharm Côte d'Ivoire",
                                style: TextStyle(color: Colors.white.withOpacity(0.45), fontSize: 12)),
                          ]),
                        ),
                        const SizedBox(height: 8),
                        Center(
                          child: Text('Un souci ? Contactez votre gestionnaire',
                              style: TextStyle(color: Colors.white.withOpacity(0.45), fontSize: 12)),
                        ),
                      ]),
                    ),
                  ),
                ]),
              ),
            ),
          ),
        ]),
      ),
    );
  }
}
