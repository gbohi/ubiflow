// lib/features/demandes/cloture_screen.dart
//
// Clôture d'une mission par le demandeur : dates réelles, dépenses réelles par
// rubrique de la note de frais, observations ; solde recalculé par le serveur
// (à rembourser ou reste dû) ; pièces de clôture (rapport…) jointes ici ;
// soumission au contrôle.

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import '../../core/api/api_client.dart';
import '../../core/services/demandes_service.dart';
import '../../core/widgets/common_widgets.dart';
import '../../shared/theme/app_theme.dart';
import 'commun.dart';
import 'fichiers.dart';
import 'mission_saisie.dart' show versIsoLocal;

/// Rubriques de la note de frais (mêmes clés que le web et l'API)
const rubriquesCloture = [
  (cle: 'hotel', libelle: "Frais d'hôtel", aide: 'Petit déjeuner compris', detail: null),
  (cle: 'transport', libelle: 'Transport', aide: 'Location de véhicule, taxis', detail: null),
  (cle: 'telephone', libelle: 'Frais de téléphone', aide: '', detail: null),
  (cle: 'divers', libelle: 'Divers', aide: 'Précisez ci-dessous', detail: 'divers_detail'),
  (cle: 'reception', libelle: 'Réception', aide: '', detail: null),
  (cle: 'detaxe', libelle: 'Détaxe (à reverser)', aide: 'Taxes remboursées à l’étranger : déduites', detail: null),
  (cle: 'a_refacturer', libelle: 'Autres frais à refacturer', aide: 'Précisez ci-dessous', detail: 'a_refacturer_detail'),
];

class ClotureScreen extends StatefulWidget {
  final Map<String, dynamic> demande;
  const ClotureScreen({super.key, required this.demande});
  @override
  State<ClotureScreen> createState() => _ClotureScreenState();
}

class _ClotureScreenState extends State<ClotureScreen> {
  late Map<String, dynamic> _cloture;
  late final Map<String, dynamic> _depenses;
  final _observations = TextEditingController();
  String? _departReel;
  String? _retourReel;
  Map<String, dynamic> _erreurs = {};
  bool _enCours = false;

  int get _id => widget.demande['id'] as int;
  String get _devise => widget.demande['devise'] as String? ?? 'XOF';

  @override
  void initState() {
    super.initState();
    _cloture = Map<String, dynamic>.from(widget.demande['cloture'] as Map);
    _depenses = Map<String, dynamic>.from(_cloture['depenses'] as Map? ?? {});
    _observations.text = _cloture['observations'] as String? ?? '';
    final mission = widget.demande['mission'] as Map? ?? {};
    _departReel = _iso(_cloture['depart_reel'] ?? mission['depart_le']);
    _retourReel = _iso(_cloture['retour_reel'] ?? mission['retour_le']);
  }

  @override
  void dispose() {
    _observations.dispose();
    super.dispose();
  }

  String? _iso(dynamic v) {
    final d = DateTime.tryParse('${v ?? ''}');
    return d == null ? null : versIsoLocal(d.toLocal());
  }

  Map<String, dynamic> get _saisie => {
        'depart_reel': _departReel,
        'retour_reel': _retourReel,
        'observations': _observations.text.trim(),
        'depenses': {
          for (final r in rubriquesCloture) ...{
            r.cle: num.tryParse('${_depenses[r.cle] ?? ''}'.replaceAll(',', '.')) ?? 0,
            if (r.detail != null) r.detail!: _depenses[r.detail] ?? '',
          },
        },
      };

  Future<bool> _enregistrer({bool silencieux = false}) async {
    setState(() {
      _enCours = true;
      _erreurs = {};
    });
    try {
      final c = await demandesService.enregistrerCloture(_id, _saisie);
      setState(() => _cloture = c);
      if (!silencieux && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Clôture enregistrée.')));
      }
      return true;
    } catch (e) {
      final data = e is DioException ? e.response?.data : null;
      setState(() => _erreurs = data is Map ? Map<String, dynamic>.from(data) : {});
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(messageErreurApi(e) ?? 'Enregistrement impossible.'), backgroundColor: AppColors.error));
      }
      return false;
    } finally {
      if (mounted) setState(() => _enCours = false);
    }
  }

  Future<void> _soumettre() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('Soumettre la clôture ?'),
        content: const Text('Vos dépenses réelles et le rapport partent au contrôle et ne seront plus modifiables, sauf retour.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Annuler')),
          FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Soumettre')),
        ],
      ),
    );
    if (ok != true || !await _enregistrer(silencieux: true) || !mounted) return;
    setState(() => _enCours = true);
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    try {
      await demandesService.soumettreCloture(_id);
      messenger.showSnackBar(const SnackBar(content: Text('Clôture soumise au contrôle.'), backgroundColor: AppColors.success));
      navigator.pop(true);
    } catch (e) {
      final data = e is DioException ? e.response?.data : null;
      setState(() {
        _enCours = false;
        _erreurs = data is Map ? Map<String, dynamic>.from(data) : {};
      });
      messenger.showSnackBar(SnackBar(content: Text(messageErreurApi(e) ?? 'Soumission impossible.'), backgroundColor: AppColors.error));
    }
  }

  Future<void> _joindre(Map piece) async {
    final fichier = await choisirPiece(context);
    if (fichier == null || !mounted) return;
    setState(() => _enCours = true);
    final messenger = ScaffoldMessenger.of(context);
    try {
      await demandesService.ajouterDocument(_id, fichier.chemin, fichier.nom, typePiece: piece['id'] as int);
      final d = await demandesService.demande(_id);
      setState(() => _cloture = Map<String, dynamic>.from(d['cloture'] as Map));
      messenger.showSnackBar(SnackBar(content: Text('${piece['libelle']} jointe.'), backgroundColor: AppColors.success));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(messageErreurApi(e) ?? 'Envoi impossible.'), backgroundColor: AppColors.error));
    } finally {
      if (mounted) setState(() => _enCours = false);
    }
  }

  Future<void> _choisirDate(bool depart) async {
    final actuelle = DateTime.tryParse((depart ? _departReel : _retourReel) ?? '') ?? DateTime.now();
    final jour = await showDatePicker(
      context: context,
      initialDate: actuelle,
      firstDate: DateTime.now().subtract(const Duration(days: 730)),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );
    if (jour == null || !mounted) return;
    final h = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(actuelle));
    if (h == null) return;
    final v = versIsoLocal(DateTime(jour.year, jour.month, jour.day, h.hour, h.minute));
    setState(() => depart ? _departReel = v : _retourReel = v);
  }

  String? _erreur(String cle) {
    final e = _erreurs[cle] ?? (_erreurs['depenses'] as Map?)?[cle];
    return e == null ? null : (e is List ? e.join(' ') : '$e');
  }

  @override
  Widget build(BuildContext context) {
    final calcul = Map<String, dynamic>.from(_cloture['calcul'] as Map? ?? {});
    final pieces = List<Map>.from(_cloture['pieces_cloture'] as List? ?? []);
    final modifiable = (_cloture['actions'] as Map?)?['modifier'] == true;
    return Scaffold(
      body: Column(children: [
        EnTeteMarine(titre: 'Clôture de la mission', sousTitre: '${widget.demande['reference']} · ${_cloture['etat_libelle']}'),
        Expanded(
          child: ListView(padding: const EdgeInsets.fromLTRB(14, 14, 14, 24), children: [
            if ((_cloture['motif_retour'] as String? ?? '').isNotEmpty) ...[
              BandeauInfo(icone: Icons.undo_rounded, ton: TonPastille.or, texte: 'Retournée : ${_cloture['motif_retour']}'),
              const SizedBox(height: 12),
            ],
            const LibelleSection('Dates réelles'),
            Row(children: [
              Expanded(child: _date('Départ réel', _departReel, _erreur('depart_reel'), modifiable ? () => _choisirDate(true) : null)),
              const SizedBox(width: 8),
              Expanded(child: _date('Retour réel', _retourReel, _erreur('retour_reel'), modifiable ? () => _choisirDate(false) : null)),
            ]),
            const SizedBox(height: 8),
            LibelleSection('Dépenses réelles ($_devise)'),
            for (final r in rubriquesCloture) ...[
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: TextFormField(
                  initialValue: '${_depenses[r.cle] ?? ''}' == '0' ? '' : '${_depenses[r.cle] ?? ''}',
                  enabled: modifiable,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: InputDecoration(labelText: r.libelle, helperText: r.aide.isEmpty ? null : r.aide,
                      errorText: _erreur(r.cle), border: const OutlineInputBorder(), isDense: true),
                  onChanged: (v) => _depenses[r.cle] = v,
                ),
              ),
              if (r.detail != null && (num.tryParse('${_depenses[r.cle] ?? ''}') ?? 0) > 0)
                Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: TextFormField(
                    initialValue: '${_depenses[r.detail] ?? ''}',
                    enabled: modifiable,
                    decoration: InputDecoration(labelText: 'Précisions : ${r.libelle.toLowerCase()}', errorText: _erreur(r.detail!),
                        border: const OutlineInputBorder(), isDense: true),
                    onChanged: (v) => _depenses[r.detail!] = v,
                  ),
                ),
            ],
            TextField(
              controller: _observations,
              enabled: modifiable,
              minLines: 2,
              maxLines: 5,
              decoration: const InputDecoration(labelText: 'Observations et déroulement de la mission', border: OutlineInputBorder()),
            ),
            const SizedBox(height: 14),

            if (pieces.isNotEmpty) ...[
              const LibelleSection('Pièces de clôture'),
              CarteListe(lignes: [
                for (final p in pieces)
                  ListTile(
                    leading: Icon(p['fournie'] == true ? Icons.check_circle_rounded : Icons.error_outline_rounded,
                        color: p['fournie'] == true ? AppColors.success : AppColors.error),
                    title: Text('${p['libelle']}${p['obligatoire'] == true ? '' : ' (facultative)'}'),
                    trailing: modifiable
                        ? TextButton.icon(onPressed: _enCours ? null : () => _joindre(p),
                            icon: const Icon(Icons.attach_file_rounded, size: 18), label: Text(p['fournie'] == true ? 'Ajouter' : 'Joindre'))
                        : null,
                  ),
              ]),
              const SizedBox(height: 14),
            ],

            const LibelleSection('Solde de la mission'),
            CarteListe(lignes: [
              for (final (l, v) in resumeCloture({..._cloture, 'etat_libelle': _cloture['etat_libelle']}, _devise).skip(1))
                ListTile(dense: true, title: Text(l), trailing: Text(v, style: const TextStyle(fontWeight: FontWeight.w700))),
              if (calcul.isEmpty)
                const ListTile(dense: true, title: Text('Enregistrez pour calculer le solde.', style: TextStyle(fontSize: 12))),
            ]),
            if (modifiable) ...[
              const SizedBox(height: 20),
              BoutonVert(label: 'Soumettre la clôture', icone: Icons.send_rounded, chargement: _enCours, onPressed: _soumettre),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: _enCours ? null : () => _enregistrer(),
                icon: const Icon(Icons.save_outlined),
                label: const Text('Enregistrer et recalculer'),
              ),
            ],
          ]),
        ),
      ]),
    );
  }

  Widget _date(String libelle, String? valeur, String? erreur, VoidCallback? onTap) => InkWell(
        onTap: onTap,
        child: InputDecorator(
          decoration: InputDecoration(labelText: libelle, errorText: erreur, border: const OutlineInputBorder(),
              prefixIcon: const Icon(Icons.event_rounded), enabled: onTap != null),
          isEmpty: valeur == null,
          child: Text(valeur == null ? '' : dateCourte(valeur)),
        ),
      );
}
