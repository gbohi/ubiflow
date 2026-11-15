// lib/features/menu/desserts.dart
//
// Suppléments (desserts…) : jamais commandés seuls.
//  - DessertsDuJour : vignettes d'information sous les plats du jour ; un
//    appui ouvre la fiche en lecture (photo, description, allergènes) ;
//  - ChoixDessertSheet : après « Réserver ce plat », le plat choisi est
//    rappelé, puis le dessert (ou « Sans dessert ») ;
//  - LigneDessert / ChangerDessertSheet : dans « Mes commandes ».

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api/api_client.dart' show messageErreurApi;
import '../../core/services/cantine_service.dart';
import '../../core/widgets/common_widgets.dart';
import '../../shared/models/models.dart';
import '../../shared/models/parcours_models.dart';
import '../../shared/providers/app_provider.dart';
import '../../shared/theme/app_theme.dart';

const kCouleurDessert = Color(0xFFC2417A);

class PastilleInclus extends StatelessWidget {
  final String texte;
  const PastilleInclus({super.key, this.texte = 'inclus'});

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(
            color: AppColors.success.withOpacity(0.16),
            borderRadius: BorderRadius.circular(20)),
        child: Text(texte,
            style: const TextStyle(
                fontSize: 10.5,
                fontWeight: FontWeight.w700,
                color: Color(0xFF1C8A4B))),
      );
}

/// Desserts du jour : information (on les choisit en réservant un plat)
class DessertsDuJour extends StatelessWidget {
  final List<SupplementJour> desserts;
  const DessertsDuJour({super.key, required this.desserts});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final gris =
        isDark ? AppColors.darkTextSecondary : AppColors.lightTextSecondary;
    final famille = desserts.first.famille.isEmpty
        ? 'Desserts'
        : '${desserts.first.famille}s';
    return Container(
      key: const Key('desserts-du-jour'),
      padding: const EdgeInsets.only(top: 12),
      decoration: BoxDecoration(
          border: Border(top: BorderSide(color: gris.withOpacity(0.25)))),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
            child: Text('$famille du jour',
                style:
                    const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
          ),
          PastilleInclus(
              texte: desserts.every((d) => d.inclus)
                  ? 'inclus avec votre plat'
                  : 'avec votre plat'),
        ]),
        const SizedBox(height: 10),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(children: [
            for (final d in desserts)
              Padding(
                padding: const EdgeInsets.only(right: 10),
                child: InkWell(
                  key: Key('dessert-${d.id}'),
                  borderRadius: BorderRadius.circular(12),
                  onTap: () => FicheDessertSheet.show(context, d),
                  child: SizedBox(
                    width: 96,
                    child: Column(children: [
                      VignettePlat(
                          url: d.photoUrl,
                          taille: 64,
                          rayon: 12,
                          icone: Icons.cake_outlined),
                      const SizedBox(height: 4),
                      Text(d.nom,
                          maxLines: 2,
                          textAlign: TextAlign.center,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 11.5)),
                    ]),
                  ),
                ),
              ),
          ]),
        ),
        const SizedBox(height: 6),
        Row(children: [
          Icon(Icons.info_outline_rounded, size: 15, color: gris),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
                'Réservez un plat : vous choisirez votre dessert à l\'étape suivante.',
                style: TextStyle(fontSize: 11.5, color: gris)),
          ),
        ]),
      ]),
    );
  }
}

/// Fiche d'un dessert en lecture seule
class FicheDessertSheet extends StatelessWidget {
  final SupplementJour dessert;
  const FicheDessertSheet({super.key, required this.dessert});

  static Future<void> show(BuildContext context, SupplementJour d) =>
      showModalBottomSheet<void>(
        context: context,
        useRootNavigator: true,
        isScrollControlled: true,
        useSafeArea: true,
        showDragHandle: true,
        builder: (_) => FicheDessertSheet(dessert: d),
      );

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final gris =
        isDark ? AppColors.darkTextSecondary : AppColors.lightTextSecondary;
    final d = dessert;
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 0, 18, 18),
      child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(16),
              child: d.photoUrl == null
                  ? Container(
                      height: 150,
                      color: kCouleurDessert.withOpacity(0.10),
                      child: const Icon(Icons.cake_outlined,
                          size: 54, color: kCouleurDessert))
                  : Image.network(d.photoUrl!,
                      height: 170,
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => Container(
                          height: 150,
                          color: kCouleurDessert.withOpacity(0.10),
                          child: const Icon(Icons.cake_outlined,
                              size: 54, color: kCouleurDessert))),
            ),
            const SizedBox(height: 12),
            Row(children: [
              Expanded(
                child: Text(d.nom,
                    style: const TextStyle(
                        fontSize: 18, fontWeight: FontWeight.w700)),
              ),
              PastilleInclus(
                  texte: d.inclus
                      ? '${d.famille.isEmpty ? 'Dessert' : d.famille} · inclus'
                      : d.famille),
            ]),
            if (d.description.trim().isNotEmpty) ...[
              const SizedBox(height: 6),
              Text(d.description, style: TextStyle(color: gris, fontSize: 13)),
            ],
            const SizedBox(height: 10),
            Text('ALLERGÈNES',
                style: TextStyle(
                    fontSize: 11, fontWeight: FontWeight.w700, color: gris)),
            const SizedBox(height: 2),
            Text(d.mentions.isEmpty ? 'Aucun déclaré' : d.mentions.join(', '),
                style: TextStyle(color: gris, fontSize: 13)),
            const SizedBox(height: 12),
            BandeauInfo(
              icone: Icons.info_outline_rounded,
              ton: TonPastille.gris,
              texte: 'Ce dessert se choisit en réservant un plat du jour.',
            ),
            const SizedBox(height: 12),
            OutlinedButton(
              key: const Key('fermer-fiche-dessert'),
              onPressed: () => Navigator.of(context).pop(),
              style: OutlinedButton.styleFrom(
                  minimumSize: const Size.fromHeight(46)),
              child: const Text('Fermer'),
            ),
          ]),
    );
  }
}

/// Choix du dessert après le plat : renvoie l'id du dessert, 0 pour « Sans
/// dessert », null si la feuille est fermée (réservation abandonnée).
class ChoixDessertSheet extends StatefulWidget {
  final String platNom;
  final String platDetail;
  final List<SupplementJour> desserts;
  const ChoixDessertSheet(
      {super.key,
      required this.platNom,
      this.platDetail = '',
      required this.desserts});

  static Future<int?> show(BuildContext context,
          {required String platNom,
          String platDetail = '',
          required List<SupplementJour> desserts}) =>
      showModalBottomSheet<int>(
        context: context,
        useRootNavigator: true,
        isScrollControlled: true,
        useSafeArea: true,
        showDragHandle: true,
        builder: (_) => ChoixDessertSheet(
            platNom: platNom, platDetail: platDetail, desserts: desserts),
      );

  @override
  State<ChoixDessertSheet> createState() => _ChoixDessertSheetState();
}

class _ChoixDessertSheetState extends State<ChoixDessertSheet> {
  int _choix = 0;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final gris =
        isDark ? AppColors.darkTextSecondary : AppColors.lightTextSecondary;
    final tousInclus = widget.desserts.every((d) => d.inclus);
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(18, 0, 18, 18),
        child:
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          _Etape(numero: null, titre: 'Votre plat'),
          const SizedBox(height: 6),
          Container(
            key: const Key('plat-choisi'),
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: AppColors.success.withOpacity(0.08),
              border: Border.all(color: AppColors.success, width: 2),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Row(children: [
              const Icon(Icons.restaurant_rounded, color: Color(0xFFD8901A)),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(widget.platNom,
                          style: const TextStyle(
                              fontWeight: FontWeight.w700, fontSize: 14)),
                      if (widget.platDetail.isNotEmpty)
                        Text(widget.platDetail,
                            style: TextStyle(fontSize: 12, color: gris)),
                    ]),
              ),
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('Changer'),
              ),
            ]),
          ),
          const SizedBox(height: 14),
          Row(children: [
            const Expanded(child: _Etape(numero: 2, titre: 'Votre dessert')),
            PastilleInclus(
                texte: tousInclus ? 'inclus · 1 au choix' : '1 au choix'),
          ]),
          const SizedBox(height: 8),
          for (final d in widget.desserts)
            _OptionDessert(
              key: Key('choix-dessert-${d.id}'),
              nom: d.nom,
              photoUrl: d.photoUrl,
              detail: d.famille.isEmpty ? 'Dessert' : d.famille,
              inclus: d.inclus,
              prix: d.prix,
              choisi: _choix == d.id,
              onTap: () => setState(() => _choix = d.id),
            ),
          _OptionDessert(
            key: const Key('choix-sans-dessert'),
            nom: 'Sans dessert',
            sans: true,
            choisi: _choix == 0,
            onTap: () => setState(() => _choix = 0),
          ),
          const SizedBox(height: 10),
          BoutonVert(
            key: const Key('continuer-paiement'),
            label: 'Continuer vers le paiement',
            icone: Icons.arrow_forward_rounded,
            onPressed: () => Navigator.of(context).pop(_choix),
          ),
        ]),
      ),
    );
  }
}

class _Etape extends StatelessWidget {
  final int? numero;
  final String titre;
  const _Etape({required this.numero, required this.titre});

  @override
  Widget build(BuildContext context) => Row(children: [
        Container(
          width: 22,
          height: 22,
          alignment: Alignment.center,
          decoration: BoxDecoration(
              color: numero == null ? AppColors.success : AppColors.primary,
              shape: BoxShape.circle),
          child: numero == null
              ? const Icon(Icons.check_rounded, size: 14, color: Colors.white)
              : Text('$numero',
                  style: const TextStyle(
                      color: Colors.white,
                      fontSize: 11,
                      fontWeight: FontWeight.w700)),
        ),
        const SizedBox(width: 8),
        Flexible(
          child: Text(titre,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontWeight: FontWeight.w700)),
        ),
      ]);
}

class _OptionDessert extends StatelessWidget {
  final String nom;
  final String? photoUrl;
  final String detail;
  final bool inclus;
  final double? prix;
  final bool sans;
  final bool choisi;
  final VoidCallback onTap;
  const _OptionDessert(
      {super.key,
      required this.nom,
      this.photoUrl,
      this.detail = '',
      this.inclus = true,
      this.prix,
      this.sans = false,
      required this.choisi,
      required this.onTap});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final gris =
        isDark ? AppColors.darkTextSecondary : AppColors.lightTextSecondary;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Semantics(
        selected: choisi,
        button: true,
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.all(9),
            decoration: BoxDecoration(
              color: choisi ? AppColors.success.withOpacity(0.08) : null,
              border: Border.all(
                  color: choisi ? AppColors.success : gris.withOpacity(0.3),
                  width: choisi ? 2 : 1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(children: [
              if (sans)
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                      color: gris.withOpacity(0.12),
                      borderRadius: BorderRadius.circular(10)),
                  child: Icon(Icons.close_rounded, color: gris),
                )
              else
                VignettePlat(
                    url: photoUrl, taille: 44, icone: Icons.cake_outlined),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(nom,
                          style: const TextStyle(
                              fontWeight: FontWeight.w600, fontSize: 13.5)),
                      if (detail.isNotEmpty)
                        Text(detail,
                            style: TextStyle(fontSize: 11.5, color: gris)),
                    ]),
              ),
              if (!sans && inclus) const PastilleInclus(),
              if (!sans && !inclus && prix != null)
                Text('${prix!.round()} F',
                    style: const TextStyle(fontWeight: FontWeight.w700)),
            ]),
          ),
        ),
      ),
    );
  }
}

/// Dessert d'un repas réservé (Mes commandes)
class LigneDessert extends StatelessWidget {
  final SupplementCommande dessert;
  final String detail;
  const LigneDessert({super.key, required this.dessert, this.detail = ''});

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final gris =
        isDark ? AppColors.darkTextSecondary : AppColors.lightTextSecondary;
    return Row(children: [
      VignettePlat(
          url: dessert.platDetail?.imageUrl,
          taille: 40,
          icone: Icons.cake_outlined),
      const SizedBox(width: 10),
      Expanded(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(dessert.platDetail?.nom ?? '',
              style:
                  const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
          Text(
              [
                dessert.famille.isEmpty ? 'Dessert' : dessert.famille,
                if (detail.isNotEmpty) detail
              ].join(' · '),
              style: TextStyle(fontSize: 11.5, color: gris)),
        ]),
      ),
      if (dessert.inclus) const PastilleInclus(),
    ]);
  }
}

/// « Changer de dessert » / « Ajouter un dessert » d'un repas réservé
class ChangerDessertSheet extends StatefulWidget {
  final Commande commande;
  final CommandeService? service;
  const ChangerDessertSheet({super.key, required this.commande, this.service});

  static Future<void> show(BuildContext context, Commande c,
          {CommandeService? service}) =>
      showModalBottomSheet<void>(
        context: context,
        useRootNavigator: true,
        isScrollControlled: true,
        useSafeArea: true,
        showDragHandle: true,
        builder: (_) => ChangeNotifierProvider.value(
          value: context.read<CommandeProvider>(),
          child: ChangerDessertSheet(commande: c, service: service),
        ),
      );

  @override
  State<ChangerDessertSheet> createState() => _ChangerDessertSheetState();
}

class _ChangerDessertSheetState extends State<ChangerDessertSheet> {
  late final CommandeService _service = widget.service ?? commandeService;
  SupplementsProposes? _proposes;
  String? _erreur;
  int _choix = 0;
  bool _envoi = false;

  @override
  void initState() {
    super.initState();
    _charger();
  }

  Future<void> _charger() async {
    try {
      final p = await _service.supplementsProposes(widget.commande.id);
      if (!mounted) return;
      setState(() {
        _proposes = p;
        _choix = p.supplements.where((s) => s.choisi).firstOrNull?.id ?? 0;
      });
    } catch (e) {
      if (mounted)
        setState(
            () => _erreur = messageErreurApi(e) ?? 'Desserts indisponibles.');
    }
  }

  Future<void> _enregistrer() async {
    final p = _proposes;
    if (p == null || _envoi) return;
    setState(() => _envoi = true);
    final prov = context.read<CommandeProvider>();
    try {
      final famille = p.supplements.firstOrNull?.familleId ??
          widget.commande.supplements.firstOrNull?.familleId;
      final c = _choix == 0
          ? await _service.retirerSupplement(widget.commande.id, famille)
          : await _service.choisirSupplement(widget.commande.id, _choix);
      prov.remplacerCommande(c);
      if (mounted) Navigator.of(context).pop();
    } catch (e) {
      if (mounted) {
        setState(() {
          _envoi = false;
          _erreur =
              messageErreurApi(e) ?? "Le dessert n'a pas pu être modifié.";
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = _proposes;
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(18, 0, 18, 18),
        child:
            Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('Votre dessert',
              style: Theme.of(context)
                  .textTheme
                  .titleMedium
                  ?.copyWith(fontWeight: FontWeight.w700)),
          Text('Avec votre ${widget.commande.platDetail?.nom ?? 'repas'}',
              style: const TextStyle(fontSize: 12.5)),
          const SizedBox(height: 12),
          if (_erreur != null)
            BandeauInfo(
                icone: Icons.error_outline_rounded,
                ton: TonPastille.rouge,
                texte: _erreur!),
          if (p == null && _erreur == null)
            const Padding(
                padding: EdgeInsets.all(24),
                child: Center(child: CircularProgressIndicator())),
          if (p != null) ...[
            for (final s in p.supplements)
              _OptionDessert(
                key: Key('changer-dessert-${s.id}'),
                nom: s.nom,
                photoUrl: s.photoUrl,
                detail: s.famille,
                inclus: s.inclus,
                choisi: _choix == s.id,
                onTap: () => setState(() => _choix = s.id),
              ),
            _OptionDessert(
              key: const Key('changer-sans-dessert'),
              nom: 'Sans dessert',
              sans: true,
              choisi: _choix == 0,
              onTap: () => setState(() => _choix = 0),
            ),
            const SizedBox(height: 8),
            BoutonVert(
              key: const Key('enregistrer-dessert'),
              label: 'Enregistrer',
              icone: Icons.check_rounded,
              onPressed: p.modifiable && !_envoi ? _enregistrer : null,
            ),
            if (!p.modifiable)
              const Padding(
                padding: EdgeInsets.only(top: 8),
                child: Text(
                    "L'heure limite de commande est passée : le dessert ne peut plus être modifié.",
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 12)),
              ),
          ],
        ]),
      ),
    );
  }
}
