// lib/features/accueil/accueil_screen.dart
//
// Accueil de synthèse (même API que le web) : phrase de synthèse, 4 indicateurs,
// actions rapides, « À faire » (tout ce qui attend une action, les retards
// d'abord), listes de la vue choisie et notifications. Les accès aux modules
// sont dans la barre du bas.

import 'package:flutter/material.dart';
import '../../core/api/api_client.dart';
import '../../core/services/accueil_service.dart';
import '../../core/widgets/common_widgets.dart';
import '../../core/widgets/remix.dart';
import '../../shared/theme/app_theme.dart';
import '../demandes/commun.dart';
import '../demandes/demande_detail_screen.dart';
import '../demandes/mes_demandes_screen.dart';
import '../demandes/nouvelle_demande_screen.dart';
import '../notifications/notifications_screen.dart';

const _ambre = Color(0xFFA15C07);

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
      // « /demandes?statut=… » ou « ?famille=mission » : liste filtrée ; « /demandes » : onglet Demandes
      final params = Uri.tryParse(lien!)?.queryParameters ?? const {};
      final statut = params['statut'] ?? '';
      final missions = params['famille'] == 'mission';
      if (statut.isNotEmpty || missions) {
        _ouvrir(MesDemandesScreen(statutInitial: statut, missionsSeulement: missions));
      } else {
        widget.onOnglet?.call(1);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final d = _donnees;
    final profils = List<Map>.from(d?['profils'] as List? ?? []);
    return Scaffold(
      body: Column(children: [
        EnTeteMarine(
          debut: Image.asset('assets/images/ubipharm-monogramme.png', height: 26, semanticLabel: 'UbiPharm'),
          titre: d == null ? 'Accueil' : 'Bonjour ${d['prenom']}',
          sousTitre: d?['resume'] as String?,
          actions: [
            EnTeteBouton(
                icone: Remix.notification3,
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
    final actions = List<Map>.from(d['actions_rapides'] as List? ?? []);
    final aFaire = List<Map>.from(d['a_faire'] as List? ?? []);
    final listes = List<Map>.from(d['listes'] as List? ?? []);
    final notifications = List<Map>.from(d['notifications'] as List? ?? []);
    return ListView(padding: const EdgeInsets.fromLTRB(14, 14, 14, 28), children: [
      LayoutBuilder(builder: (context, c) {
        final largeur = (c.maxWidth - 10) / 2;
        return Wrap(spacing: 10, runSpacing: 10, children: [
          for (final k in kpis) SizedBox(width: largeur, child: _Kpi(k, devise, onTap: () => _ouvrirLien(k['lien'] as String?))),
        ]);
      }),
      const SizedBox(height: 12),

      // Actions rapides : 4 boutons de même largeur, entièrement visibles
      Row(children: [
        for (var i = 0; i < actions.length; i++) ...[
          if (i > 0) const SizedBox(width: 8),
          Expanded(
            child: _ActionRapide(
              libelle: '${actions[i]['libelle']}',
              icone: Remix.deClasse(actions[i]['icone'] as String?) ?? Remix.addCircle,
              onTap: () => _ouvrir(NouvelleDemandeScreen(codeType: actions[i]['code'] as String?)),
            ),
          ),
        ],
      ]),

      _Titre('À faire', compte: (d['a_faire_total'] as int?) ?? aFaire.length),
      if (aFaire.isEmpty)
        CarteListe(lignes: const [
          ListTile(
            leading: Icon(Remix.checkboxCircle, color: AppColors.accentDark),
            title: Text('Rien ne vous attend : tout est à jour.', style: TextStyle(fontSize: 13.5)),
          ),
        ])
      else
        CarteListe(
          bordure: const Color(0xFFF1D7A8),
          lignes: [for (final e in aFaire.take(5)) _LigneAFaire(e, devise, onTap: () => _ouvrir(DemandeDetailScreen(id: e['id'] as int)))],
        ),

      for (final l in listes) ...[
        _Titre('${l['titre']}', lien: l['lien_tout'] == null ? null : () => _ouvrirLien(l['lien_tout'] as String?)),
        CarteListe(lignes: [
          if ((l['lignes'] as List? ?? []).isEmpty)
            ListTile(dense: true, title: Text('${l['vide'] ?? 'Rien à signaler.'}', style: const TextStyle(fontSize: 13))),
          // Les 2 plus récentes ; « Tout voir » ouvre la liste complète
          for (final ligne in List<Map>.from(l['lignes'] as List? ?? []).take(2))
            _LigneDemande(ligne, devise, avecDemandeur: d['profil'] != 'collaborateur',
                onTap: () => _ouvrir(DemandeDetailScreen(id: ligne['id'] as int))),
        ]),
      ],

      _Titre('Notifications', lien: () => _ouvrir(const NotificationsScreen())),
      CarteListe(lignes: [
        if (notifications.isEmpty) const ListTile(dense: true, title: Text('Aucune notification.')),
        for (final n in notifications.take(3))
          InkWell(
            onTap: () {
              accueilService.lire(n['id'] as int).catchError((_) {});
              _ouvrirLien(n['lien'] as String?);
            },
            child: Padding(
              padding: const EdgeInsets.fromLTRB(14, 11, 14, 11),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Container(
                  width: 7, height: 7, margin: const EdgeInsets.only(top: 6, right: 10),
                  decoration: BoxDecoration(
                      shape: BoxShape.circle, color: n['lue'] == true ? const Color(0xFFCBD3DC) : AppColors.accent),
                ),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('${n['titre']}', style: TextStyle(fontSize: 13, fontWeight: n['lue'] == true ? FontWeight.w400 : FontWeight.w600)),
                    Text(ilYA(n['creee_le']), style: Theme.of(context).textTheme.bodySmall),
                  ]),
                ),
              ]),
            ),
          ),
      ]),
    ]);
  }
}

/// « il y a 20 min », « il y a 3 h », « hier », « il y a 4 jours »
String ilYA(dynamic iso) {
  final d = DateTime.tryParse('${iso ?? ''}');
  if (d == null) return '';
  final min = DateTime.now().difference(d).inMinutes;
  if (min < 60) return min <= 1 ? "à l'instant" : 'il y a $min min';
  final h = min ~/ 60;
  if (h < 24) return 'il y a $h h';
  final j = h ~/ 24;
  return j == 1 ? 'hier' : 'il y a $j jours';
}

class _Titre extends StatelessWidget {
  final String texte;
  final int? compte;
  final VoidCallback? lien;
  const _Titre(this.texte, {this.compte, this.lien});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 18, 0, 8),
        child: Row(children: [
          Semantics(header: true, child: Text(texte, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600))),
          if (compte != null && compte! > 0) ...[
            const SizedBox(width: 6),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 1),
              decoration: BoxDecoration(color: AppColors.primary, borderRadius: BorderRadius.circular(9)),
              child: Text('$compte', style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w700)),
            ),
          ],
          const Spacer(),
          if (lien != null)
            TextButton(
              onPressed: lien,
              style: TextButton.styleFrom(foregroundColor: const Color(0xFF1F9D5C), visualDensity: VisualDensity.compact),
              child: const Text('Tout voir'),
            ),
        ]),
      );
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

class _Kpi extends StatelessWidget {
  final Map k;
  final String devise;
  final VoidCallback? onTap;
  const _Kpi(this.k, this.devise, {this.onTap});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final attention = k['ton'] == 'attention' || k['ton'] == 'alerte';
    final couleurValeur = k['ton'] == 'alerte'
        ? AppColors.error
        : attention
            ? _ambre
            : (isDark ? Colors.white : AppColors.primary);
    final valeur = montant(k['valeur']);
    return Material(
      color: isDark ? AppColors.darkCard : AppColors.lightCard,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(color: attention ? const Color(0xFFF1D7A8) : (isDark ? AppColors.darkBorder : AppColors.lightBorder)),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: k['lien'] == null ? null : onTap,
        child: Container(
          decoration: attention
              ? const BoxDecoration(border: Border(left: BorderSide(color: Color(0xFFE9A23B), width: 3)))
              : null,
          padding: const EdgeInsets.fromLTRB(13, 12, 13, 12),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${k['libelle']}', maxLines: 1, overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(fontWeight: FontWeight.w500)),
            const SizedBox(height: 2),
            FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerLeft,
              child: Text.rich(TextSpan(children: [
                TextSpan(text: valeur, style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: couleurValeur)),
                if (k['format'] == 'montant')
                  TextSpan(text: ' $devise', style: Theme.of(context).textTheme.bodySmall?.copyWith(fontWeight: FontWeight.w600)),
              ])),
            ),
            if ((k['sous_titre'] as String? ?? '').isNotEmpty)
              Text('${k['sous_titre']}', maxLines: 2, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.bodySmall),
          ]),
        ),
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
    return Material(
      color: isDark ? AppColors.darkCard : AppColors.lightCard,
      shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: isDark ? AppColors.darkBorder : AppColors.lightBorder)),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 4),
          child: Column(children: [
            Icon(icone, size: 20, color: const Color(0xFF1F9D5C)),
            const SizedBox(height: 4),
            // Deux lignes au plus, sans jamais couper un mot (« Remboursement » se réduit)
            SizedBox(
              height: 30,
              child: Center(
                child: libelle.contains(' ')
                    ? Text(libelle, textAlign: TextAlign.center, maxLines: 2, overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, height: 1.25))
                    : FittedBox(
                        fit: BoxFit.scaleDown,
                        child: Text(libelle, maxLines: 1, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600)),
                      ),
              ),
            ),
          ]),
        ),
      ),
    );
  }
}

class _LigneAFaire extends StatelessWidget {
  final Map e;
  final String devise;
  final VoidCallback onTap;
  const _LigneAFaire(this.e, this.devise, {required this.onTap});

  @override
  Widget build(BuildContext context) {
    final principal = ['a_payer', 'a_cloturer', 'a_corriger'].contains(e['motif']);
    final details = [e['reference'], if (e['info'] != null && '${e['info']}'.isNotEmpty) e['info']].join(' · ');
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          IconeTypeDemande(e['type_code'] as String?, taille: 36),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${e['objet']}', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14, height: 1.3)),
              const SizedBox(height: 2),
              Text(details, style: Theme.of(context).textTheme.bodySmall),
              if (e['retard'] == true)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: PastilleStatut(label: 'En retard', ton: TonPastille.rouge, icone: Remix.alarmWarning),
                ),
              const SizedBox(height: 8),
              Row(children: [
                SizedBox(
                  height: 32,
                  child: principal
                      ? FilledButton(
                          onPressed: onTap,
                          style: FilledButton.styleFrom(
                              backgroundColor: AppColors.accent, foregroundColor: AppColors.primary,
                              padding: const EdgeInsets.symmetric(horizontal: 12), elevation: 0,
                              textStyle: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600)),
                          child: Text('${e['action']}'),
                        )
                      : OutlinedButton(
                          onPressed: onTap,
                          style: OutlinedButton.styleFrom(
                              foregroundColor: AppColors.primary, padding: const EdgeInsets.symmetric(horizontal: 12),
                              textStyle: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600)),
                          child: Text('${e['action']}'),
                        ),
                ),
                const Spacer(),
                if (e['montant'] != null)
                  Text(montant(e['montant'], devise), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
              ]),
            ]),
          ),
        ]),
      ),
    );
  }
}

class _LigneDemande extends StatelessWidget {
  final Map l;
  final String devise;
  final bool avecDemandeur;
  final VoidCallback onTap;
  const _LigneDemande(this.l, this.devise, {required this.onTap, this.avecDemandeur = false});

  @override
  Widget build(BuildContext context) {
    final details = [
      l['reference'],
      if (avecDemandeur && l['demandeur'] != null) l['demandeur'],
      if ((l['info'] as String? ?? '').isNotEmpty) l['info'],
    ].join(' · ');
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          IconeTypeDemande(l['type_code'] as String?, taille: 36),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${l['objet']}', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14, height: 1.3)),
              const SizedBox(height: 2),
              Text(details, style: Theme.of(context).textTheme.bodySmall),
              const SizedBox(height: 7),
              Row(children: [
                if (l['statut'] != null) PastilleDemande(l['statut'] as String),
                const Spacer(),
                if (l['montant'] != null)
                  Text(montant(l['montant'], devise), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
              ]),
            ]),
          ),
        ]),
      ),
    );
  }
}
