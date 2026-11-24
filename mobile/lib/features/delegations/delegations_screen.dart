// lib/features/delegations/delegations_screen.dart
//
// Délégations de validation : celles que j'ai données et celles que j'ai
// reçues ; création (délégataire, période, motif) et révocation.

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../core/api/api_client.dart';
import '../../core/services/demandes_service.dart';
import '../../core/widgets/common_widgets.dart';
import '../../shared/theme/app_theme.dart';

const _etats = {
  'active': ('Active', TonPastille.vert),
  'planifiee': ('Planifiée', TonPastille.bleu),
  'terminee': ('Terminée', TonPastille.gris),
  'revoquee': ('Révoquée', TonPastille.rouge),
};

String _jour(dynamic iso) {
  final d = DateTime.tryParse('${iso ?? ''}');
  return d == null ? '—' : DateFormat('dd/MM/yyyy').format(d);
}

class DelegationsScreen extends StatefulWidget {
  const DelegationsScreen({super.key});
  @override
  State<DelegationsScreen> createState() => _DelegationsScreenState();
}

class _DelegationsScreenState extends State<DelegationsScreen> {
  String _sens = 'donnees';
  late Future<List<Map<String, dynamic>>> _liste = demandesService.delegations(sens: _sens);

  Future<void> _recharger() async {
    final f = demandesService.delegations(sens: _sens);
    setState(() => _liste = f);
    await f.catchError((_) => <Map<String, dynamic>>[]);
  }

  Future<void> _revoquer(Map d) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('Révoquer la délégation ?'),
        content: Text('${d['delegataire_nom']} ne pourra plus valider à votre place.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Annuler')),
          FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Révoquer')),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      await demandesService.revoquerDelegation(d['id'] as int);
      messenger.showSnackBar(const SnackBar(content: Text('Délégation révoquée.')));
      _recharger();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(messageErreurApi(e) ?? 'Révocation impossible.'), backgroundColor: AppColors.error));
    }
  }

  Future<void> _nouvelle() async {
    final cree = await Navigator.of(context).push<bool>(MaterialPageRoute(builder: (_) => const _NouvelleDelegation()));
    if (cree == true) {
      _sens = 'donnees';
      _recharger();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _nouvelle,
        icon: const Icon(Icons.add_rounded),
        label: const Text('Déléguer'),
      ),
      body: Column(children: [
        const EnTeteMarine(titre: 'Délégations', sousTitre: 'Validations confiées pendant une absence'),
        RangeeFiltres(filtres: [
          FiltrePastille(label: 'Données', actif: _sens == 'donnees', onTap: () { _sens = 'donnees'; _recharger(); }),
          FiltrePastille(label: 'Reçues', actif: _sens == 'recues', onTap: () { _sens = 'recues'; _recharger(); }),
        ]),
        Expanded(
          child: RefreshIndicator(
            onRefresh: _recharger,
            child: FutureBuilder<List<Map<String, dynamic>>>(
              future: _liste,
              builder: (context, snap) {
                if (snap.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
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
                    EmptyState(icon: Icons.person_add_alt_outlined, title: 'Aucune délégation'),
                  ]);
                }
                return ListView.separated(
                  padding: const EdgeInsets.fromLTRB(14, 12, 14, 90),
                  itemCount: liste.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 8),
                  itemBuilder: (_, i) {
                    final d = liste[i];
                    final etat = _etats[d['etat']] ?? ('${d['etat']}', TonPastille.gris);
                    final perimetre = [
                      ...List<String>.from(d['types_demande_libelles'] as List? ?? []),
                      ...List<String>.from(d['responsabilites_libelles'] as List? ?? []),
                    ];
                    return CarteListe(lignes: [
                      ListTile(
                        title: Text(_sens == 'donnees' ? 'À ${d['delegataire_nom']}' : 'De ${d['delegant_nom']}',
                            style: const TextStyle(fontWeight: FontWeight.w700)),
                        subtitle: Text([
                          'Du ${_jour(d['date_debut'])} au ${_jour(d['date_fin'])}',
                          perimetre.isEmpty ? 'Toutes mes validations' : perimetre.join(', '),
                          if ((d['motif'] as String? ?? '').isNotEmpty) d['motif'],
                        ].join('\n')),
                        isThreeLine: true,
                        trailing: PastilleStatut(label: etat.$1, ton: etat.$2),
                      ),
                      if (_sens == 'donnees' && (d['etat'] == 'active' || d['etat'] == 'planifiee'))
                        Align(
                          alignment: Alignment.centerRight,
                          child: TextButton.icon(
                            onPressed: () => _revoquer(d),
                            icon: const Icon(Icons.block_rounded, color: AppColors.error, size: 18),
                            label: const Text('Révoquer', style: TextStyle(color: AppColors.error)),
                          ),
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

class _NouvelleDelegation extends StatefulWidget {
  const _NouvelleDelegation();
  @override
  State<_NouvelleDelegation> createState() => _NouvelleDelegationState();
}

class _NouvelleDelegationState extends State<_NouvelleDelegation> {
  List<Map<String, dynamic>> _collaborateurs = [];
  Map<String, dynamic>? _delegataire;
  DateTimeRange? _periode;
  final _motif = TextEditingController();
  bool _enCours = false;

  @override
  void initState() {
    super.initState();
    demandesService.annuaire().then((c) {
      if (mounted) setState(() => _collaborateurs = c);
    }).catchError((_) {});
  }

  @override
  void dispose() {
    _motif.dispose();
    super.dispose();
  }

  Future<void> _choisirPeriode() async {
    final maintenant = DateTime.now();
    final p = await showDateRangePicker(
      context: context,
      firstDate: DateTime(maintenant.year, maintenant.month, maintenant.day),
      lastDate: maintenant.add(const Duration(days: 365)),
      initialDateRange: _periode,
      locale: const Locale('fr', 'FR'),
    );
    if (p != null) setState(() => _periode = p);
  }

  Future<void> _enregistrer() async {
    if (_delegataire == null || _periode == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Choisissez le délégataire et la période.')));
      return;
    }
    setState(() => _enCours = true);
    final f = DateFormat('yyyy-MM-dd');
    try {
      await demandesService.creerDelegation({
        'delegataire': _delegataire!['id'],
        'date_debut': f.format(_periode!.start),
        'date_fin': f.format(_periode!.end),
        'motif': _motif.text.trim(),
        'types_demande': <int>[],
        'responsabilites': <int>[],
      });
      if (mounted) Navigator.of(context).pop(true);
    } catch (e) {
      if (mounted) {
        setState(() => _enCours = false);
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(messageErreurApi(e) ?? 'Enregistrement impossible.'), backgroundColor: AppColors.error));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(children: [
        const EnTeteMarine(titre: 'Nouvelle délégation'),
        Expanded(
          child: ListView(padding: const EdgeInsets.all(16), children: [
            Autocomplete<Map<String, dynamic>>(
              displayStringForOption: (c) => '${c['libelle']}',
              optionsBuilder: (v) {
                final t = v.text.toLowerCase().trim();
                return t.isEmpty
                    ? const Iterable<Map<String, dynamic>>.empty()
                    : _collaborateurs.where((c) => '${c['libelle']}'.toLowerCase().contains(t)).take(20);
              },
              onSelected: (c) => setState(() => _delegataire = c),
              fieldViewBuilder: (context, controleur, focus, _) => TextField(
                controller: controleur,
                focusNode: focus,
                decoration: const InputDecoration(labelText: 'Délégataire', hintText: 'Nom ou matricule',
                    prefixIcon: Icon(Icons.search_rounded), border: OutlineInputBorder()),
              ),
            ),
            const SizedBox(height: 14),
            OutlinedButton.icon(
              onPressed: _choisirPeriode,
              icon: const Icon(Icons.date_range_rounded),
              label: Text(_periode == null
                  ? 'Choisir la période'
                  : 'Du ${_jour(_periode!.start.toIso8601String())} au ${_jour(_periode!.end.toIso8601String())}'),
            ),
            const SizedBox(height: 14),
            TextField(
              controller: _motif,
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(labelText: 'Motif (congés, mission…)', border: OutlineInputBorder()),
            ),
            const SizedBox(height: 8),
            Text('La délégation couvre toutes vos validations sur la période. Pour la limiter à certains types ou responsabilités, utilisez le web.',
                style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 20),
            BoutonVert(label: 'Enregistrer', icone: Icons.check_rounded, chargement: _enCours, onPressed: _enregistrer),
          ]),
        ),
      ]),
    );
  }
}
