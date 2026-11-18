// lib/features/statistiques/statistiques_screen.dart
//
// Statistiques (version légère du web) :
//  - gestionnaire / administrateur : chiffres clés, montants par mois,
//    plats les plus commandés, participation par agence, desserts, heure de
//    pointe (GET statistiques/?resume=1, statistiques/indicateurs/,
//    statistiques/complements/) ;
//  - prestataire responsable : ses repas, montant dû, plats, desserts,
//    heure de pointe (GET prestataire/statistiques/indicateurs/).

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../core/api/api_client.dart';
import '../../core/widgets/common_widgets.dart';
import '../../shared/theme/app_theme.dart';
import '../prestataire/prestataire_widgets.dart' show CartePresta;

enum PeriodeStats { mois, precedent, trimestre }

/// Données agrégées de l'écran (JSON des API, lu prudemment)
class DonneesStats {
  final Map<String, dynamic> resume; // kpis UbiPharm (vide pour le prestataire)
  final Map<String, dynamic> indicateurs; // plats + montants
  final Map<String, dynamic> complements; // desserts, participation, affluence…
  const DonneesStats(
      {this.resume = const {},
      this.indicateurs = const {},
      this.complements = const {}});
}

typedef ChargeurStats = Future<DonneesStats> Function(
    bool prestataire, String debut, String fin);

Future<DonneesStats> chargerStatsApi(
    bool prestataire, String debut, String fin) async {
  final p = {'debut': debut, 'fin': fin};
  Map<String, dynamic> m(dynamic d) =>
      d is Map ? Map<String, dynamic>.from(d) : <String, dynamic>{};
  if (prestataire) {
    final r = m((await apiClient.get('/prestataire/statistiques/indicateurs/',
            params: p))
        .data);
    return DonneesStats(indicateurs: r, complements: m(r['complements']));
  }
  final res = await Future.wait([
    apiClient.get('/statistiques/', params: {...p, 'resume': '1'}),
    apiClient.get('/statistiques/indicateurs/', params: p),
    apiClient.get('/statistiques/complements/', params: p),
  ]);
  return DonneesStats(
      resume: m(res[0].data),
      indicateurs: m(res[1].data),
      complements: m(res[2].data));
}

class StatistiquesScreen extends StatefulWidget {
  final bool prestataire;
  final ChargeurStats chargeur;
  const StatistiquesScreen(
      {super.key, this.prestataire = false, this.chargeur = chargerStatsApi});

  @override
  State<StatistiquesScreen> createState() => _StatistiquesScreenState();
}

class _StatistiquesScreenState extends State<StatistiquesScreen> {
  PeriodeStats _periode = PeriodeStats.mois;
  DonneesStats? _d;
  String? _erreur;
  bool _chargement = false;

  static final _iso = DateFormat('yyyy-MM-dd');
  static final _nb = NumberFormat.decimalPattern('fr_FR');

  @override
  void initState() {
    super.initState();
    _charger();
  }

  (String, String) get _bornes {
    final a = DateTime.now();
    switch (_periode) {
      case PeriodeStats.precedent:
        return (
          _iso.format(DateTime(a.year, a.month - 1, 1)),
          _iso.format(DateTime(a.year, a.month, 0))
        );
      case PeriodeStats.trimestre:
        return (
          _iso.format(DateTime(a.year, a.month - 2, 1)),
          _iso.format(DateTime(a.year, a.month + 1, 0))
        );
      case PeriodeStats.mois:
        return (
          _iso.format(DateTime(a.year, a.month, 1)),
          _iso.format(DateTime(a.year, a.month + 1, 0))
        );
    }
  }

  Future<void> _charger() async {
    setState(() {
      _chargement = true;
      _erreur = null;
    });
    final (debut, fin) = _bornes;
    try {
      final d = await widget.chargeur(widget.prestataire, debut, fin);
      if (mounted) setState(() => _d = d);
    } catch (e) {
      if (mounted) {
        setState(() => _erreur = messageErreurApi(e) ??
            "Les statistiques n'ont pas pu être chargées.");
      }
    } finally {
      if (mounted) setState(() => _chargement = false);
    }
  }

  String _n(dynamic v) => v == null ? '—' : _nb.format(v is num ? v : 0);
  String _f(dynamic v) => '${_nb.format(((v ?? 0) as num).round())} F';
  String _pct(dynamic v) => v == null
      ? '—'
      : '${(v as num).toStringAsFixed(1).replaceAll('.', ',')} %';
  Map<String, dynamic> _m(dynamic v) =>
      v is Map ? Map<String, dynamic>.from(v) : <String, dynamic>{};
  List<Map<String, dynamic>> _l(dynamic v) =>
      v is List ? v.map(_m).toList() : <Map<String, dynamic>>[];

  @override
  Widget build(BuildContext context) {
    final d = _d;
    Widget corps;
    if (_erreur != null && d == null) {
      corps = ListView(padding: const EdgeInsets.all(14), children: [
        BandeauInfo(
            icone: Icons.cloud_off_rounded,
            ton: TonPastille.rouge,
            texte: _erreur!,
            action: TextButton(
                onPressed: _charger, child: const Text('Réessayer'))),
      ]);
    } else if (d == null) {
      corps = const Center(child: CircularProgressIndicator());
    } else {
      corps = RefreshIndicator(
        onRefresh: _charger,
        child: ListView(
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 24),
            children: _contenu(d)),
      );
    }
    return Scaffold(
      body: Column(children: [
        EnTeteMarine(
          titre: 'Statistiques',
          sousTitre: widget.prestataire
              ? 'Vos plats, vos montants, votre comptoir'
              : 'Cantine · toutes vos agences',
          bas: Wrap(spacing: 6, children: [
            for (final p in PeriodeStats.values)
              ChoiceChip(
                key: Key('periode-${p.name}'),
                label: Text(switch (p) {
                  PeriodeStats.mois => 'Ce mois',
                  PeriodeStats.precedent => 'Mois précédent',
                  PeriodeStats.trimestre => '3 mois',
                }),
                selected: _periode == p,
                onSelected: _chargement
                    ? null
                    : (_) {
                        setState(() => _periode = p);
                        _charger();
                      },
              ),
          ]),
        ),
        if (_chargement && d != null)
          const LinearProgressIndicator(minHeight: 2),
        Expanded(child: corps),
      ]),
    );
  }

  List<Widget> _contenu(DonneesStats d) {
    final k = _m(d.resume['kpis']);
    final ik = _m(d.indicateurs['kpis']);
    final mt = _m(d.indicateurs['montants']);
    final de = _m(d.complements['desserts']);
    final pa = _m(d.complements['participation']);
    final af = _m(d.complements['affluence']);
    final pointe = _m(af['pointe']);
    final tuiles = <(String, String, String, IconData)>[
      (
        'Repas commandés',
        _n(ik['nb_repas']),
        '${_n(ik['nb_supplements'])} desserts',
        Icons.restaurant_rounded
      ),
      if (!widget.prestataire) ...[
        (
          'Taux de retrait',
          _pct(k['taux_retrait']),
          '${_n(k['non_retires'])} non retirés',
          Icons.check_circle_outline_rounded
        ),
        (
          'Facturé aux employés',
          _f(mt['total_employes']),
          'repas des employés',
          Icons.person_outline_rounded
        ),
      ],
      (
        widget.prestataire ? 'Montant dû' : 'Dû aux prestataires',
        _f(mt['total_prestataires']),
        'repas et desserts',
        Icons.storefront_outlined
      ),
      if (!widget.prestataire)
        (
          'Participation',
          _pct(pa['taux_participation']),
          '${_n(pa['commandeurs'])} / ${_n(pa['effectif'])} employés',
          Icons.groups_outlined
        ),
      (
        'Heure de pointe',
        pointe['tranche']?.toString() ?? '—',
        '${_n(af['nb_retraits'])} retraits',
        Icons.schedule_rounded
      ),
    ];
    return [
      GridView.count(
        crossAxisCount: 2,
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        mainAxisSpacing: 10,
        crossAxisSpacing: 10,
        childAspectRatio: 1.55,
        children: [for (final t in tuiles) _Tuile(t.$1, t.$2, t.$3, t.$4)],
      ),
      const SizedBox(height: 14),
      _titre('Montants par mois'),
      _montantsMois(_l(mt['par_mois'])),
      const SizedBox(height: 14),
      _titre('Plats les plus commandés'),
      _barres(
          _l(d.indicateurs['par_plat']).take(6).toList(),
          'plat',
          'commandes',
          (p) => '${_n(p['commandes'])} · ${_pct(p['popularite'])}'),
      if (_l(de['par_dessert']).isNotEmpty) ...[
        const SizedBox(height: 14),
        _titre(
            'Desserts · ${_pct(de['part_avec_dessert'])} des repas avec dessert'),
        _barres(_l(de['par_dessert']).take(5).toList(), 'plat', 'choisis',
            (p) => '${_n(p['choisis'])} · ${_pct(p['part'])}'),
      ],
      if (!widget.prestataire && _l(pa['par_agence']).isNotEmpty) ...[
        const SizedBox(height: 14),
        _titre('Participation par agence'),
        _barres(_l(pa['par_agence']), 'agence', 'taux_participation',
            (p) => '${_pct(p['taux_participation'])} · ${_n(p['repas'])} repas',
            max: 100),
      ],
    ];
  }

  Widget _titre(String t) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Text(t,
            style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
      );

  Widget _barres(List<Map<String, dynamic>> lignes, String libelle,
      String valeur, String Function(Map<String, dynamic>) texte,
      {num? max}) {
    if (lignes.isEmpty) {
      return const CartePresta(child: Text('Aucune donnée sur la période'));
    }
    final plafond = max ??
        lignes
            .map((l) => (l[valeur] as num?) ?? 0)
            .fold<num>(1, (a, b) => b > a ? b : a);
    return CartePresta(
      child: Column(children: [
        for (final l in lignes)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 5),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(
                    child: Text('${l[libelle] ?? ''}',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                            fontWeight: FontWeight.w600, fontSize: 13))),
                Text(texte(l),
                    style: const TextStyle(
                        fontSize: 12, color: AppColors.lightTextSecondary)),
              ]),
              const SizedBox(height: 4),
              ClipRRect(
                borderRadius: BorderRadius.circular(99),
                child: LinearProgressIndicator(
                  value: (((l[valeur] as num?) ?? 0) / plafond)
                      .clamp(0, 1)
                      .toDouble(),
                  minHeight: 7,
                  backgroundColor: AppColors.lightBorder,
                  color: AppColors.accentDark,
                ),
              ),
            ]),
          ),
      ]),
    );
  }

  Widget _montantsMois(List<Map<String, dynamic>> mois) {
    if (mois.isEmpty) {
      return const CartePresta(child: Text('Aucun montant sur la période'));
    }
    final emp = !widget.prestataire;
    double v(dynamic x) => ((x ?? 0) as num).toDouble();
    final maxY = mois
        .map((m) => [v(m['prestataires']), if (emp) v(m['employes'])])
        .expand((e) => e)
        .fold<double>(1, (a, b) => b > a ? b : a);
    return CartePresta(
      child: Column(children: [
        SizedBox(
          height: 170,
          child: BarChart(BarChartData(
            maxY: maxY * 1.15,
            gridData: const FlGridData(show: false),
            borderData: FlBorderData(show: false),
            titlesData: FlTitlesData(
              leftTitles:
                  const AxisTitles(sideTitles: SideTitles(showTitles: false)),
              rightTitles:
                  const AxisTitles(sideTitles: SideTitles(showTitles: false)),
              topTitles:
                  const AxisTitles(sideTitles: SideTitles(showTitles: false)),
              bottomTitles: AxisTitles(
                sideTitles: SideTitles(
                  showTitles: true,
                  getTitlesWidget: (x, _) => Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text('${mois[x.toInt()]['court'] ?? ''}',
                        style: const TextStyle(fontSize: 10)),
                  ),
                ),
              ),
            ),
            barGroups: [
              for (var i = 0; i < mois.length; i++)
                BarChartGroupData(x: i, barsSpace: 3, barRods: [
                  if (emp)
                    BarChartRodData(
                        toY: v(mois[i]['employes']),
                        color: AppColors.primary,
                        width: 12,
                        borderRadius: BorderRadius.circular(3)),
                  BarChartRodData(
                      toY: v(mois[i]['prestataires']),
                      color: AppColors.accentDark,
                      width: 12,
                      borderRadius: BorderRadius.circular(3)),
                ]),
            ],
          )),
        ),
        const SizedBox(height: 6),
        for (final m in mois)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 2),
            child: Row(children: [
              Expanded(
                  child: Text('${m['libelle'] ?? ''}',
                      style: const TextStyle(fontSize: 12.5))),
              if (emp)
                Text(_f(m['employes']),
                    style: const TextStyle(
                        fontSize: 12.5, color: AppColors.primary)),
              if (emp) const SizedBox(width: 12),
              Text(_f(m['prestataires']),
                  style: const TextStyle(
                      fontSize: 12.5,
                      fontWeight: FontWeight.w700,
                      color: AppColors.accentDark)),
            ]),
          ),
        if (emp)
          const Padding(
            padding: EdgeInsets.only(top: 6),
            child: Text('■ facturé aux employés   ■ dû aux prestataires',
                style: TextStyle(
                    fontSize: 11, color: AppColors.lightTextSecondary)),
          ),
      ]),
    );
  }
}

class _Tuile extends StatelessWidget {
  final String libelle, valeur, note;
  final IconData icone;
  const _Tuile(this.libelle, this.valeur, this.note, this.icone);

  @override
  Widget build(BuildContext context) {
    return CartePresta(
      padding: const EdgeInsets.all(12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(icone, size: 16, color: AppColors.lightTextSecondary),
          const SizedBox(width: 6),
          Expanded(
              child: Text(libelle,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                      fontSize: 11.5, color: AppColors.lightTextSecondary))),
        ]),
        const Spacer(),
        FittedBox(
          fit: BoxFit.scaleDown,
          alignment: Alignment.centerLeft,
          child: Text(valeur,
              style:
                  const TextStyle(fontSize: 19, fontWeight: FontWeight.w800)),
        ),
        Text(note,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
                fontSize: 11, color: AppColors.lightTextSecondary)),
      ]),
    );
  }
}
