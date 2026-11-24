// lib/features/demandes/mission_saisie.dart
//
// Saisie d'une mission (locale ou hors pays) avec l'estimation des frais
// recalculée en direct par le serveur (mêmes règles et barèmes que le web).
// La map `mission` est modifiée en place et envoyée telle quelle à l'API.

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../core/services/demandes_service.dart';
import '../../core/widgets/common_widgets.dart';
import 'commun.dart';

const fraisParType = {
  'locale': ['hebergement', 'autres'],
  'hors_pays': ['visa', 'aerien', 'hebergement', 'autres'],
};

/// « 2026-12-02T08:00 » (heure locale, format attendu par l'API)
String versIsoLocal(DateTime d) => DateFormat("yyyy-MM-dd'T'HH:mm").format(d);

class MissionSaisie extends StatefulWidget {
  final Map<String, dynamic> mission;
  final int typeDemande;
  final String typeMission;
  final int? demandeId;
  /// Erreurs de l'API pour la mission : { champ: message }
  final Map erreurs;
  const MissionSaisie({
    super.key,
    required this.mission,
    required this.typeDemande,
    required this.typeMission,
    this.demandeId,
    this.erreurs = const {},
  });

  @override
  State<MissionSaisie> createState() => _MissionSaisieState();
}

class _MissionSaisieState extends State<MissionSaisie> {
  List<Map<String, dynamic>> _villes = [];
  Map<String, dynamic>? _calcul;
  bool _calculEnCours = false;
  Timer? _minuterie;
  int _requete = 0;

  Map<String, dynamic> get m => widget.mission;
  bool get _horsPays => widget.typeMission == 'hors_pays';

  @override
  void initState() {
    super.initState();
    m['trajet'] ??= 'aller_retour';
    m['frais'] ??= <Map<String, dynamic>>[];
    m['moyen_transport'] ??= _horsPays ? 'avion' : 'transport_commun';
    for (final cle in ['depart_le', 'retour_le']) {
      final d = DateTime.tryParse('${m[cle] ?? ''}');
      if (d != null) m[cle] = versIsoLocal(d.toLocal());
    }
    demandesService.villes().then((v) {
      if (mounted) setState(() => _villes = v);
    }).catchError((_) {});
    _changer();
  }

  @override
  void dispose() {
    _minuterie?.cancel();
    super.dispose();
  }

  void _changer() {
    setState(() {});
    _minuterie?.cancel();
    _minuterie = Timer(const Duration(milliseconds: 500), () async {
      final n = ++_requete;
      setState(() => _calculEnCours = true);
      try {
        final c = await demandesService.calculer(widget.typeDemande, m, demande: widget.demandeId);
        if (mounted && n == _requete) setState(() => _calcul = c);
      } catch (_) {
        if (mounted && n == _requete) setState(() => _calcul = null);
      } finally {
        if (mounted && n == _requete) setState(() => _calculEnCours = false);
      }
    });
  }

  String? _erreur(String cle) {
    final e = widget.erreurs[cle] ?? (_calcul?['champs'] as Map?)?[cle];
    if (e == null) return null;
    return e is List ? e.join(' ') : '$e';
  }

  String? get _paysLocal {
    final depart = _villes.where((v) => v['id'] == m['ville_depart']).firstOrNull;
    return depart?['pays_code'] as String? ?? (_villes.any((v) => v['pays_code'] == 'CI') ? 'CI' : null);
  }

  List<Map<String, dynamic>> get _villesDepart {
    final p = _paysLocal;
    return p == null ? _villes : _villes.where((v) => v['pays_code'] == p).toList();
  }

  List<Map<String, dynamic>> get _villesDestination {
    final p = _paysLocal;
    if (p == null) return _villes;
    return _villes.where((v) => _horsPays ? v['pays_code'] != p : v['pays_code'] == p).toList();
  }

  String _libelleVille(Map v) => _horsPays ? '${v['libelle']} (${v['pays_libelle']})' : '${v['libelle']}';

  bool get _transportManuel {
    final x = m['montant_transport_manuel'];
    return (x != null && x != '') ||
        List<String>.from(_calcul?['erreurs'] as List? ?? []).any((e) => e.startsWith('Aucun tarif de transport'));
  }

  Future<void> _choisirVille(String cle, List<Map<String, dynamic>> villes, String titre) async {
    final choisie = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _ChoixVille(villes: villes, titre: titre, libelle: _libelleVille),
    );
    if (choisie != null) {
      m[cle] = choisie['id'];
      _changer();
    }
  }

  Future<void> _choisirDate(String cle) async {
    final actuelle = DateTime.tryParse('${m[cle] ?? ''}') ??
        DateTime.tryParse('${m['depart_le'] ?? ''}') ??
        DateTime.now().add(const Duration(days: 1)).copyWith(hour: 8, minute: 0);
    final jour = await showDatePicker(
      context: context,
      initialDate: actuelle,
      firstDate: DateTime.now().subtract(const Duration(days: 365)),
      lastDate: DateTime.now().add(const Duration(days: 730)),
    );
    if (jour == null || !mounted) return;
    final heure = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(actuelle));
    if (heure == null) return;
    m[cle] = versIsoLocal(DateTime(jour.year, jour.month, jour.day, heure.hour, heure.minute));
    _changer();
  }

  @override
  Widget build(BuildContext context) {
    final villeDepart = _villes.where((v) => v['id'] == m['ville_depart']).firstOrNull;
    final villeDestination = _villes.where((v) => v['id'] == m['ville_destination']).firstOrNull;
    final rubriques = fraisParType[widget.typeMission]!;
    final frais = List<Map>.from(m['frais'] as List);
    final distanceRef = (_calcul?['mission'] as Map?)?['distance_referentiel_km'];
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      _Champ(
        erreur: _erreur('motif'),
        child: TextFormField(
          initialValue: '${m['motif'] ?? ''}',
          minLines: 2,
          maxLines: 4,
          decoration: const InputDecoration(labelText: 'Motif et justification de la mission *', border: OutlineInputBorder()),
          onChanged: (v) => m['motif'] = v,
        ),
      ),
      _Selecteur(
        libelle: 'Ville de départ *',
        valeur: villeDepart == null ? null : _libelleVille(villeDepart),
        erreur: _erreur('ville_depart'),
        icone: Icons.trip_origin_rounded,
        onTap: () => _choisirVille('ville_depart', _villesDepart, 'Ville de départ'),
      ),
      _Selecteur(
        libelle: _horsPays ? 'Destination (ville et pays) *' : 'Destination *',
        valeur: villeDestination == null ? null : _libelleVille(villeDestination),
        erreur: _erreur('ville_destination'),
        icone: Icons.place_outlined,
        onTap: () => _choisirVille('ville_destination', _villesDestination, 'Destination'),
      ),
      Row(children: [
        Expanded(
          child: _Selecteur(
            libelle: 'Départ *',
            valeur: m['depart_le'] == null ? null : dateCourte(m['depart_le']),
            erreur: _erreur('depart_le'),
            icone: Icons.event_rounded,
            onTap: () => _choisirDate('depart_le'),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _Selecteur(
            libelle: 'Retour *',
            valeur: m['retour_le'] == null ? null : dateCourte(m['retour_le']),
            erreur: _erreur('retour_le'),
            icone: Icons.event_available_rounded,
            onTap: () => _choisirDate('retour_le'),
          ),
        ),
      ]),
      _Champ(
        erreur: _erreur('moyen_transport'),
        child: DropdownButtonFormField<String>(
          value: m['moyen_transport'] as String?,
          decoration: const InputDecoration(labelText: 'Moyen de transport *', border: OutlineInputBorder()),
          items: [for (final e in moyensTransport.entries) DropdownMenuItem(value: e.key, child: Text(e.value))],
          onChanged: (v) {
            m['moyen_transport'] = v;
            _changer();
          },
        ),
      ),
      SegmentedButton<String>(
        segments: const [
          ButtonSegment(value: 'aller_retour', label: Text('Aller-retour')),
          ButtonSegment(value: 'aller_simple', label: Text('Aller simple')),
        ],
        selected: {m['trajet'] as String? ?? 'aller_retour'},
        onSelectionChanged: (s) {
          m['trajet'] = s.first;
          _changer();
        },
      ),
      const SizedBox(height: 12),

      // Véhicule personnel (mission locale) : distance déclarée, justifiée si elle diffère du référentiel
      if (!_horsPays && m['moyen_transport'] == 'vehicule_personnel') ...[
        _Champ(
          erreur: _erreur('distance_km'),
          child: TextFormField(
            initialValue: '${m['distance_km'] ?? ''}',
            keyboardType: TextInputType.number,
            decoration: InputDecoration(
                labelText: 'Distance (km)', border: const OutlineInputBorder(),
                helperText: distanceRef == null ? null : 'Référentiel : $distanceRef km'),
            onChanged: (v) {
              m['distance_km'] = num.tryParse(v);
              _changer();
            },
          ),
        ),
        if (m['distance_km'] != null && distanceRef != null && m['distance_km'] != distanceRef)
          _texte('justification_distance', 'Justification de la distance *'),
      ],
      // Transport en commun ou autre (mission locale) : forfait éventuel justifié
      if (!_horsPays && m['moyen_transport'] != 'vehicule_personnel' && m['moyen_transport'] != 'vehicule_service') ...[
        _Champ(
          erreur: _erreur('forfait_transport'),
          child: TextFormField(
            initialValue: '${m['forfait_transport'] ?? ''}',
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
                labelText: 'Forfait transport (facultatif)', border: OutlineInputBorder(),
                helperText: 'À la place du tarif de la ville, avec justification'),
            onChanged: (v) {
              m['forfait_transport'] = num.tryParse(v);
              _changer();
            },
          ),
        ),
        if (m['forfait_transport'] != null) _texte('justification_forfait', 'Justification du forfait *'),
      ],
      if (_transportManuel) ...[
        _Champ(
          erreur: _erreur('montant_transport_manuel'),
          child: TextFormField(
            initialValue: '${m['montant_transport_manuel'] ?? ''}',
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
                labelText: 'Montant du transport *', border: OutlineInputBorder(),
                helperText: 'Aucun tarif pour cette destination : montant à justifier'),
            onChanged: (v) {
              m['montant_transport_manuel'] = num.tryParse(v);
              _changer();
            },
          ),
        ),
        _texte('justification_transport', 'Justification du montant du transport *'),
      ],

      // Autres frais (hébergement, visa, billet d'avion…)
      Row(children: [
        const Expanded(child: LibelleSection('Autres frais')),
        TextButton.icon(
          onPressed: () {
            (m['frais'] as List).add(<String, dynamic>{'rubrique': rubriques.first, 'montant': null, 'devise': 'XOF', 'description': ''});
            _changer();
          },
          icon: const Icon(Icons.add_rounded),
          label: const Text('Ajouter'),
        ),
      ]),
      for (var i = 0; i < frais.length; i++) _ligneFrais(i, frais[i], rubriques),

      const SizedBox(height: 8),
      _recapitulatif(),
    ]);
  }

  Widget _texte(String cle, String libelle) => _Champ(
        erreur: _erreur(cle),
        child: TextFormField(
          initialValue: '${m[cle] ?? ''}',
          minLines: 1,
          maxLines: 3,
          decoration: InputDecoration(labelText: libelle, border: const OutlineInputBorder()),
          onChanged: (v) => m[cle] = v,
        ),
      );

  Widget _ligneFrais(int i, Map f, List<String> rubriques) => Padding(
        key: ObjectKey(f),
        padding: const EdgeInsets.only(bottom: 10),
        child: CarteListe(lignes: [
          Padding(
            padding: const EdgeInsets.all(10),
            child: Column(children: [
              Row(children: [
                Expanded(
                  child: DropdownButtonFormField<String>(
                    value: rubriques.contains(f['rubrique']) ? f['rubrique'] as String : rubriques.first,
                    isDense: true,
                    decoration: const InputDecoration(labelText: 'Rubrique', border: OutlineInputBorder()),
                    items: [for (final r in rubriques) DropdownMenuItem(value: r, child: Text(rubriquesMission[r] ?? r))],
                    onChanged: (v) {
                      f['rubrique'] = v;
                      _changer();
                    },
                  ),
                ),
                IconButton(
                  tooltip: 'Retirer',
                  icon: const Icon(Icons.delete_outline_rounded),
                  onPressed: () {
                    (m['frais'] as List).removeAt(i);
                    _changer();
                  },
                ),
              ]),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(
                  flex: 3,
                  child: TextFormField(
                    initialValue: '${f['montant'] ?? ''}',
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(labelText: 'Montant', isDense: true, border: OutlineInputBorder()),
                    onChanged: (v) {
                      f['montant'] = num.tryParse(v);
                      _changer();
                    },
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  flex: 2,
                  child: DropdownButtonFormField<String>(
                    value: ['XOF', 'EUR', 'USD'].contains(f['devise']) ? f['devise'] as String : 'XOF',
                    isDense: true,
                    decoration: const InputDecoration(labelText: 'Devise', border: OutlineInputBorder()),
                    items: [for (final d in ['XOF', 'EUR', 'USD']) DropdownMenuItem(value: d, child: Text(d))],
                    onChanged: (v) {
                      f['devise'] = v;
                      _changer();
                    },
                  ),
                ),
              ]),
              const SizedBox(height: 8),
              TextFormField(
                initialValue: '${f['description'] ?? ''}',
                decoration: const InputDecoration(labelText: 'Description', isDense: true, border: OutlineInputBorder()),
                onChanged: (v) => f['description'] = v,
              ),
            ]),
          ),
        ]),
      );

  Widget _recapitulatif() {
    final c = _calcul;
    final erreurs = List<String>.from(c?['erreurs'] as List? ?? []);
    final signalements = List<String>.from(c?['signalements'] as List? ?? []);
    return CarteListe(lignes: [
      ListTile(
        dense: true,
        title: const Text('Estimation des frais', style: TextStyle(fontWeight: FontWeight.w700)),
        subtitle: c?['categorie'] != null ? Text('Catégorie ${c!['categorie']} · barèmes du ${c['date_baremes'] ?? '—'}') : null,
        trailing: _calculEnCours ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)) : null,
      ),
      if (c != null)
        for (final (rubrique, detail, valeur) in lignesRecap(c))
          ListTile(
            dense: true,
            title: Text(rubrique, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
            subtitle: Text(detail, style: const TextStyle(fontSize: 12)),
            trailing: Text(valeur, style: const TextStyle(fontWeight: FontWeight.w600)),
          ),
      if (c != null)
        ListTile(
          dense: true,
          title: const Text('Total prévisionnel', style: TextStyle(fontWeight: FontWeight.w800)),
          trailing: Text(montant(c['total_ref'], c['devise_reference'] as String? ?? ''),
              style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 15)),
        ),
      for (final e in erreurs)
        ListTile(dense: true, leading: const Icon(Icons.error_outline_rounded, color: Colors.red), title: Text(e, style: const TextStyle(fontSize: 12))),
      for (final s in signalements)
        ListTile(dense: true, leading: const Icon(Icons.warning_amber_rounded, color: Colors.orange), title: Text(s, style: const TextStyle(fontSize: 12))),
      if (c == null && !_calculEnCours)
        const ListTile(dense: true, title: Text('Renseignez le trajet et les dates pour obtenir l\'estimation.', style: TextStyle(fontSize: 12))),
    ]);
  }
}

/// Champ avec message d'erreur de l'API dessous
class _Champ extends StatelessWidget {
  final Widget child;
  final String? erreur;
  const _Champ({required this.child, this.erreur});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          child,
          if (erreur != null)
            Padding(
              padding: const EdgeInsets.only(top: 4, left: 4),
              child: Text(erreur!, style: TextStyle(color: Theme.of(context).colorScheme.error, fontSize: 12)),
            ),
        ]),
      );
}

class _Selecteur extends StatelessWidget {
  final String libelle;
  final String? valeur;
  final String? erreur;
  final IconData icone;
  final VoidCallback onTap;
  const _Selecteur({required this.libelle, required this.valeur, required this.icone, required this.onTap, this.erreur});

  @override
  Widget build(BuildContext context) => _Champ(
        erreur: erreur,
        child: InkWell(
          onTap: onTap,
          child: InputDecorator(
            decoration: InputDecoration(labelText: libelle, border: const OutlineInputBorder(), prefixIcon: Icon(icone)),
            isEmpty: valeur == null,
            child: Text(valeur ?? '', maxLines: 1, overflow: TextOverflow.ellipsis),
          ),
        ),
      );
}

class _ChoixVille extends StatefulWidget {
  final List<Map<String, dynamic>> villes;
  final String titre;
  final String Function(Map) libelle;
  const _ChoixVille({required this.villes, required this.titre, required this.libelle});
  @override
  State<_ChoixVille> createState() => _ChoixVilleState();
}

class _ChoixVilleState extends State<_ChoixVille> {
  String _recherche = '';

  @override
  Widget build(BuildContext context) {
    final t = _recherche.toLowerCase();
    final villes = widget.villes.where((v) => widget.libelle(v).toLowerCase().contains(t)).toList();
    return SafeArea(
      child: Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
        child: SizedBox(
          height: MediaQuery.of(context).size.height * 0.75,
          child: Column(children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
              child: TextField(
                autofocus: true,
                decoration: InputDecoration(labelText: widget.titre, prefixIcon: const Icon(Icons.search_rounded),
                    border: const OutlineInputBorder()),
                onChanged: (v) => setState(() => _recherche = v),
              ),
            ),
            Expanded(
              child: villes.isEmpty
                  ? const EmptyState(icon: Icons.location_off_outlined, title: 'Aucune ville')
                  : ListView.builder(
                      itemCount: villes.length,
                      itemBuilder: (_, i) => ListTile(
                        title: Text(widget.libelle(villes[i])),
                        onTap: () => Navigator.pop(context, villes[i]),
                      ),
                    ),
            ),
          ]),
        ),
      ),
    );
  }
}
