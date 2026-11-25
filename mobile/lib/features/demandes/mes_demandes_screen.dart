// lib/features/demandes/mes_demandes_screen.dart
//
// Mes demandes : liste par statut, ouverture de la fiche, nouvelle demande.

import 'package:flutter/material.dart';
import '../../core/services/demandes_service.dart';
import '../../core/api/api_client.dart';
import '../../core/widgets/common_widgets.dart';
import 'commun.dart';
import 'demande_detail_screen.dart';
import 'nouvelle_demande_screen.dart';

class MesDemandesScreen extends StatefulWidget {
  /// Filtre de statut à l'ouverture (« Tout voir » de l'accueil)
  final String statutInitial;
  /// Missions seulement (« Tout voir » des prochaines missions)
  final bool missionsSeulement;
  const MesDemandesScreen({super.key, this.statutInitial = '', this.missionsSeulement = false});
  @override
  State<MesDemandesScreen> createState() => _MesDemandesScreenState();
}

class _MesDemandesScreenState extends State<MesDemandesScreen> {
  static const _filtres = [
    ('', 'Toutes'), ('en_validation', 'En validation'), ('a_corriger', 'À corriger'),
    ('en_attente_cloture', 'À clôturer'), ('approuvee', 'Approuvées'), ('rejetee', 'Rejetées'),
    ('annulee', 'Annulées'), ('brouillon', 'Brouillons'),
  ];
  late String _statut = widget.statutInitial;
  late Future<List<Map<String, dynamic>>> _demandes = _liste();

  Future<List<Map<String, dynamic>>> _liste() {
    return demandesService.mesDemandes(statut: _statut, famille: widget.missionsSeulement ? 'mission' : '');
  }

  Future<void> _recharger() async {
    final f = _liste();
    setState(() => _demandes = f);
    await f.catchError((_) => <Map<String, dynamic>>[]);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          await Navigator.push(context, MaterialPageRoute(builder: (_) => const NouvelleDemandeScreen()));
          _recharger();
        },
        icon: const Icon(Icons.add_rounded),
        label: const Text('Nouvelle demande'),
      ),
      body: Column(children: [
        EnTeteMarine(
            titre: widget.missionsSeulement ? 'Mes missions' : 'Mes demandes',
            sousTitre: widget.missionsSeulement ? 'Missions locales et hors pays' : 'Création, suivi, pièces jointes et clôture'),
        SizedBox(
          height: 52,
          child: ListView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            children: [
              for (final (cle, libelle) in _filtres)
                Padding(
                  padding: const EdgeInsets.only(right: 6),
                  child: ChoiceChip(
                    label: Text(libelle),
                    selected: _statut == cle,
                    onSelected: (_) {
                      _statut = cle;
                      _recharger();
                    },
                  ),
                ),
            ],
          ),
        ),
        Expanded(
          child: RefreshIndicator(
            onRefresh: _recharger,
            child: FutureBuilder<List<Map<String, dynamic>>>(
              future: _demandes,
              builder: (context, snap) {
                if (snap.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snap.hasError) {
                  return ListView(children: [
                    EmptyState(icon: Icons.wifi_off_rounded, title: 'Chargement impossible',
                        subtitle: messageErreurApi(snap.error!) ?? 'Tirez pour réessayer.'),
                  ]);
                }
                final demandes = snap.data ?? [];
                if (demandes.isEmpty) {
                  return ListView(children: [
                    const SizedBox(height: 40),
                    EmptyState(icon: Icons.description_outlined, title: widget.missionsSeulement ? 'Aucune mission' : 'Aucune demande'),
                  ]);
                }
                return ListView.separated(
                  padding: const EdgeInsets.fromLTRB(12, 4, 12, 90),
                  itemCount: demandes.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                  itemBuilder: (_, i) => _CarteDemande(
                    demande: demandes[i],
                    onTap: () async {
                      await Navigator.push(context, MaterialPageRoute(
                          builder: (_) => DemandeDetailScreen(id: demandes[i]['id'] as int)));
                      _recharger();
                    },
                  ),
                );
              },
            ),
          ),
        ),
      ]),
    );
  }
}

class _CarteDemande extends StatelessWidget {
  final Map<String, dynamic> demande;
  final VoidCallback onTap;
  const _CarteDemande({required this.demande, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final etape = demande['etape_en_cours'] as Map?;
    final m = demande['montant_demande'];
    return CarteListeDemande(
      typeCode: demande['type_code'] as String?,
      reference: demande['reference'] as String? ?? 'Brouillon',
      montant: m == null ? '' : montant(m, demande['devise'] as String? ?? ''),
      objet: demande['objet'] as String? ?? '',
      details: [demande['type_libelle'] ?? '', if (etape != null) 'Étape : ${etape['libelle']}'].join(' · '),
      statut: PastilleDemande(demande['statut'] as String),
      onTap: onTap,
    );
  }
}
