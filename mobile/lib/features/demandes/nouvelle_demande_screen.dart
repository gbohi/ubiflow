// lib/features/demandes/nouvelle_demande_screen.dart
//
// Nouvelle demande : choix du type (missions en tête), puis formulaire.
// Avec `codeType` (action rapide de l'accueil), le formulaire s'ouvre aussitôt.

import 'package:flutter/material.dart';
import '../../core/api/api_client.dart';
import '../../core/services/demandes_service.dart';
import '../../core/widgets/common_widgets.dart';
import 'commun.dart';
import 'demande_form_screen.dart';

class NouvelleDemandeScreen extends StatefulWidget {
  final String? codeType;
  const NouvelleDemandeScreen({super.key, this.codeType});

  @override
  State<NouvelleDemandeScreen> createState() => _NouvelleDemandeScreenState();
}

class _NouvelleDemandeScreenState extends State<NouvelleDemandeScreen> {
  List<Map<String, dynamic>>? _types;
  String? _erreur;

  @override
  void initState() {
    super.initState();
    _charger();
  }

  Future<void> _charger() async {
    try {
      final t = await demandesService.types();
      t.sort((a, b) => ((a['ordre'] as int?) ?? 0).compareTo((b['ordre'] as int?) ?? 0));
      if (!mounted) return;
      final choisi = t.where((x) => x['code'] == widget.codeType).firstOrNull;
      if (choisi != null) {
        Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => DemandeFormScreen(type: choisi)));
        return;
      }
      setState(() {
        _types = t;
        _erreur = null;
      });
    } catch (e) {
      if (mounted) setState(() => _erreur = messageErreurApi(e) ?? 'Chargement impossible.');
    }
  }

  @override
  Widget build(BuildContext context) {
    final types = _types;
    return Scaffold(
      body: Column(children: [
        const EnTeteMarine(titre: 'Nouvelle demande', sousTitre: 'Choisissez le type de demande'),
        Expanded(
          child: _erreur != null
              ? ListView(children: [
                  EmptyState(icon: Icons.wifi_off_rounded, title: 'Chargement impossible', subtitle: _erreur),
                  Center(child: TextButton(onPressed: _charger, child: const Text('Réessayer'))),
                ])
              : types == null
                  ? const Center(child: CircularProgressIndicator())
                  : types.isEmpty
                      ? const EmptyState(icon: Icons.description_outlined, title: 'Aucun type de demande disponible')
                      : ListView.separated(
                          padding: const EdgeInsets.fromLTRB(14, 14, 14, 24),
                          itemCount: types.length,
                          separatorBuilder: (_, __) => const SizedBox(height: 8),
                          itemBuilder: (_, i) {
                            final t = types[i];
                            return CarteListe(lignes: [
                              ListTile(
                                leading: IconeTypeDemande(t['code'] as String?),
                                title: Text('${t['libelle']}', style: const TextStyle(fontWeight: FontWeight.w700)),
                                subtitle: (t['description'] as String? ?? '').isEmpty
                                    ? null
                                    : Text('${t['description']}', maxLines: 2, overflow: TextOverflow.ellipsis),
                                trailing: const Icon(Icons.chevron_right_rounded),
                                onTap: () => Navigator.of(context)
                                    .pushReplacement(MaterialPageRoute(builder: (_) => DemandeFormScreen(type: t))),
                              ),
                            ]);
                          },
                        ),
        ),
      ]),
    );
  }
}
