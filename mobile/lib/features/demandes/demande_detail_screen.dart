// lib/features/demandes/demande_detail_screen.dart
//
// Fiche d'une demande : contenu, circuit, historique ; panneau de décision
// (approuver, retourner, rejeter) si une validation m'attend.

import 'package:flutter/material.dart';
import '../../core/api/api_client.dart';
import '../../core/services/demandes_service.dart';
import '../../core/widgets/common_widgets.dart';
import '../../shared/theme/app_theme.dart';
import 'commun.dart';

class DemandeDetailScreen extends StatefulWidget {
  final int id;
  const DemandeDetailScreen({super.key, required this.id});
  @override
  State<DemandeDetailScreen> createState() => _DemandeDetailScreenState();
}

class _DemandeDetailScreenState extends State<DemandeDetailScreen> {
  Map<String, dynamic>? _demande;
  List<Map<String, dynamic>> _historique = [];
  String? _erreur;
  bool _enCours = false;
  final _motif = TextEditingController();

  @override
  void initState() {
    super.initState();
    _charger();
  }

  @override
  void dispose() {
    _motif.dispose();
    super.dispose();
  }

  Future<void> _charger() async {
    try {
      final d = await demandesService.demande(widget.id);
      final h = await demandesService.historique(widget.id);
      if (!mounted) return;
      setState(() {
        _demande = d;
        _historique = h.reversed.toList();
        _erreur = null;
      });
    } catch (e) {
      if (mounted) setState(() => _erreur = messageErreurApi(e) ?? 'Chargement impossible.');
    }
  }

  Future<void> _agir(Map tache, String action) async {
    final motif = _motif.text.trim();
    if (action != 'approuver' && motif.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Le motif est obligatoire pour un retour ou un rejet.')));
      return;
    }
    if (action == 'rejeter') {
      final ok = await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: const Text('Rejeter la demande ?'),
          content: const Text('Le rejet est définitif.'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Annuler')),
            FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Rejeter')),
          ],
        ),
      );
      if (ok != true) return;
    }
    setState(() => _enCours = true);
    final messenger = ScaffoldMessenger.of(context);
    try {
      final statut = await demandesService.agir(tache['id'] as int, action, motif);
      _motif.clear();
      messenger.showSnackBar(SnackBar(content: Text('Décision enregistrée. Statut : $statut.'),
          backgroundColor: AppColors.success));
      await _charger();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(messageErreurApi(e) ?? 'Action impossible.'),
          backgroundColor: AppColors.error));
    } finally {
      if (mounted) setState(() => _enCours = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final d = _demande;
    return Scaffold(
      body: Column(children: [
        EnTeteMarine(
          titre: d?['reference'] as String? ?? (d == null ? 'Demande' : 'Brouillon'),
          sousTitre: d == null ? null : '${d['type_libelle']} — ${d['demandeur_nom']}',
        ),
        Expanded(
          child: _erreur != null
              ? EmptyState(icon: Icons.error_outline_rounded, title: _erreur!)
              : d == null
                  ? const Center(child: CircularProgressIndicator())
                  : RefreshIndicator(onRefresh: _charger, child: _contenu(d)),
        ),
      ]),
    );
  }

  Widget _contenu(Map<String, dynamic> d) {
    final champs = List<Map>.from(d['champs'] as List? ?? []);
    final donnees = Map<String, dynamic>.from(d['donnees'] as Map? ?? {});
    final taches = List<Map>.from(d['mes_taches'] as List? ?? []);
    final circuit = List<Map>.from(d['circuit'] as List? ?? []);
    final devise = d['devise'] as String? ?? '';
    return ListView(padding: const EdgeInsets.fromLTRB(14, 12, 14, 32), children: [
      Row(children: [PastilleDemande(d['statut'] as String), const Spacer(),
        Text(montant(d['montant_demande'], devise), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16))]),
      const SizedBox(height: 12),

      if (taches.isNotEmpty) _panneauDecision(taches.first),

      const LibelleSection('Contenu'),
      CarteListe(lignes: [
        _ligne('Objet', d['objet']),
        if (d['montant_approuve'] != null && d['montant_approuve'] != d['montant_demande'])
          _ligne('Montant approuvé', montant(d['montant_approuve'], devise)),
        for (final c in champs) _ligne(c['libelle'] as String, _valeur(c, donnees[c['code']])),
      ]),
      const SizedBox(height: 12),

      if (d['mission'] is Map) ...[
        const LibelleSection('Mission'),
        CarteListe(lignes: [for (final (l, v) in resumeMission(d['mission'] as Map)) _ligne(l, v)]),
        const SizedBox(height: 12),
      ],
      if (d['calcul'] is Map) ...[
        const LibelleSection('Récapitulatif des frais'),
        CarteListe(lignes: [
          for (final (rubrique, detail, valeur) in lignesRecap(d['calcul'] as Map))
            ListTile(
              dense: true,
              title: Text(rubrique, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
              subtitle: Text(detail, style: const TextStyle(fontSize: 12)),
              trailing: Text(valeur, style: const TextStyle(fontWeight: FontWeight.w600)),
            ),
          ListTile(
            dense: true,
            title: const Text('Total prévisionnel', style: TextStyle(fontWeight: FontWeight.w700)),
            trailing: Text(montant((d['calcul'] as Map)['total_ref'], (d['calcul'] as Map)['devise_reference'] as String? ?? ''),
                style: const TextStyle(fontWeight: FontWeight.w700)),
          ),
          for (final s in List.from((d['calcul'] as Map)['signalements'] as List? ?? []))
            ListTile(dense: true, leading: const Icon(Icons.warning_amber_rounded, color: Colors.orange),
                title: Text('$s', style: const TextStyle(fontSize: 12))),
        ]),
        const SizedBox(height: 12),
      ],

      if (circuit.isNotEmpty) ...[
        const LibelleSection('Circuit de validation'),
        CarteListe(lignes: [
          for (final e in List<Map>.from(circuit.last['etapes'] as List)) _etape(e),
        ]),
        const SizedBox(height: 12),
      ],

      const LibelleSection('Historique'),
      CarteListe(lignes: [
        for (final a in _historique)
          ListTile(
            dense: true,
            title: Text('${a['type_libelle']}${a['etape_libelle'] != null ? ' — ${a['etape_libelle']}' : ''}',
                style: const TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Text([
              '${a['auteur_nom']}${a['pour_compte_de_nom'] != null ? ' pour ${a['pour_compte_de_nom']}' : ''} · ${dateCourte(a['horodatage'])}',
              if ((a['motif'] as String? ?? '').isNotEmpty) a['motif'],
            ].join('\n')),
          ),
      ]),
    ]);
  }

  Widget _panneauDecision(Map tache) {
    final actions = List<String>.from(tache['actions_autorisees'] as List? ?? []);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: CarteListe(bordure: AppColors.accent, epaisseurBordure: 1.5, lignes: [
        Padding(
          padding: const EdgeInsets.all(14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Text('Votre validation — ${tache['etape']}', style: const TextStyle(fontWeight: FontWeight.w700)),
            if (tache['pour_compte_de'] != null)
              Text('Pour le compte de ${tache['pour_compte_de']} (délégation)', style: const TextStyle(fontSize: 12)),
            if ((tache['champs_modifiables'] as List? ?? []).isNotEmpty)
              const Text('Pour corriger un montant ou un champ, utilisez le web.', style: TextStyle(fontSize: 12)),
            const SizedBox(height: 10),
            TextField(
              controller: _motif,
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(
                  hintText: 'Commentaire (obligatoire pour un retour ou un rejet)', border: OutlineInputBorder()),
            ),
            const SizedBox(height: 10),
            FilledButton.icon(
              onPressed: _enCours ? null : () => _agir(tache, 'approuver'),
              icon: const Icon(Icons.check_rounded),
              label: const Text('Approuver'),
              style: FilledButton.styleFrom(backgroundColor: AppColors.success),
            ),
            if (actions.contains('retourner'))
              OutlinedButton.icon(
                onPressed: _enCours ? null : () => _agir(tache, 'retourner'),
                icon: const Icon(Icons.undo_rounded),
                label: const Text('Retourner pour correction'),
              ),
            if (actions.contains('rejeter'))
              TextButton.icon(
                onPressed: _enCours ? null : () => _agir(tache, 'rejeter'),
                icon: const Icon(Icons.close_rounded, color: AppColors.error),
                label: const Text('Rejeter', style: TextStyle(color: AppColors.error)),
              ),
          ]),
        ),
      ]),
    );
  }

  Widget _etape(Map e) {
    final etat = e['etat'] as String;
    final (icone, couleur) = switch (etat) {
      'approuvee' => (Icons.check_circle_rounded, AppColors.success),
      'en_cours' => (Icons.radio_button_checked_rounded, AppColors.primary),
      'rejetee' => (Icons.cancel_rounded, AppColors.error),
      'retournee' => (Icons.undo_rounded, Colors.orange),
      _ => (Icons.radio_button_unchecked_rounded, Colors.grey),
    };
    final taches = List<Map>.from(e['taches'] as List? ?? [])
        .where((t) => t['etat'] != 'annulee' || (t['decision'] as String? ?? '').isNotEmpty);
    return ListTile(
      dense: true,
      leading: Icon(icone, color: couleur),
      title: Text('${e['libelle']} — ${e['etat_libelle']}', style: const TextStyle(fontWeight: FontWeight.w600)),
      subtitle: Text(etat == 'sautee'
          ? (e['motif_saut'] as String? ?? '')
          : taches.isNotEmpty
              ? taches.map((t) => '${t['valideur']}${t['traitee_le'] != null ? ' · ${dateCourte(t['traitee_le'])}' : ''}').join('\n')
              : List<String>.from(e['valideurs_prevus'] as List? ?? []).join(', ')),
    );
  }

  Widget _ligne(String libelle, dynamic valeur) => ListTile(
        dense: true,
        title: Text(libelle, style: const TextStyle(fontSize: 12)),
        subtitle: Text('${valeur ?? '—'}', style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
      );

  String _valeur(Map champ, dynamic v) {
    if (v == null || v == '') return '—';
    switch (champ['nature']) {
      case 'booleen':
        return v == true ? 'Oui' : 'Non';
      case 'montant':
        return montant(v);
      case 'date':
        final d = DateTime.tryParse(v.toString());
        return d == null ? '$v' : '${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}/${d.year}';
      default:
        return '$v';
    }
  }
}
