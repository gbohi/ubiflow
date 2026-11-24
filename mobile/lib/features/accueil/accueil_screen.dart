// lib/features/accueil/accueil_screen.dart
//
// Accueil de synthèse, comme sur le web : vue selon le profil (collaborateur,
// valideur, direction générale, DAF / chef comptable), 4 indicateurs, alertes,
// actions rapides, listes prioritaires, graphiques légers, notifications
// récentes, dernières activités et raccourcis.

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../core/api/api_client.dart';
import '../../core/services/accueil_service.dart';
import '../../core/widgets/common_widgets.dart';
import '../../shared/theme/app_theme.dart';
import '../demandes/commun.dart';
import '../demandes/demande_detail_screen.dart';
import '../demandes/nouvelle_demande_screen.dart';
import '../delegations/delegations_screen.dart';
import '../notifications/notifications_screen.dart';

/// Icônes Remix (renvoyées par l'API, comme pour le web) → icônes Material.
const Map<String, IconData> iconesRemix = {
  'ri-file-list-3-line': Icons.description_outlined,
  'ri-loader-2-line': Icons.hourglass_top_rounded,
  'ri-checkbox-circle-line': Icons.check_circle_outline_rounded,
  'ri-error-warning-line': Icons.error_outline_rounded,
  'ri-checkbox-multiple-line': Icons.task_alt_rounded,
  'ri-alarm-warning-line': Icons.alarm_rounded,
  'ri-check-double-line': Icons.done_all_rounded,
  'ri-arrow-go-back-line': Icons.undo_rounded,
  'ri-stack-line': Icons.layers_outlined,
  'ri-time-line': Icons.schedule_rounded,
  'ri-road-map-line': Icons.alt_route_rounded,
  'ri-money-dollar-circle-line': Icons.monetization_on_outlined,
  'ri-hand-coin-line': Icons.payments_outlined,
  'ri-task-line': Icons.fact_check_outlined,
  'ri-wallet-3-line': Icons.account_balance_wallet_outlined,
  'ri-flight-takeoff-line': Icons.flight_takeoff_rounded,
  'ri-refund-2-line': Icons.currency_exchange_rounded,
  'ri-add-circle-line': Icons.add_circle_outline_rounded,
};

class AccueilScreen extends StatefulWidget {
  /// Change d'onglet (1 : Mes demandes, 2 : À valider)
  final void Function(int onglet)? onOnglet;
  const AccueilScreen({super.key, this.onOnglet});

  @override
  State<AccueilScreen> createState() => _AccueilScreenState();
}

class _AccueilScreenState extends State<AccueilScreen> {
  Map<String, dynamic>? _donnees;
  String? _erreur;
  String? _profil;
  int _nonLues = 0;

  @override
  void initState() {
    super.initState();
    _charger();
  }

  Future<void> _charger() async {
    try {
      final d = await accueilService.accueil(profil: _profil);
      final n = await accueilService.nonLues().catchError((_) => 0);
      if (!mounted) return;
      setState(() {
        _donnees = d;
        _profil = d['profil'] as String?;
        _nonLues = n;
        _erreur = null;
      });
    } catch (e) {
      if (mounted) setState(() => _erreur = messageErreurApi(e) ?? 'Chargement impossible.');
    }
  }

  Future<void> _ouvrir(Widget ecran) async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => ecran));
    _charger();
  }

  void _ouvrirLien(String? lien) {
    final id = demandeDuLien(lien);
    if (id != null) {
      _ouvrir(DemandeDetailScreen(id: id));
    } else if ((lien ?? '').startsWith('/validations')) {
      widget.onOnglet?.call(2);
    } else if ((lien ?? '').startsWith('/demandes')) {
      widget.onOnglet?.call(1);
    } else if ((lien ?? '').startsWith('/delegations')) {
      _ouvrir(const DelegationsScreen());
    }
  }

  @override
  Widget build(BuildContext context) {
    final d = _donnees;
    final profils = List<Map>.from(d?['profils'] as List? ?? []);
    final date = DateTime.tryParse('${d?['aujourdhui'] ?? ''}');
    return Scaffold(
      body: Column(children: [
        EnTeteMarine(
          titre: d == null ? 'Accueil' : 'Bonjour, ${d['prenom']}',
          sousTitre: date == null ? null : 'Résumé de votre activité · ${DateFormat('EEEE d MMMM y', 'fr_FR').format(date)}',
          actions: [
            EnTeteBouton(
                icone: Icons.notifications_none_rounded,
                tooltip: 'Notifications',
                badge: _nonLues,
                onPressed: () => _ouvrir(const NotificationsScreen())),
          ],
          bas: profils.length > 1
              ? SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(children: [
                    for (final p in profils)
                      Padding(
                        padding: const EdgeInsets.only(right: 6),
                        child: _PastilleProfil(
                          label: '${p['libelle']}',
                          actif: _profil == p['code'],
                          onTap: () {
                            setState(() => _profil = p['code'] as String);
                            _charger();
                          },
                        ),
                      ),
                  ]),
                )
              : null,
        ),
        Expanded(
          child: _erreur != null && d == null
              ? ListView(children: [
                  EmptyState(icon: Icons.wifi_off_rounded, title: 'Chargement impossible', subtitle: _erreur),
                  Center(child: TextButton(onPressed: _charger, child: const Text('Réessayer'))),
                ])
              : d == null
                  ? const Center(child: CircularProgressIndicator())
                  : RefreshIndicator(onRefresh: _charger, child: _contenu(d)),
        ),
      ]),
    );
  }

  Widget _contenu(Map<String, dynamic> d) {
    final devise = d['devise'] as String? ?? '';
    final kpis = List<Map>.from(d['kpis'] as List? ?? []);
    final alertes = List<Map>.from(d['alertes'] as List? ?? []);
    final actions = List<Map>.from(d['actions_rapides'] as List? ?? []);
    final listes = List<Map>.from(d['listes'] as List? ?? []);
    final graphes = List<Map>.from(d['graphes'] as List? ?? []);
    final notifications = List<Map>.from(d['notifications'] as List? ?? []);
    final activites = List<Map>.from(d['activites'] as List? ?? []);
    return ListView(padding: const EdgeInsets.fromLTRB(14, 14, 14, 32), children: [
      // Indicateurs : grille de 2 colonnes
      LayoutBuilder(builder: (context, c) {
        final largeur = (c.maxWidth - 10) / 2;
        return Wrap(spacing: 10, runSpacing: 10, children: [
          for (final k in kpis) SizedBox(width: largeur, child: _Kpi(k, devise, onTap: () => _ouvrirLien(k['lien'] as String?))),
        ]);
      }),
      const SizedBox(height: 12),

      for (final a in alertes) ...[
        InkWell(
          onTap: () => _ouvrirLien(a['lien'] as String?),
          child: BandeauInfo(
            icone: a['ton'] == 'alerte' ? Icons.report_rounded : Icons.info_outline_rounded,
            texte: '${a['texte']}',
            ton: a['ton'] == 'alerte' ? TonPastille.rouge : TonPastille.or,
          ),
        ),
        const SizedBox(height: 8),
      ],

      const LibelleSection('Actions rapides'),
      SizedBox(
        height: 86,
        child: ListView(scrollDirection: Axis.horizontal, children: [
          for (final a in actions)
            _ActionRapide(
              libelle: '${a['libelle']}',
              icone: iconesRemix[a['icone']] ?? Icons.add_circle_outline_rounded,
              onTap: () => _ouvrir(NouvelleDemandeScreen(codeType: a['code'] as String?)),
            ),
          if (widget.onOnglet != null && kpis.any((k) => k['cle'] == 'a_valider'))
            _ActionRapide(libelle: 'Valider', icone: Icons.task_alt_rounded, onTap: () => widget.onOnglet!(2)),
        ]),
      ),
      const SizedBox(height: 12),

      for (final g in graphes)
        if ((g['donnees'] as List? ?? []).isNotEmpty) ...[
          LibelleSection('${g['titre']}'),
          CarteListe(lignes: [
            Padding(padding: const EdgeInsets.all(14), child: _Graphe(g, devise)),
          ]),
          const SizedBox(height: 12),
        ],

      for (final l in listes) ...[
        Row(children: [
          Expanded(child: LibelleSection('${l['titre']} (${(l['lignes'] as List? ?? []).length})')),
          if (l['lien_tout'] != null)
            TextButton(onPressed: () => _ouvrirLien(l['lien_tout'] as String?), child: const Text('Voir tout')),
        ]),
        CarteListe(lignes: [
          if ((l['lignes'] as List? ?? []).isEmpty)
            ListTile(dense: true, title: Text('${l['vide'] ?? 'Rien à signaler.'}', style: const TextStyle(fontSize: 13))),
          for (final ligne in List<Map>.from(l['lignes'] as List? ?? []))
            _LigneDemande(ligne, devise, onTap: () => _ouvrir(DemandeDetailScreen(id: ligne['id'] as int))),
        ]),
        const SizedBox(height: 12),
      ],

      Row(children: [
        const Expanded(child: LibelleSection('Notifications récentes')),
        TextButton(onPressed: () => _ouvrir(const NotificationsScreen()), child: const Text('Tout voir')),
      ]),
      CarteListe(lignes: [
        if (notifications.isEmpty) const ListTile(dense: true, title: Text('Aucune notification.')),
        for (final n in notifications.take(5))
          ListTile(
            dense: true,
            leading: Icon(n['lue'] == true ? Icons.notifications_none_rounded : Icons.notifications_active_rounded,
                color: n['lue'] == true ? Colors.grey : AppColors.accentDark),
            title: Text('${n['titre']}', style: const TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Text(dateCourte(n['creee_le'])),
            onTap: () {
              accueilService.lire(n['id'] as int).catchError((_) {});
              _ouvrirLien(n['lien'] as String?);
            },
          ),
      ]),
      const SizedBox(height: 12),

      if (activites.isNotEmpty) ...[
        const LibelleSection('Dernières activités'),
        CarteListe(lignes: [
          for (final a in activites.take(6))
            ListTile(
              dense: true,
              title: Text('${a['type']} · ${a['reference'] ?? ''}', style: const TextStyle(fontWeight: FontWeight.w600)),
              subtitle: Text('${a['auteur']} · ${dateCourte(a['le'])}'),
              onTap: a['demande'] == null ? null : () => _ouvrir(DemandeDetailScreen(id: a['demande'] as int)),
            ),
        ]),
        const SizedBox(height: 12),
      ],

      const LibelleSection('Raccourcis'),
      Wrap(spacing: 8, runSpacing: 8, children: [
        ActionChip(avatar: const Icon(Icons.description_outlined, size: 18), label: const Text('Mes demandes'),
            onPressed: () => widget.onOnglet?.call(1)),
        ActionChip(avatar: const Icon(Icons.task_alt_rounded, size: 18), label: const Text('À valider'),
            onPressed: () => widget.onOnglet?.call(2)),
        ActionChip(avatar: const Icon(Icons.add_circle_outline_rounded, size: 18), label: const Text('Nouvelle demande'),
            onPressed: () => _ouvrir(const NouvelleDemandeScreen())),
        ActionChip(avatar: const Icon(Icons.person_add_alt_outlined, size: 18), label: const Text('Délégations'),
            onPressed: () => _ouvrir(const DelegationsScreen())),
      ]),
    ]);
  }
}

/// Choix de la vue dans l'en-tête marine : active en vert, les autres translucides.
class _PastilleProfil extends StatelessWidget {
  final String label;
  final bool actif;
  final VoidCallback onTap;
  const _PastilleProfil({required this.label, required this.actif, required this.onTap});

  @override
  Widget build(BuildContext context) => Semantics(
        selected: actif,
        button: true,
        child: Material(
          color: actif ? AppColors.accent : Colors.white.withOpacity(0.1),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          child: InkWell(
            borderRadius: BorderRadius.circular(20),
            onTap: onTap,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
              child: Text(label,
                  style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600,
                      color: actif ? AppColors.primary : Colors.white)),
            ),
          ),
        ),
      );
}

String _valeurKpi(Map k, String devise) =>
    k['format'] == 'montant' ? montant(k['valeur'], devise) : montant(k['valeur']);

class _Kpi extends StatelessWidget {
  final Map k;
  final String devise;
  final VoidCallback? onTap;
  const _Kpi(this.k, this.devise, {this.onTap});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final couleur = switch (k['ton']) {
      'alerte' => AppColors.error,
      'attention' => AppColors.warning,
      _ => isDark ? AppColors.accent : AppColors.primary,
    };
    return InkWell(
      onTap: k['lien'] == null ? null : onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: isDark ? AppColors.darkCard : AppColors.lightCard,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: isDark ? AppColors.darkBorder : AppColors.lightBorder),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Container(
              width: 32, height: 32,
              decoration: BoxDecoration(color: couleur.withAlpha(30), borderRadius: BorderRadius.circular(9)),
              child: Icon(iconesRemix[k['icone']] ?? Icons.insights_rounded, size: 18, color: couleur),
            ),
            const SizedBox(width: 8),
            Expanded(child: Text('${k['libelle']}', maxLines: 2, style: const TextStyle(fontSize: 12, height: 1.2))),
          ]),
          const SizedBox(height: 8),
          FittedBox(
            fit: BoxFit.scaleDown,
            alignment: Alignment.centerLeft,
            child: Text(_valeurKpi(k, devise),
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800, color: k['ton'] == '' ? null : couleur)),
          ),
          if ((k['sous_titre'] as String? ?? '').isNotEmpty)
            Text('${k['sous_titre']}', maxLines: 2, style: Theme.of(context).textTheme.bodySmall),
        ]),
      ),
    );
  }
}

class _ActionRapide extends StatelessWidget {
  final String libelle;
  final IconData icone;
  final VoidCallback onTap;
  const _ActionRapide({required this.libelle, required this.icone, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(14),
        child: Container(
          width: 118,
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 10),
          decoration: BoxDecoration(
            color: isDark ? AppColors.darkCard : AppColors.lightCard,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: isDark ? AppColors.darkBorder : AppColors.lightBorder),
          ),
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            Icon(icone, color: isDark ? AppColors.accent : AppColors.primary),
            const SizedBox(height: 6),
            FittedBox(
              fit: BoxFit.scaleDown,
              child: Text(libelle, textAlign: TextAlign.center, maxLines: 2,
                  style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
            ),
          ]),
        ),
      ),
    );
  }
}

class _LigneDemande extends StatelessWidget {
  final Map l;
  final String devise;
  final VoidCallback onTap;
  const _LigneDemande(this.l, this.devise, {required this.onTap});

  @override
  Widget build(BuildContext context) {
    final details = [
      l['reference'] ?? 'Brouillon',
      l['type'],
      if (l['demandeur'] != null) l['demandeur'],
      if ((l['info'] as String? ?? '').isNotEmpty) l['info'],
    ].join(' · ');
    return ListTile(
      onTap: onTap,
      leading: IconeTypeDemande(l['type_code'] as String?),
      title: Text('${l['objet']}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
      subtitle: Text(details, maxLines: 2, style: const TextStyle(fontSize: 12)),
      trailing: l['montant'] != null
          ? Text(montant(l['montant'], devise), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12.5))
          : (l['statut'] != null ? PastilleDemande(l['statut'] as String) : null),
    );
  }
}

/// Graphique léger : barres horizontales classées (une seule teinte) ou
/// colonnes mensuelles (première série).
class _Graphe extends StatelessWidget {
  final Map g;
  final String devise;
  const _Graphe(this.g, this.devise);

  static const _teinte = Color(0xFF2A78D6);

  String _etiquette(num v) {
    if (g['unite'] != 'montant') return montant(v);
    if (v >= 1e6) return '${(v / 1e6).toStringAsFixed(v >= 1e7 ? 0 : 1).replaceAll('.', ',')} M';
    if (v >= 1e3) return '${(v / 1e3).round()} k';
    return montant(v);
  }

  @override
  Widget build(BuildContext context) {
    final donnees = List<Map>.from(g['donnees'] as List? ?? []);
    if (g['type'] == 'colonnes') {
      final serie = (List<Map>.from(g['series'] as List? ?? []).firstOrNull?['cle'] ?? '') as String;
      final valeurs = [for (final d in donnees) num.tryParse('${(d['valeurs'] as Map?)?[serie] ?? 0}') ?? 0];
      final max = valeurs.fold<num>(0, (a, b) => b > a ? b : a);
      return SizedBox(
        height: 150,
        child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
          for (var i = 0; i < donnees.length; i++)
            Expanded(
              child: Semantics(
                label: '${donnees[i]['libelle']} : ${montant(valeurs[i], devise)}',
                child: Column(mainAxisAlignment: MainAxisAlignment.end, children: [
                  if (valeurs[i] > 0) Text(_etiquette(valeurs[i]), style: const TextStyle(fontSize: 10)),
                  const SizedBox(height: 2),
                  Container(
                    height: max == 0 ? 1 : 1 + 100 * valeurs[i] / max,
                    margin: const EdgeInsets.symmetric(horizontal: 6),
                    decoration: const BoxDecoration(color: _teinte, borderRadius: BorderRadius.vertical(top: Radius.circular(4))),
                  ),
                  const SizedBox(height: 4),
                  Text('${donnees[i]['libelle']}', style: const TextStyle(fontSize: 10)),
                ]),
              ),
            ),
        ]),
      );
    }
    final valeurs = [for (final d in donnees) num.tryParse('${d['valeur']}') ?? 0];
    final max = valeurs.fold<num>(0, (a, b) => b > a ? b : a);
    return Column(children: [
      for (var i = 0; i < donnees.length; i++)
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 4),
          child: Row(children: [
            SizedBox(width: 110, child: Text('${donnees[i]['libelle']}', maxLines: 1, overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 12))),
            Expanded(
              child: LayoutBuilder(builder: (context, c) => Row(children: [
                    Container(
                      width: max == 0 ? 2 : 2 + (c.maxWidth - 60) * valeurs[i] / max,
                      height: 14,
                      decoration: BoxDecoration(color: _teinte, borderRadius: BorderRadius.circular(3)),
                    ),
                    const SizedBox(width: 6),
                    Text(_etiquette(valeurs[i]), style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600)),
                  ])),
            ),
          ]),
        ),
    ]);
  }
}
