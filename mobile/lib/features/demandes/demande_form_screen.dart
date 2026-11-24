// lib/features/demandes/demande_form_screen.dart
//
// Saisie d'une demande : création (brouillon) ou modification (brouillon,
// retour pour correction). Objet, montant, champs propres au type, demande
// de rattachement (frais complémentaires, annulation) et mission avec calcul
// en direct. « Enregistrer » garde un brouillon ; « Soumettre » l'envoie au
// circuit de validation. Les pièces jointes s'ajoutent depuis la fiche.

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../core/api/api_client.dart';
import '../../core/services/demandes_service.dart';
import '../../core/widgets/common_widgets.dart';
import '../../shared/theme/app_theme.dart';
import 'demande_detail_screen.dart';
import 'mission_saisie.dart';

/// Erreurs champ par champ renvoyées par l'API (400), ou null.
Map<String, dynamic>? erreursChamps(Object e) {
  final data = e is DioException ? e.response?.data : null;
  return data is Map ? Map<String, dynamic>.from(data) : null;
}

class DemandeFormScreen extends StatefulWidget {
  final Map<String, dynamic> type;
  /// Demande à modifier (null : création)
  final Map<String, dynamic>? demande;
  /// Erreurs à afficher d'emblée (soumission refusée juste après la création)
  final Map<String, dynamic> erreurs;
  const DemandeFormScreen({super.key, required this.type, this.demande, this.erreurs = const {}});

  @override
  State<DemandeFormScreen> createState() => _DemandeFormScreenState();
}

class _DemandeFormScreenState extends State<DemandeFormScreen> {
  final _objet = TextEditingController();
  final _montant = TextEditingController();
  late final Map<String, dynamic> _donnees;
  late final Map<String, dynamic> _mission;
  List<Map<String, dynamic>> _parents = [];
  int? _parent;
  List<Map<String, dynamic>> _collaborateurs = [];
  Map<String, dynamic> _erreurs = {};
  bool _enCours = false;

  Map<String, dynamic> get t => widget.type;
  bool get _estMission => t['famille'] == 'mission';
  bool get _avecParent => (t['parametres'] as Map?)?['parent'] != null;
  bool get _avecMontant => t['avec_montant'] == true && !_estMission;
  String get _typeMission => (t['parametres'] as Map?)?['type_mission'] as String? ?? 'locale';
  List<Map> get _champs => List<Map>.from(t['champs'] as List? ?? []).where((c) => c['actif'] != false).toList();

  @override
  void initState() {
    super.initState();
    final d = widget.demande;
    _erreurs = Map<String, dynamic>.from(widget.erreurs);
    _objet.text = d?['objet'] as String? ?? '';
    _montant.text = d?['montant_demande'] == null ? '' : '${num.tryParse('${d!['montant_demande']}') ?? ''}';
    _donnees = Map<String, dynamic>.from(d?['donnees'] as Map? ?? {})..remove('mission');
    _mission = Map<String, dynamic>.from(d?['mission'] as Map? ?? {});
    _mission['frais'] = [for (final f in List.from(_mission['frais'] as List? ?? [])) Map<String, dynamic>.from(f as Map)];
    _parent = d?['demande_parent'] as int?;
    if (_avecParent && d == null) {
      demandesService.parentsPossibles(t['id'] as int).then((p) {
        if (!mounted) return;
        setState(() {
          _parents = p;
          if (p.length == 1) _parent = p.first['id'] as int;
        });
      }).catchError((_) {});
    }
    if (_champs.any((c) => c['nature'] == 'collaborateur')) {
      demandesService.annuaire().then((c) {
        if (mounted) setState(() => _collaborateurs = c);
      }).catchError((_) {});
    }
  }

  @override
  void dispose() {
    _objet.dispose();
    _montant.dispose();
    super.dispose();
  }

  String? _erreur(String cle, [Map? source]) {
    final donnees = source == null ? _erreurs['donnees'] as Map? : null;
    final e = (source ?? _erreurs)[cle] ?? donnees?[cle];
    if (e == null) return null;
    return e is List ? e.join(' ') : '$e';
  }

  Map<String, dynamic> get _contenu => {
        'objet': _objet.text.trim(),
        if (_avecMontant) 'montant_demande': num.tryParse(_montant.text.replaceAll(' ', '').replaceAll(',', '.')),
        'donnees': _donnees,
        if (_estMission) 'mission': _mission,
      };

  Future<void> _enregistrer({required bool soumettre}) async {
    if (_enCours) return;
    if (soumettre) {
      final ok = await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: const Text('Soumettre la demande ?'),
          content: const Text('Elle part en validation et ne sera plus modifiable, sauf retour pour correction.'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Annuler')),
            FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Soumettre')),
          ],
        ),
      );
      if (ok != true || !mounted) return;
    }
    setState(() {
      _enCours = true;
      _erreurs = {};
    });
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    Map<String, dynamic> d;
    try {
      d = widget.demande == null
          ? await demandesService.creer({
              'type_demande': t['id'],
              ..._contenu,
              if (_avecParent) 'demande_parent': _parent,
            })
          : await demandesService.modifier(widget.demande!['id'] as int, _contenu);
    } catch (e) {
      setState(() {
        _enCours = false;
        _erreurs = erreursChamps(e) ?? {};
      });
      messenger.showSnackBar(SnackBar(content: Text(messageErreurApi(e) ?? 'Vérifiez les informations saisies.'),
          backgroundColor: AppColors.error));
      return;
    }
    final id = d['id'] as int;
    if (soumettre) {
      try {
        final s = await demandesService.soumettre(id);
        messenger.showSnackBar(SnackBar(content: Text('Demande ${s['reference']} soumise.'), backgroundColor: AppColors.success));
      } catch (e) {
        // Le brouillon est enregistré : on reste sur le formulaire pour corriger ce qui bloque
        final erreurs = erreursChamps(e) ?? {};
        setState(() {
          _enCours = false;
          _erreurs = erreurs;
        });
        messenger.showSnackBar(SnackBar(
            content: Text('Brouillon enregistré, soumission impossible : ${messageErreurApi(e) ?? 'vérifiez la saisie.'}'),
            backgroundColor: AppColors.error));
        if (widget.demande == null) {
          navigator.pushReplacement(MaterialPageRoute(
              builder: (_) => DemandeFormScreen(type: t, demande: d, erreurs: erreurs)));
        }
        return;
      }
    } else {
      messenger.showSnackBar(const SnackBar(content: Text('Brouillon enregistré.')));
    }
    // Retour à la fiche (remplace le formulaire)
    if (widget.demande != null) {
      navigator.pop(true);
    } else {
      navigator.pushReplacement(MaterialPageRoute(builder: (_) => DemandeDetailScreen(id: id)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final modification = widget.demande != null;
    return Scaffold(
      body: Column(children: [
        EnTeteMarine(
          titre: modification ? 'Modifier la demande' : 'Nouvelle demande',
          sousTitre: '${t['libelle']}${modification && widget.demande!['reference'] != null ? ' · ${widget.demande!['reference']}' : ''}',
        ),
        Expanded(
          child: ListView(padding: const EdgeInsets.fromLTRB(14, 14, 14, 24), children: [
            if ((t['description'] as String? ?? '').isNotEmpty && !modification) ...[
              BandeauInfo(icone: Icons.info_outline_rounded, texte: '${t['description']}', ton: TonPastille.bleu),
              const SizedBox(height: 12),
            ],
            if (widget.demande?['statut'] == 'a_corriger') ...[
              const BandeauInfo(icone: Icons.undo_rounded, texte: 'Demande retournée pour correction : modifiez puis soumettez à nouveau.',
                  ton: TonPastille.or),
              const SizedBox(height: 12),
            ],
            _champ(TextField(
              controller: _objet,
              decoration: const InputDecoration(labelText: 'Objet *', border: OutlineInputBorder()),
            ), _erreur('objet')),
            if (_avecParent && !modification)
              _champ(DropdownButtonFormField<int>(
                value: _parent,
                isExpanded: true,
                decoration: const InputDecoration(labelText: 'Demande concernée *', border: OutlineInputBorder()),
                items: [
                  for (final p in _parents)
                    DropdownMenuItem(
                      value: p['id'] as int,
                      child: Text('${p['reference']} · ${p['objet']}', overflow: TextOverflow.ellipsis),
                    ),
                ],
                onChanged: (v) => setState(() => _parent = v),
              ), _erreur('demande_parent') ?? (_parents.isEmpty ? 'Aucune demande ne peut être rattachée pour le moment.' : null)),
            if (_avecMontant)
              _champ(TextField(
                controller: _montant,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                decoration: const InputDecoration(labelText: 'Montant demandé (XOF) *', border: OutlineInputBorder()),
              ), _erreur('montant_demande')),
            for (final c in _champs) _champDynamique(c),
            if (_estMission) ...[
              const LibelleSection('Mission'),
              MissionSaisie(
                mission: _mission,
                typeDemande: t['id'] as int,
                typeMission: _typeMission,
                demandeId: widget.demande?['id'] as int?,
                erreurs: Map.from(_erreurs['mission'] as Map? ?? {}),
              ),
            ],
            if (_erreurs['circuit'] != null || _erreurs['pieces'] != null) ...[
              const SizedBox(height: 12),
              BandeauInfo(icone: Icons.error_outline_rounded, ton: TonPastille.rouge,
                  texte: _erreur('circuit') ?? _erreur('pieces') ?? ''),
            ],
            const SizedBox(height: 20),
            BoutonVert(
              label: modification && widget.demande!['statut'] == 'a_corriger' ? 'Soumettre à nouveau' : 'Soumettre',
              icone: Icons.send_rounded,
              chargement: _enCours,
              onPressed: () => _enregistrer(soumettre: true),
            ),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: _enCours ? null : () => _enregistrer(soumettre: false),
              icon: const Icon(Icons.save_outlined),
              label: Text(modification ? 'Enregistrer les modifications' : 'Enregistrer le brouillon'),
            ),
            const SizedBox(height: 6),
            Text('Les pièces justificatives se joignent depuis la fiche de la demande (photo ou fichier).',
                style: Theme.of(context).textTheme.bodySmall, textAlign: TextAlign.center),
          ]),
        ),
      ]),
    );
  }

  Widget _champ(Widget child, String? erreur) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          child,
          if (erreur != null)
            Padding(
              padding: const EdgeInsets.only(top: 4, left: 4),
              child: Text(erreur, style: TextStyle(color: Theme.of(context).colorScheme.error, fontSize: 12)),
            ),
        ]),
      );

  Widget _champDynamique(Map c) {
    final code = c['code'] as String;
    final libelle = '${c['libelle']}${c['obligatoire'] == true ? ' *' : ''}';
    final aide = (c['aide'] as String? ?? '').isEmpty ? null : c['aide'] as String;
    final erreur = _erreur(code);
    final deco = InputDecoration(labelText: libelle, helperText: aide, border: const OutlineInputBorder());
    switch (c['nature']) {
      case 'texte_long':
        return _champ(TextFormField(initialValue: '${_donnees[code] ?? ''}', minLines: 2, maxLines: 5, decoration: deco,
            onChanged: (v) => _donnees[code] = v), erreur);
      case 'entier':
      case 'montant':
        return _champ(TextFormField(
          initialValue: '${_donnees[code] ?? ''}',
          keyboardType: TextInputType.numberWithOptions(decimal: c['nature'] == 'montant'),
          decoration: deco,
          onChanged: (v) => _donnees[code] = c['nature'] == 'entier' ? int.tryParse(v) : num.tryParse(v.replaceAll(',', '.')),
        ), erreur);
      case 'booleen':
        return _champ(SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: Text(libelle),
          subtitle: aide == null ? null : Text(aide),
          value: _donnees[code] == true,
          onChanged: (v) => setState(() => _donnees[code] = v),
        ), erreur);
      case 'liste':
        final options = List<String>.from(c['options'] as List? ?? []);
        return _champ(DropdownButtonFormField<String>(
          value: options.contains(_donnees[code]) ? _donnees[code] as String : null,
          decoration: deco,
          items: [for (final o in options) DropdownMenuItem(value: o, child: Text(o))],
          onChanged: (v) => setState(() => _donnees[code] = v),
        ), erreur);
      case 'date':
      case 'datetime':
        final avecHeure = c['nature'] == 'datetime';
        final valeur = DateTime.tryParse('${_donnees[code] ?? ''}');
        return _champ(InkWell(
          onTap: () async {
            final jour = await showDatePicker(
              context: context,
              initialDate: valeur ?? DateTime.now(),
              firstDate: DateTime(2000),
              lastDate: DateTime.now().add(const Duration(days: 1095)),
            );
            if (jour == null || !mounted) return;
            var choisi = jour;
            if (avecHeure) {
              final h = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(valeur ?? DateTime.now()));
              if (h == null) return;
              choisi = DateTime(jour.year, jour.month, jour.day, h.hour, h.minute);
            }
            setState(() => _donnees[code] =
                avecHeure ? versIsoLocal(choisi) : DateFormat('yyyy-MM-dd').format(choisi));
          },
          child: InputDecorator(
            decoration: deco.copyWith(prefixIcon: const Icon(Icons.event_rounded)),
            isEmpty: valeur == null,
            child: Text(valeur == null ? '' : DateFormat(avecHeure ? 'dd/MM/yyyy HH:mm' : 'dd/MM/yyyy').format(valeur)),
          ),
        ), erreur);
      case 'collaborateur':
        final actuel = _collaborateurs.where((x) => x['id'] == _donnees[code]).firstOrNull;
        return _champ(DropdownButtonFormField<int>(
          value: actuel?['id'] as int?,
          isExpanded: true,
          decoration: deco,
          items: [for (final x in _collaborateurs) DropdownMenuItem(value: x['id'] as int, child: Text('${x['libelle']}'))],
          onChanged: (v) => setState(() => _donnees[code] = v),
        ), erreur);
      default:
        return _champ(TextFormField(initialValue: '${_donnees[code] ?? ''}', decoration: deco,
            onChanged: (v) => _donnees[code] = v), erreur);
    }
  }
}
