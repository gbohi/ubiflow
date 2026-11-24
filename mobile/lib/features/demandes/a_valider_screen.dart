// lib/features/demandes/a_valider_screen.dart
//
// Validations en attente (les miennes et celles reçues par délégation).

import 'package:flutter/material.dart';
import '../../core/services/demandes_service.dart';
import '../../core/api/api_client.dart';
import '../../core/widgets/common_widgets.dart';
import 'commun.dart';
import 'demande_detail_screen.dart';

class AValiderScreen extends StatefulWidget {
  const AValiderScreen({super.key});
  @override
  State<AValiderScreen> createState() => _AValiderScreenState();
}

class _AValiderScreenState extends State<AValiderScreen> {
  late Future<List<Map<String, dynamic>>> _taches = demandesService.aValider();

  Future<void> _recharger() async {
    final f = demandesService.aValider();
    setState(() => _taches = f);
    await f.catchError((_) => <Map<String, dynamic>>[]);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(children: [
        const EnTeteMarine(titre: 'À valider', sousTitre: 'Demandes qui attendent votre décision'),
        Expanded(
          child: RefreshIndicator(
            onRefresh: _recharger,
            child: FutureBuilder<List<Map<String, dynamic>>>(
              future: _taches,
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
                final taches = snap.data ?? [];
                if (taches.isEmpty) {
                  return ListView(children: const [
                    SizedBox(height: 40),
                    EmptyState(icon: Icons.task_alt_rounded, title: 'Rien à valider',
                        subtitle: 'Vous êtes à jour.'),
                  ]);
                }
                return ListView.separated(
                  padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
                  itemCount: taches.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                  itemBuilder: (_, i) {
                    final t = taches[i];
                    final d = Map<String, dynamic>.from(t['demande'] as Map);
                    return Card(
                      margin: EdgeInsets.zero,
                      child: ListTile(
                        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                        leading: IconeTypeDemande(d['type_code'] as String?),
                        title: Text('${d['reference']} — ${d['demandeur']}',
                            style: const TextStyle(fontWeight: FontWeight.w700)),
                        subtitle: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text('${d['type_libelle']} — ${d['objet']}', maxLines: 2, overflow: TextOverflow.ellipsis),
                          Text('Étape : ${t['etape']}', style: const TextStyle(fontSize: 12)),
                          if (t['en_retard'] == true)
                            const Text('En retard', style: TextStyle(fontSize: 12, color: Colors.red, fontWeight: FontWeight.w600)),
                          if (t['pour_compte_de'] != null)
                            Text('Pour le compte de ${t['pour_compte_de']}',
                                style: const TextStyle(fontSize: 12, color: Colors.orange)),
                        ]),
                        trailing: Text(montant(d['montant_demande'], d['devise'] as String? ?? ''),
                            style: const TextStyle(fontWeight: FontWeight.w600)),
                        onTap: () async {
                          await Navigator.push(context, MaterialPageRoute(
                              builder: (_) => DemandeDetailScreen(id: d['id'] as int)));
                          _recharger();
                        },
                      ),
                    );
                  },
                );
              },
            ),
          ),
        ),
      ]),
    );
  }
}
