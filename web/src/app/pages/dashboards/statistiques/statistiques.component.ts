// src/app/pages/dashboards/statistiques/statistiques.component.ts
//
// Statistiques : huit tableaux thématiques (vue globale, missions, finances, paiements,
// départements, circuits, remboursements et frais complémentaires, réceptions clients).
// Chaque tableau : indicateurs en tête, trois graphiques au plus, puis le tableau détaillé
// (valeurs exactes, clic = ouverture de la demande). Filtres communs, période annuelle par défaut.
// Exports Excel (une feuille par bloc) et PDF (graphiques et tableaux).

import { Component, OnInit, QueryList, ViewChildren, inject } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ToastrService } from 'ngx-toastr';
import { firstValueFrom, forkJoin } from 'rxjs';
import {
  Cellule, chargerLogoPdf, enregistrerPdf, exporterExcel, imagePdf, nomFichier, nouveauPdf, placePdf, tableauPdf, titrePdf,
} from 'src/app/core/helpers/exports';
import { BaremesService } from 'src/app/core/services/baremes/baremes.service';
import { DemandesService, TypeDemande } from 'src/app/core/services/demandes/demandes.service';
import { OrganisationService, messageErreur } from 'src/app/core/services/organisation/organisation.service';
import { Indicateur, PilotageService, Profil, Section, Statistiques } from 'src/app/core/services/pilotage/pilotage.service';
import { GrapheAnneauComponent } from '../graphes/graphe-anneau.component';
import { GrapheBarresComponent } from '../graphes/graphe-barres.component';
import { GrapheCarteComponent } from '../graphes/graphe-carte.component';
import { GrapheColonnesComponent } from '../graphes/graphe-colonnes.component';
import { GrapheCourbeComponent } from '../graphes/graphe-courbe.component';
import { GrapheEmpileComponent } from '../graphes/graphe-empile.component';
import { GrapheEntonnoirComponent } from '../graphes/graphe-entonnoir.component';
import { complet } from '../graphes/format';
import { svgVersPng } from '../graphes/svg-png';

const STATUTS = [
  ['en_validation', 'En validation'], ['a_corriger', 'À corriger'], ['approuvee', 'Approuvée'],
  ['en_attente_cloture', 'En attente de clôture'], ['cloturee', 'Clôturée'], ['rejetee', 'Rejetée'], ['annulee', 'Annulée'],
];

@Component({
  selector: 'app-statistiques',
  templateUrl: './statistiques.component.html',
})
export class StatistiquesComponent implements OnInit {
  private readonly service = inject(PilotageService);
  private readonly demandes = inject(DemandesService);
  private readonly organisation = inject(OrganisationService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastrService);
  private readonly baremes = inject(BaremesService);

  @ViewChildren(GrapheBarresComponent) private gBarres!: QueryList<GrapheBarresComponent>;
  @ViewChildren(GrapheColonnesComponent) private gColonnes!: QueryList<GrapheColonnesComponent>;
  @ViewChildren(GrapheCourbeComponent) private gCourbes!: QueryList<GrapheCourbeComponent>;
  @ViewChildren(GrapheAnneauComponent) private gAnneaux!: QueryList<GrapheAnneauComponent>;
  @ViewChildren(GrapheEmpileComponent) private gEmpiles!: QueryList<GrapheEmpileComponent>;
  @ViewChildren(GrapheEntonnoirComponent) private gEntonnoirs!: QueryList<GrapheEntonnoirComponent>;
  @ViewChildren(GrapheCarteComponent) private gCartes!: QueryList<GrapheCarteComponent>;

  readonly statuts = STATUTS;
  themes: Profil[] = [];
  theme = '';
  stats: Statistiques | null = null;
  chargement = false;
  exportEnCours = false;
  vueTableau: Record<string, boolean> = {};
  types: TypeDemande[] = [];
  departements: any[] = [];
  agences: any[] = [];
  categories: any[] = [];
  collaborateurs: { id: number; libelle: string }[] = [];
  filtres: Record<string, any> = this.periode('annee');
  preset = 'annee';

  ngOnInit(): void {
    forkJoin({ th: this.service.themesStatistiques(), t: this.demandes.types(true) }).subscribe({
      next: ({ th, t }) => {
        this.themes = th;
        this.types = t;
        const demande = this.route.snapshot.queryParamMap.get('theme');
        this.choisir(th.find(x => x.code === demande)?.code ?? th[0]?.code);
      },
      error: e => this.toast.error(messageErreur(e)),
    });
    this.organisation.departementsTous().subscribe(d => this.departements = d ?? []);
    this.organisation.agencesToutes().subscribe(a => this.agences = a ?? []);
    this.organisation.categoriesToutes().subscribe(c => this.categories = c ?? []);
    this.organisation.annuaire().subscribe(u => this.collaborateurs = (u ?? []).map(x => ({ id: x.id, libelle: x.libelle })));
  }

  choisir(code: string): void {
    if (!code) return;
    this.theme = code;
    this.vueTableau = {};
    this.router.navigate([], { queryParams: { theme: code }, replaceUrl: true });
    this.charger();
  }

  periode(cle: string): Record<string, any> {
    const auj = new Date(), iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    const debut = { mois: new Date(auj.getFullYear(), auj.getMonth(), 1), trimestre: new Date(auj.getFullYear(), Math.floor(auj.getMonth() / 3) * 3, 1),
                    annee: new Date(auj.getFullYear(), 0, 1), douze: new Date(auj.getFullYear(), auj.getMonth() - 11, 1) }[cle] ?? new Date(auj.getFullYear(), 0, 1);
    return { ...(this.filtres ?? {}), du: iso(debut), au: iso(auj) };
  }

  appliquerPeriode(cle: string): void { this.preset = cle; this.filtres = this.periode(cle); this.charger(); }

  charger(): void {
    if (!this.theme) return;
    this.chargement = true;
    this.service.statistiques(this.theme, this.filtres).subscribe({
      next: s => { this.stats = s; this.chargement = false; },
      error: e => { this.chargement = false; this.toast.error(messageErreur(e)); },
    });
  }

  get filtresActifs(): boolean {
    const f = this.filtres;
    return this.preset !== 'annee' || ['type_demande', 'statut', 'departement', 'agence', 'categorie', 'demandeur'].some(k => f[k]);
  }

  reinitialiser(): void { this.filtres = this.periode('annee'); this.preset = 'annee'; this.charger(); }

  get themeCourant(): Profil | undefined { return this.themes.find(t => t.code === this.theme); }

  // ── Mise en page : graphiques deux par ligne (le premier seul sur sa ligne s'ils sont en nombre impair),
  //    tableaux sur toute la largeur.
  pleineLargeur(i: number): boolean {
    const sections = this.stats?.sections ?? [];
    if (sections[i]?.type === 'tableau') return true;
    const graphes = sections.map((s, j) => ({ s, j })).filter(x => x.s.type !== 'tableau');
    return graphes.length % 2 === 1 && graphes[0]?.j === i;
  }

  /** Barres verticales demandées (« demandes par type ») : mêmes colonnes qu'une série mensuelle */
  enColonnes(s: Section): { donnees: any[]; series: { cle: string; libelle: string }[] } {
    return { donnees: (s.donnees ?? []).map(d => ({ libelle: d.libelle, valeurs: { v: d.valeur } })), series: [{ cle: 'v', libelle: s.titre }] };
  }

  // ── Affichage ──
  valeur(i: Indicateur): string {
    if (i.format === 'heures' || i.format === 'jours') return complet(Number(i.valeur), 1);
    return complet(Number(i.valeur));
  }
  unite(i: Indicateur): string {
    return { montant: this.stats?.devise ?? '', heures: 'h', jours: 'j', pourcentage: '%' }[i.format as string] ?? '';
  }
  cellule(c: { format: string }, v: any): string {
    if (v === null || v === undefined || v === '') return '—';
    switch (c.format) {
      case 'montant': return `${complet(Number(v))} ${this.stats?.devise ?? ''}`;
      case 'date': return new Date(String(v).length === 10 ? `${v}T00:00:00` : v).toLocaleDateString('fr-FR');
      case 'dateheure': return new Date(v).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' });
      case 'oui_non': return v ? 'Oui' : 'Non';
      case 'nombre': return complet(Number(v));
      default: return String(v);
    }
  }
  format(s: Section): string { return s.unite === 'montant' ? 'montant' : 'nombre'; }
  /** Cellule de la vue « Valeurs » d'un graphique */
  texteValeur(s: Section, c: Cellule, k: number): string {
    if (k === 0 || typeof c !== 'number') return String(c ?? '');
    if (s.unite === 'heures' || s.unite === 'jours') return complet(c, 1);
    return s.type === 'carte' ? complet(c) : this.cellule({ format: this.format(s) }, c);
  }
  vide(s: Section): boolean {
    switch (s.type) {
      case 'tableau': return !s.lignes?.length;
      case 'carte': return !s.points?.length && !s.pays?.length;
      case 'barres': case 'anneau': case 'entonnoir': return !s.donnees?.some(d => Number(d.valeur) > 0);
      default: return !s.donnees?.some(d => Object.values(d.valeurs ?? {}).some(v => Number(v) > 0));
    }
  }
  ouvrir(ligne: any): void { if (ligne?.id) this.router.navigate(['/demandes', ligne.id]); }

  get libelleFiltres(): string {
    const f = this.filtres, parts: string[] = [];
    parts.push(`du ${new Date(f['du'] + 'T00:00:00').toLocaleDateString('fr-FR')} au ${new Date(f['au'] + 'T00:00:00').toLocaleDateString('fr-FR')}`);
    const lib = (liste: any[], id: any, champ: string) => liste.find(x => String(x.id) === String(id))?.[champ];
    if (f['type_demande']) parts.push(`type : ${lib(this.types, f['type_demande'], 'libelle')}`);
    if (f['statut']) parts.push(`statut : ${STATUTS.find(s => s[0] === f['statut'])?.[1]}`);
    if (f['departement']) parts.push(`département : ${lib(this.departements, f['departement'], 'libelle_service')}`);
    if (f['agence']) parts.push(`agence : ${lib(this.agences, f['agence'], 'nom_agence')}`);
    if (f['categorie']) parts.push(`catégorie : ${lib(this.categories, f['categorie'], 'libelle')}`);
    if (f['demandeur']) parts.push(`demandeur : ${lib(this.collaborateurs, f['demandeur'], 'libelle')}`);
    return parts.join(' · ');
  }

  // ── Exports ──
  /** Valeurs d'un bloc sous forme de lignes (première ligne = en-têtes) */
  lignesSection(s: Section): Cellule[][] {
    const devise = this.stats?.devise ?? '';
    const titreValeur = s.unite === 'montant' ? `Montant (${devise})` : s.unite === 'heures' ? 'Heures' : s.unite === 'jours' ? 'Jours' : 'Nombre';
    switch (s.type) {
      case 'barres': case 'anneau': case 'entonnoir':
        return [['Libellé', titreValeur], ...(s.donnees ?? []).map(d => [d.libelle, Number(d.valeur)])];
      case 'carte':
        return [['Ville', 'Pays', 'Missions'], ...(s.points ?? []).map(p => [p.ville, p.pays, Number(p.valeur)])];
      case 'tableau': {
        const cols = s.colonnes ?? [];
        return [['N°', ...cols.map(c => c.libelle)],
                ...(s.lignes ?? []).map((l, i) => [i + 1, ...cols.map(c => ['montant', 'nombre'].includes(c.format) && l[c.cle] !== null && l[c.cle] !== undefined
                  ? Number(l[c.cle]) : this.cellule(c, l[c.cle]))])];
      }
      default: {
        const premiere = s.type === 'barres_empilees' ? 'Libellé' : 'Mois';
        return [[premiere, ...(s.series ?? []).map(x => s.unite === 'montant' ? `${x.libelle} (${devise})` : x.libelle)],
                ...(s.donnees ?? []).map(d => [d.libelle, ...(s.series ?? []).map(x => Number(d.valeurs[x.cle]) || 0)])];
      }
    }
  }

  exporterExcel(): void {
    if (!this.stats) return;
    const t = this.stats;
    const indicateurs: Cellule[][] = [[`Statistiques — ${t.titre}`], [this.libelleFiltres],
      [`Édité le ${new Date().toLocaleString('fr-FR')}`], [], ['Indicateur', 'Valeur', 'Unité'],
      ...t.indicateurs.map(i => [i.libelle, Number(i.valeur), this.unite(i)])];
    exporterExcel(nomFichier('statistiques', t.titre, t.du, t.au),
      [{ nom: 'Indicateurs', lignes: indicateurs, largeurs: [44, 18, 8] }, ...t.sections.map(s => ({ nom: s.titre, lignes: this.lignesSection(s) }))]);
  }

  async exporterPdf(): Promise<void> {
    if (!this.stats || this.exportEnCours) return;
    this.exportEnCours = true;
    try {
      const t = this.stats;
      await chargerLogoPdf((await firstValueFrom(this.baremes.parametres()).catch(() => null))?.logo);
      const p = nouveauPdf(`Statistiques — ${t.titre}`, `${this.libelleFiltres} · montants en ${t.devise} · édité le ${new Date().toLocaleString('fr-FR')}`, false);
      tableauPdf(p, ['Indicateur', 'Valeur'], t.indicateurs.map(i => [i.libelle, `${this.valeur(i)} ${this.unite(i)}`.trim()]), false, [1]);
      const svgs = new Map<string, SVGSVGElement>();
      for (const liste of [this.gBarres, this.gColonnes, this.gCourbes, this.gAnneaux, this.gEmpiles, this.gEntonnoirs, this.gCartes] as QueryList<any>[]) {
        liste.forEach(g => { if (g.svg?.nativeElement) svgs.set(g.titre, g.svg.nativeElement); });
      }
      for (const s of t.sections) {
        titrePdf(p, s.titre);
        if (this.vide(s)) { tableauPdf(p, ['Aucune donnée sur la période'], []); continue; }
        const svg = svgs.get(s.titre);
        if (svg && s.type !== 'tableau') await imagePdf(p, await svgVersPng(svg));
        const lignes = this.lignesSection(s);
        placePdf(p, 20);
        tableauPdf(p, lignes[0], lignes.slice(1).map(l => l.map(c => typeof c === 'number' ? complet(c) : c)), false,
                   lignes[0].map((_, i) => i).filter(i => lignes.slice(1).some(l => typeof l[i] === 'number') && i > 0));
      }
      enregistrerPdf(p, nomFichier('statistiques', t.titre, t.du, t.au));
    } catch (e: any) {
      this.toast.error(e?.message || "L'export a échoué.");
    } finally {
      this.exportEnCours = false;
    }
  }
}
