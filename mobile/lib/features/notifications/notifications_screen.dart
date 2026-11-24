// lib/features/notifications/notifications_screen.dart
//
// Notifications in-app : non lues en tête, ouverture directe de la demande,
// « Tout marquer comme lu ».

import 'package:flutter/material.dart';
import '../../core/api/api_client.dart';
import '../../core/services/accueil_service.dart';
import '../../core/widgets/common_widgets.dart';
import '../../shared/theme/app_theme.dart';
import '../demandes/commun.dart';
import '../demandes/demande_detail_screen.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});
  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  bool _nonLues = false;
  late Future<List<Map<String, dynamic>>> _liste = accueilService.notifications();

  Future<void> _recharger() async {
    final f = accueilService.notifications(nonLues: _nonLues);
    setState(() => _liste = f);
    await f.catchError((_) => <Map<String, dynamic>>[]);
  }

  Future<void> _ouvrir(Map n) async {
    if (n['lue'] != true) await accueilService.lire(n['id'] as int).catchError((_) {});
    final id = (n['demande'] as int?) ?? demandeDuLien(n['lien'] as String?);
    if (id != null && mounted) {
      await Navigator.of(context).push(MaterialPageRoute(builder: (_) => DemandeDetailScreen(id: id)));
    }
    _recharger();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(children: [
        EnTeteMarine(
          titre: 'Notifications',
          actions: [
            EnTeteBouton(
              icone: Icons.done_all_rounded,
              tooltip: 'Tout marquer comme lu',
              onPressed: () async {
                await accueilService.toutLire().catchError((_) {});
                _recharger();
              },
            ),
          ],
        ),
        RangeeFiltres(filtres: [
          FiltrePastille(label: 'Toutes', actif: !_nonLues, onTap: () { _nonLues = false; _recharger(); }),
          FiltrePastille(label: 'Non lues', actif: _nonLues, onTap: () { _nonLues = true; _recharger(); }),
        ]),
        Expanded(
          child: RefreshIndicator(
            onRefresh: _recharger,
            child: FutureBuilder<List<Map<String, dynamic>>>(
              future: _liste,
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
                final liste = snap.data ?? [];
                if (liste.isEmpty) {
                  return ListView(children: const [
                    SizedBox(height: 40),
                    EmptyState(icon: Icons.notifications_none_rounded, title: 'Aucune notification'),
                  ]);
                }
                return ListView.separated(
                  padding: const EdgeInsets.fromLTRB(14, 12, 14, 24),
                  itemCount: liste.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                  itemBuilder: (_, i) {
                    final n = liste[i];
                    final lue = n['lue'] == true;
                    return CarteListe(lignes: [
                      ListTile(
                        onTap: () => _ouvrir(n),
                        leading: Icon(lue ? Icons.notifications_none_rounded : Icons.notifications_active_rounded,
                            color: lue ? Colors.grey : AppColors.accentDark),
                        title: Text('${n['titre']}',
                            style: TextStyle(fontWeight: lue ? FontWeight.w500 : FontWeight.w700)),
                        subtitle: Text([
                          if ((n['message'] as String? ?? '').isNotEmpty) n['message'],
                          dateCourte(n['creee_le']),
                        ].join('\n')),
                        isThreeLine: (n['message'] as String? ?? '').isNotEmpty,
                      ),
                    ]);
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
