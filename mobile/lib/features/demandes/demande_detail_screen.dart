// lib/features/demandes/demande_detail_screen.dart
//
// Fiche d'une demande : contenu, circuit, historique ; panneau de décision
// (approuver, retourner, rejeter) si une validation m'attend.

import 'package:flutter/material.dart';
import '../../core/api/api_client.dart';
import '../../core/services/demandes_service.dart';
import '../../core/widgets/common_widgets.dart';
import '../../shared/theme/app_theme.dart';
import 'cloture_screen.dart';
import 'commun.dart';
import '../../core/widgets/remix.dart';
import 'demande_form_screen.dart';
import 'fichiers.dart';

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
  final _commentaire = TextEditingController();

  @override
  void initState() {
    super.initState();
    _charger();
  }

  @override
  void dispose() {
    _motif.dispose();
    _commentaire.dispose();
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
      if (ok != true || !mounted) return;
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
      bottomNavigationBar: _barreActions(d),
      body: Column(children: [
        EnTeteMarine(
          titre: d?['reference'] as String? ?? (d == null ? 'Demande' : '${d['type_libelle']}'),
          sousTitre: d == null
              ? null
              : d['reference'] == null
                  ? 'Brouillon créé le ${dateCourte(d['created_at']).replaceFirst(' ', ' à ')} · non soumis'
                  : '${d['type_libelle']} · ${d['demandeur_nom']}',
          actions: [if (d != null && d['reference'] != null) _menuDocuments(d)],
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
      if (d['cloture'] is Map) ...[
        const LibelleSection('Clôture de la mission'),
        CarteListe(lignes: [
          for (final (l, v) in resumeCloture(d['cloture'] as Map, d['devise'] as String? ?? '')) _ligne(l, v),
          if ((d['cloture'] as Map)['actions']?['modifier'] == true)
            Padding(
              padding: const EdgeInsets.all(12),
              child: BoutonVert(
                label: 'Déclarer mes dépenses réelles',
                icone: Icons.receipt_long_rounded,
                onPressed: () => _ouvrirEcran(ClotureScreen(demande: d)),
              ),
            ),
        ]),
        const SizedBox(height: 12),
      ],
      if (aDesPaiements(d)) ...[
        const LibelleSection('Paiements'),
        CarteListe(lignes: [for (final (l, v) in resumePaiements(d)) _ligne(l, v)]),
        const SizedBox(height: 12),
      ],
      if (d['demande_parent_reference'] != null) ...[
        CarteListe(lignes: [_ligne('Rattachée à', '${d['demande_parent_reference']} (${d['demande_parent_type']})')]),
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

      ..._sectionDocuments(d),
      ..._sectionCommentaires(d),

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
      const SizedBox(height: 8),
      _actionsDestructrices(d),
    ]);
  }

  // ── Actions du demandeur ──────────────────────────────────

  Future<void> _ouvrirEcran(Widget ecran) async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => ecran));
    _charger();
  }

  /// Type complet (champs, paramètres) pour le formulaire de modification
  Future<void> _modifier(Map<String, dynamic> d) async {
    Map<String, dynamic>? type;
    try {
      type = (await demandesService.types()).where((t) => t['id'] == d['type_demande']).firstOrNull;
    } catch (_) {}
    type ??= {
      'id': d['type_demande'], 'code': d['type_code'], 'libelle': d['type_libelle'], 'famille': d['type_famille'],
      'parametres': d['type_parametres'], 'champs': d['champs'], 'avec_montant': d['montant_demande'] != null,
    };
    if (mounted) _ouvrirEcran(DemandeFormScreen(type: type, demande: d));
  }

  Future<bool> _confirmer(String titre, String texte, String bouton) async =>
      await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: Text(titre),
          content: Text(texte),
          actions: [
            TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Retour')),
            FilledButton(onPressed: () => Navigator.pop(c, true), child: Text(bouton)),
          ],
        ),
      ) ==
      true;

  Future<String?> _demanderMotif(String titre) async {
    final ctrl = TextEditingController();
    final motif = await showDialog<String>(
      context: context,
      builder: (c) => AlertDialog(
        title: Text(titre),
        content: TextField(controller: ctrl, autofocus: true, minLines: 2, maxLines: 4,
            decoration: const InputDecoration(labelText: 'Motif *', border: OutlineInputBorder())),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c), child: const Text('Retour')),
          FilledButton(onPressed: () => Navigator.pop(c, ctrl.text.trim()), child: const Text('Valider')),
        ],
      ),
    );
    ctrl.dispose();
    return (motif ?? '').isEmpty ? null : motif;
  }

  Future<void> _executer(Future<void> Function() action, String succes, {bool fermer = false}) async {
    setState(() => _enCours = true);
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    try {
      await action();
      messenger.showSnackBar(SnackBar(content: Text(succes), backgroundColor: AppColors.success));
      if (fermer) {
        navigator.pop(true);
        return;
      }
      await _charger();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(messageErreurApi(e) ?? 'Action impossible.'), backgroundColor: AppColors.error));
    } finally {
      if (mounted) setState(() => _enCours = false);
    }
  }

  Future<void> _soumettre(Map<String, dynamic> d) async {
    if (!await _confirmer('Soumettre la demande ?',
        'Elle part en validation et ne sera plus modifiable, sauf retour pour correction.', 'Soumettre')) {
      return;
    }
    _executer(() => demandesService.soumettre(d['id'] as int), 'Demande soumise.');
  }

  /// Barre fixée en bas : « Modifier » (secondaire) et « Soumettre » (principal)
  Widget? _barreActions(Map<String, dynamic>? d) {
    if (d == null) return null;
    final a = Map<String, dynamic>.from(d['actions'] as Map? ?? {});
    if (a['soumettre'] != true && a['modifier'] != true) return null;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      decoration: BoxDecoration(
        color: isDark ? AppColors.darkSurface : Colors.white,
        border: Border(top: BorderSide(color: isDark ? AppColors.darkBorder : AppColors.lightBorder)),
      ),
      padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
      child: SafeArea(
        top: false,
        child: Row(children: [
          if (a['modifier'] == true)
            Expanded(
              flex: 2,
              child: SizedBox(
                height: 46,
                child: OutlinedButton.icon(
                  onPressed: _enCours ? null : () => _modifier(d),
                  icon: const Icon(Remix.edit, size: 18),
                  label: const Text('Modifier'),
                  style: OutlinedButton.styleFrom(
                      foregroundColor: AppColors.primary,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                ),
              ),
            ),
          if (a['modifier'] == true && a['soumettre'] == true) const SizedBox(width: 10),
          if (a['soumettre'] == true)
            Expanded(
              flex: 3,
              child: SizedBox(
                height: 46,
                child: FilledButton.icon(
                  onPressed: _enCours ? null : () => _soumettre(d),
                  icon: _enCours
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Remix.sendPlane, size: 18),
                  label: Text(d['statut'] == 'a_corriger' ? 'Soumettre à nouveau' : 'Soumettre'),
                  style: FilledButton.styleFrom(
                      backgroundColor: AppColors.accent, foregroundColor: AppColors.primary, elevation: 0,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                ),
              ),
            ),
        ]),
      ),
    );
  }

  /// Actions destructrices, en rouge, à l'écart en bas de la fiche
  Widget _actionsDestructrices(Map<String, dynamic> d) {
    final a = Map<String, dynamic>.from(d['actions'] as Map? ?? {});
    final id = d['id'] as int;
    return Column(children: [
      if (a['supprimer'] == true)
        TextButton.icon(
          onPressed: _enCours
              ? null
              : () async {
                  if (!await _confirmer('Supprimer le brouillon ?', 'Le brouillon et ses pièces seront supprimés.', 'Supprimer')) return;
                  _executer(() => demandesService.supprimer(id), 'Brouillon supprimé.', fermer: true);
                },
          icon: const Icon(Remix.deleteBin, color: AppColors.error, size: 18),
          label: const Text('Supprimer le brouillon', style: TextStyle(color: AppColors.error)),
        ),
      if (a['annuler'] == true)
        TextButton.icon(
          onPressed: _enCours
              ? null
              : () async {
                  final motif = await _demanderMotif('Annuler la demande');
                  if (motif != null) _executer(() => demandesService.annuler(id, motif), 'Demande annulée.');
                },
          icon: const Icon(Remix.closeCircle, color: AppColors.error, size: 18),
          label: const Text('Annuler la demande', style: TextStyle(color: AppColors.error)),
        ),
    ]);
  }

  // ── Documents PDF ─────────────────────────────────────────

  Widget _menuDocuments(Map<String, dynamic> d) {
    final mission = d['type_famille'] == 'mission';
    final paiement = d['type_famille'] == 'simple' && d['montant_demande'] != null;
    return PopupMenuButton<String>(
      tooltip: 'Documents',
      icon: const Icon(Icons.picture_as_pdf_outlined, color: Colors.white),
      onSelected: (doc) => _telechargerPdf(d, doc),
      itemBuilder: (_) => [
        const PopupMenuItem(value: 'pdf', child: Text('Fiche de la demande')),
        if (mission) const PopupMenuItem(value: 'ordre-mission', child: Text('Ordre de mission')),
        if (mission) const PopupMenuItem(value: 'note-frais', child: Text('Note de frais')),
        if (paiement)
          PopupMenuItem(
              value: 'demande-paiement',
              child: Text(d['type_code'] == 'RMB' ? 'Demande de remboursement' : 'Demande de paiement')),
      ],
    );
  }

  Future<void> _telechargerPdf(Map<String, dynamic> d, String doc) async {
    final messenger = ScaffoldMessenger.of(context);
    messenger.showSnackBar(const SnackBar(content: Text('Préparation du document…'), duration: Duration(seconds: 1)));
    try {
      final octets = await demandesService.pdf(d['id'] as int, doc);
      final erreur = await ouvrirOctets(octets, '$doc-${d['reference']}.pdf');
      if (erreur != null) messenger.showSnackBar(SnackBar(content: Text(erreur)));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(messageErreurApi(e) ?? 'Document indisponible.'), backgroundColor: AppColors.error));
    }
  }

  // ── Pièces jointes ────────────────────────────────────────

  List<Widget> _sectionDocuments(Map<String, dynamic> d) {
    final docs = List<Map>.from(d['documents'] as List? ?? []).where((x) => x['retire'] != true).toList();
    final exigees = List<Map>.from(d['pieces_exigees'] as List? ?? []);
    final peutAjouter = (d['actions'] as Map?)?['ajouter_document'] == true;
    if (docs.isEmpty && !peutAjouter) return [];
    final fournies = docs.map((x) => x['type_piece']).toSet();
    return [
      const LibelleSection('Pièces jointes'),
      CarteListe(lignes: [
        for (final e in exigees.where((e) => e['moment'] != 'cloture' || d['cloture'] != null))
          ListTile(
            dense: true,
            leading: Icon(fournies.contains(e['type_piece']) ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded,
                color: fournies.contains(e['type_piece']) ? AppColors.success : Colors.grey),
            title: Text('${e['type_piece_libelle']}${e['obligatoire'] == true ? '' : ' (facultative)'}',
                style: const TextStyle(fontSize: 13)),
            subtitle: Text('${e['moment_libelle']}', style: const TextStyle(fontSize: 11)),
          ),
        for (final doc in docs)
          ListTile(
            leading: Icon(
                '${doc['nom_origine']}'.toLowerCase().endsWith('.pdf') ? Icons.picture_as_pdf_outlined : Icons.insert_drive_file_outlined),
            title: Text('${doc['nom_origine']}', maxLines: 1, overflow: TextOverflow.ellipsis),
            subtitle: Text([
              if (doc['type_piece_libelle'] != null) doc['type_piece_libelle'],
              tailleLisible(doc['taille']),
              '${doc['ajoute_par_nom']}',
            ].join(' · '), style: const TextStyle(fontSize: 12)),
            onTap: () => _ouvrirDocument(d, doc),
            trailing: peutAjouter
                ? IconButton(
                    tooltip: 'Retirer',
                    icon: const Icon(Icons.close_rounded),
                    onPressed: () async {
                      final motif = await _demanderMotif('Retirer la pièce');
                      if (motif != null) {
                        _executer(() => demandesService.retirerDocument(d['id'] as int, doc['id'] as int, motif), 'Pièce retirée.');
                      }
                    },
                  )
                : null,
          ),
        if (docs.isEmpty) const ListTile(dense: true, title: Text('Aucune pièce jointe.', style: TextStyle(fontSize: 13))),
        if (peutAjouter)
          ListTile(
            leading: const Icon(Icons.add_a_photo_outlined),
            title: const Text('Ajouter une pièce (photo ou fichier)', style: TextStyle(fontWeight: FontWeight.w600)),
            onTap: _enCours ? null : () => _ajouterPiece(d),
          ),
      ]),
      const SizedBox(height: 12),
    ];
  }

  Future<void> _ouvrirDocument(Map d, Map doc) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      final octets = await demandesService.fichierDocument(d['id'] as int, doc['id'] as int);
      final erreur = await ouvrirOctets(octets, '${doc['nom_origine']}');
      if (erreur != null) messenger.showSnackBar(SnackBar(content: Text(erreur)));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(messageErreurApi(e) ?? 'Ouverture impossible.'), backgroundColor: AppColors.error));
    }
  }

  Future<void> _ajouterPiece(Map<String, dynamic> d) async {
    final fichier = await choisirPiece(context);
    if (fichier == null || !mounted) return;
    // Type de pièce : les pièces exigées d'abord, puis les autres
    List<Map<String, dynamic>> types = [];
    try {
      types = await demandesService.typesPieces();
    } catch (_) {}
    if (!mounted) return;
    final exigees = List<Map>.from(d['pieces_exigees'] as List? ?? []).map((e) => e['type_piece']).toSet();
    types.sort((a, b) => (exigees.contains(b['id']) ? 1 : 0) - (exigees.contains(a['id']) ? 1 : 0));
    final type = await showModalBottomSheet<int>(
      context: context,
      isScrollControlled: true,
      builder: (c) => SafeArea(
        child: ConstrainedBox(
          constraints: BoxConstraints(maxHeight: MediaQuery.of(c).size.height * 0.7),
          child: ListView(shrinkWrap: true, children: [
            const ListTile(title: Text('Type de pièce', style: TextStyle(fontWeight: FontWeight.w700))),
            for (final t in types.where((t) => t['actif'] != false))
              ListTile(
                leading: Icon(exigees.contains(t['id']) ? Icons.star_rounded : Icons.description_outlined,
                    color: exigees.contains(t['id']) ? AppColors.warning : null),
                title: Text('${t['libelle']}'),
                onTap: () => Navigator.pop(c, t['id'] as int),
              ),
          ]),
        ),
      ),
    );
    if (type == null) return;
    _executer(() => demandesService.ajouterDocument(d['id'] as int, fichier.chemin, fichier.nom, typePiece: type), 'Pièce ajoutée.');
  }

  // ── Commentaires ──────────────────────────────────────────

  List<Widget> _sectionCommentaires(Map<String, dynamic> d) {
    final commentaires = List<Map>.from(d['commentaires'] as List? ?? []);
    final peutCommenter = (d['actions'] as Map?)?['commenter'] == true;
    if (commentaires.isEmpty && !peutCommenter) return [];
    return [
      const LibelleSection('Commentaires'),
      CarteListe(lignes: [
        for (final c in commentaires)
          ListTile(
            dense: true,
            title: Text('${c['texte']}', style: const TextStyle(fontSize: 13)),
            subtitle: Text('${c['auteur_nom']} · ${dateCourte(c['creee_le'])}', style: const TextStyle(fontSize: 11.5)),
          ),
        if (peutCommenter)
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 4, 8),
            child: Row(children: [
              Expanded(
                child: TextField(
                  controller: _commentaire,
                  minLines: 1,
                  maxLines: 3,
                  decoration: const InputDecoration(hintText: 'Ajouter un commentaire', border: InputBorder.none),
                ),
              ),
              IconButton(
                tooltip: 'Envoyer',
                icon: const Icon(Icons.send_rounded),
                onPressed: () {
                  final texte = _commentaire.text.trim();
                  if (texte.isEmpty) return;
                  _executer(() async {
                    await demandesService.commenter(d['id'] as int, texte);
                    _commentaire.clear();
                  }, 'Commentaire ajouté.');
                },
              ),
            ]),
          ),
      ]),
      const SizedBox(height: 12),
    ];
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
