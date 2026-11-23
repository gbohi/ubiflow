// lib/features/demandes/mes_demandes_screen.dart
//
// Mes demandes : liste par statut, ouverture de la fiche.

import 'package:flutter/material.dart';
import '../../core/services/demandes_service.dart';
import '../../core/api/api_client.dart';
import '../../core/widgets/common_widgets.dart';
import 'commun.dart';
import 'demande_detail_screen.dart';

class MesDemandesScreen extends StatefulWidget {
  const MesDemandesScreen({super.key});
  @override
  State<MesDemandesScreen> createState() => _MesDemandesScreenState();
}

class _MesDemandesScreenState extends State<MesDemandesScreen> {
  static const _filtres = [
    ('', 'Toutes'), ('en_validation', 'En validation'), ('a_corriger', 'À corriger'),
    ('approuvee', 'Approuvées'), ('rejetee', 'Rejetées'), ('brouillon', 'Brouillons'),
  ];
  String _statut = '';
  late Future<List<Map<String, dynamic>>> _demandes = demandesService.mesDemandes();

  Future<void> _recharger() async {
    final f = demandesService.mesDemandes(statut: _statut);
    setState(() => _demandes = f);
    await f.catchError((_) => <Map<String, dynamic>>[]);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(children: [
        const EnTeteMarine(titre: 'Mes demandes', sousTitre: 'Création et modification sur le web'),
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
                  return ListView(children: const [
                    SizedBox(height: 40),
                    EmptyState(icon: Icons.description_outlined, title: 'Aucune demande'),
                  ]);
                }
                return ListView.separated(
                  padding: const EdgeInsets.fromLTRB(12, 4, 12, 24),
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
    return Card(
      margin: EdgeInsets.zero,
      child: ListTile(
        onTap: onTap,
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        title: Text(demande['reference'] as String? ?? 'Brouillon',
            style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('${demande['type_libelle']} — ${demande['objet']}', maxLines: 2, overflow: TextOverflow.ellipsis),
          if (etape != null)
            Text('Étape : ${etape['libelle']}', style: const TextStyle(fontSize: 12)),
          const SizedBox(height: 4),
          PastilleDemande(demande['statut'] as String),
        ]),
        trailing: Text(montant(demande['montant_demande'], demande['devise'] as String? ?? ''),
            style: const TextStyle(fontWeight: FontWeight.w600)),
      ),
    );
  }
}
