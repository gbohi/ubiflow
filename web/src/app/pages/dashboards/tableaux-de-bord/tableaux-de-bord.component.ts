// src/app/pages/dashboards/tableaux-de-bord/tableaux-de-bord.component.ts
//
// Tableaux de bord par profil (§14) : filtres communs, indicateurs, graphiques,
// tableaux ; exports Excel (une feuille par bloc) et PDF (graphiques et tableaux).

import { Component, OnInit, QueryList, ViewChildren, inject } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ToastrService } from 'ngx-toastr';
import { firstValueFrom, forkJoin } from 'rxjs';
import { BaremesService } from 'src/app/core/services/baremes/baremes.service';
import {
  Cellule, chargerLogoPdf, enregistrerPdf, exporterExcel, imagePdf, nomFichier, nouveauPdf, placePdf, tableauPdf, titrePdf,
} from 'src/app/core/helpers/exports';
import { DemandesService, TypeDemande } from 'src/app/core/services/demandes/demandes.service';
import { OrganisationService, messageErreur } from 'src/app/core/services/organisation/organisation.service';
import { Indicateur, PilotageService, Profil, Section, TableauDeBord } from 'src/app/core/services/pilotage/pilotage.service';
import { GrapheBarresComponent } from '../graphes/graphe-barres.component';
import { GrapheColonnesComponent } from '../graphes/graphe-colonnes.component';
import { complet } from '../graphes/format';
import { svgVersPng } from '../graphes/svg-png';

const STATUTS = [
  ['en_validation', 'En validation'], ['a_corriger', 'À corriger'], ['approuvee', 'Approuvée'],
  ['en_attente_cloture', 'En attente de clôture'], ['cloturee', 'Clôturée'], ['rejetee', 'Rejetée'], ['annulee', 'Annulée'],
];

@Component({
  selector: 'app-tableaux-de-bord',
  templateUrl: './tableaux-de-bord.component.html',
  styles: [`
    .tdb-tuiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 12px; }
    .tdb-tuile { background: #fff; border: 1px solid var(--bs-border-color); border-radius: 12px; padding: 12px 14px; display: block; color: inherit; text-decoration: none; }
    a.tdb-tuile:hover { border-color: #2a78d6; }
    .tdb-tuile small { color: #52514e; display: block; font-size: 12px; min-height: 2.4em; }
    .tdb-tuile b { font-size: 1.35rem; font-weight: 600; display: block; line-height: 1.3; }
    .tdb-tuile .tdb-u { font-size: 12px; font-weight: 500; color: #52514e; margin-left: 2px; }
    .tdb-tuile.attention { border-left: 4px solid #eda100; } .tdb-tuile.alerte { border-left: 4px solid #e34948; }
    .tdb-grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 16px; }
    .tdb-carte { background: #fff; border: 1px solid var(--bs-border-color); border-radius: 12px; padding: 14px 16px; }
    .tdb-carte.large { grid-column: 1 / -1; }
    .tdb-carte h6 { font-size: 14px; margin: 0; }
    .tdb-vide { color: #8a8984; font-size: 13px; padding: 16px 0; text-align: center; }
  `],
})
export class TableauxDeBordComponent implements OnInit {
  private readonly service = inject(PilotageService);
  private readonly demandes = inject(DemandesService);
  private readonly organisation = inject(OrganisationService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastrService);
  private readonly baremes = inject(BaremesService);

  @ViewChildren(GrapheBarresComponent) barres!: QueryList<GrapheBarresComponent>;
  @ViewChildren(GrapheColonnesComponent) colonnes!: QueryList<GrapheColonnesComponent>;

  readonly statuts = STATUTS;
  readonly complet = complet;
  profils: Profil[] = [];
  profil = '';
  tdb: TableauDeBord | null = null;
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
    forkJoin({ p: this.service.profils(), t: this.demandes.types(true) }).subscribe({
      next: ({ p, t }) => {
        this.profils = p;
        this.types = t;
        const demande = this.route.snapshot.queryParamMap.get('profil');
        this.choisir(p.find(x => x.code === demande)?.code ?? (p.length > 2 ? p[2].code : p[0]?.code));
      },
      error: e => this.toast.error(messageErreur(e)),
    });
  }

  /** Listes des filtres d'organisation : chargées seulement pour le tableau Direction */
  private listesChargees = false;
  private chargerListes(): void {
    if (this.listesChargees) return;
    this.listesChargees = true;
    this.organisation.departementsTous().subscribe(d => this.departements = d ?? []);
    this.organisation.agencesToutes().subscribe(a => this.agences = a ?? []);
    this.organisation.categoriesToutes().subscribe(c => this.categories = c ?? []);
    this.organisation.annuaire().subscribe(u => this.collaborateurs = (u ?? []).map(x => ({ id: x.id, libelle: x.libelle })));
  }

  get filtresOrganisation(): boolean { return this.profil === 'direction'; }

  choisir(code: string): void {
    if (!code) return;
    this.profil = code;
    if (code === 'direction') this.chargerListes();
    this.router.navigate([], { queryParams: { profil: code }, replaceUrl: true });
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
    if (!this.profil) return;
    this.chargement = true;
    this.service.tableau(this.profil, this.filtresOrganisation ? this.filtres
      : { du: this.filtres['du'], au: this.filtres['au'], type_demande: this.filtres['type_demande'] }).subscribe({
      next: t => { this.tdb = t; this.chargement = false; },
      error: e => { this.chargement = false; this.toast.error(messageErreur(e)); },
    });
  }

  reinitialiser(): void { this.filtres = this.periode('annee'); this.preset = 'annee'; this.charger(); }

  // ── Affichage ──
  valeur(i: Indicateur): string {
    if (i.format === 'montant') return complet(Number(i.valeur));
    if (i.format === 'heures') return `${complet(Number(i.valeur), 1)}`;
    if (i.format === 'jours') return `${complet(Number(i.valeur), 1)}`;
    return complet(Number(i.valeur));
  }
  unite(i: Indicateur): string {
    return i.format === 'montant' ? this.tdb?.devise ?? '' : i.format === 'heures' ? 'h' : i.format === 'jours' ? 'j' : '';
  }
  cellule(c: { format: string }, v: any): string {
    if (v === null || v === undefined || v === '') return '—';
    switch (c.format) {
      case 'montant': return `${complet(Number(v))} ${this.tdb?.devise ?? ''}`;
      case 'date': return new Date(String(v).length === 10 ? `${v}T00:00:00` : v).toLocaleDateString('fr-FR');
      case 'dateheure': return new Date(v).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' });
      case 'oui_non': return v ? 'Oui' : 'Non';
      case 'nombre': return complet(Number(v));
      default: return String(v);
    }
  }
  vide(s: Section): boolean {
    if (s.type === 'tableau') return !s.lignes?.length;
    if (s.type === 'barres') return !s.donnees?.some(d => Number(d.valeur) > 0);
    return !s.donnees?.some(d => Object.values(d.valeurs ?? {}).some(v => Number(v) > 0));
  }
  ouvrir(ligne: any): void { if (ligne?.id) this.router.navigate(['/demandes', ligne.id]); }

  get libelleFiltres(): string {
    const f = this.filtres, parts: string[] = [];
    parts.push(`du ${new Date(f['du'] + 'T00:00:00').toLocaleDateString('fr-FR')} au ${new Date(f['au'] + 'T00:00:00').toLocaleDateString('fr-FR')}`);
    const lib = (liste: any[], id: any, champ: string) => liste.find(x => String(x.id) === String(id))?.[champ];
    if (f['type_demande']) parts.push(`type : ${lib(this.types, f['type_demande'], 'libelle')}`);
    if (this.filtresOrganisation) {
      if (f['statut']) parts.push(`statut : ${STATUTS.find(s => s[0] === f['statut'])?.[1]}`);
      if (f['departement']) parts.push(`département : ${lib(this.departements, f['departement'], 'libelle_service')}`);
      if (f['agence']) parts.push(`agence : ${lib(this.agences, f['agence'], 'nom_agence')}`);
      if (f['categorie']) parts.push(`catégorie : ${lib(this.categories, f['categorie'], 'libelle')}`);
      if (f['demandeur']) parts.push(`demandeur : ${lib(this.collaborateurs, f['demandeur'], 'libelle')}`);
    }
    return parts.join(' · ');
  }

  // ── Exports ──
  private lignesSection(s: Section): Cellule[][] {
    const devise = this.tdb?.devise ?? '';
    if (s.type === 'barres') {
      return [['Libellé', s.unite === 'montant' ? `Montant (${devise})` : 'Nombre'],
              ...(s.donnees ?? []).map(d => [d.libelle, Number(d.valeur)])];
    }
    if (s.type === 'colonnes') {
      return [['Mois', ...(s.series ?? []).map(x => s.unite === 'montant' ? `${x.libelle} (${devise})` : x.libelle)],
              ...(s.donnees ?? []).map(d => [d.libelle, ...(s.series ?? []).map(x => Number(d.valeurs[x.cle]) || 0)])];
    }
    const cols = s.colonnes ?? [];
    return [['N°', ...cols.map(c => c.libelle)],
            ...(s.lignes ?? []).map((l, i) => [i + 1, ...cols.map(c => ['montant', 'nombre'].includes(c.format) && l[c.cle] !== null && l[c.cle] !== undefined
              ? Number(l[c.cle]) : this.cellule(c, l[c.cle]))])];
  }

  exporterExcel(): void {
    if (!this.tdb) return;
    const t = this.tdb;
    const indicateurs: Cellule[][] = [[`Tableau de bord — ${t.titre}`], [this.libelleFiltres],
      [`Édité le ${new Date().toLocaleString('fr-FR')}`], [], ['Indicateur', 'Valeur', 'Unité'],
      ...t.indicateurs.map(i => [i.libelle, Number(i.valeur), this.unite(i)])];
    exporterExcel(nomFichier('tableau-de-bord', t.titre, t.du, t.au),
      [{ nom: 'Indicateurs', lignes: indicateurs, largeurs: [44, 18, 8] }, ...t.sections.map(s => ({ nom: s.titre, lignes: this.lignesSection(s) }))]);
  }

  async exporterPdf(): Promise<void> {
    if (!this.tdb || this.exportEnCours) return;
    this.exportEnCours = true;
    try {
      const t = this.tdb;
      await chargerLogoPdf((await firstValueFrom(this.baremes.parametres()).catch(() => null))?.logo);
      const p = nouveauPdf(`Tableau de bord — ${t.titre}`, `${this.libelleFiltres} · montants en ${t.devise} · édité le ${new Date().toLocaleString('fr-FR')}`, false);
      tableauPdf(p, ['Indicateur', 'Valeur'], t.indicateurs.map(i => [i.libelle, `${this.valeur(i)} ${this.unite(i)}`.trim()]), false, [1]);
      const svgs = new Map<string, SVGSVGElement>();
      this.barres.forEach(b => svgs.set(b.titre, b.svg.nativeElement));
      this.colonnes.forEach(c => svgs.set(c.titre, c.svg.nativeElement));
      for (const s of t.sections) {
        titrePdf(p, s.titre);
        if (this.vide(s)) { tableauPdf(p, ['Aucune donnée sur la période'], []); continue; }
        const svg = svgs.get(s.titre);
        if (svg && s.type !== 'tableau') {
          if (s.type === 'colonnes' && (s.series?.length ?? 0) > 1) {
            p.doc.setFontSize(8); p.doc.setTextColor(82, 81, 78);
            p.doc.text('Légende : ' + (s.series ?? []).map((x, i) => `${['bleu', 'orange', 'vert d\'eau'][i]} = ${x.libelle}`).join(' · '), 14, p.y + 2);
            p.y += 4;
          }
          await imagePdf(p, await svgVersPng(svg));
        }
        const lignes = this.lignesSection(s);
        placePdf(p, 20);
        tableauPdf(p, lignes[0], lignes.slice(1).map(l => l.map(c => typeof c === 'number' ? complet(c) : c)), false,
                   lignes[0].map((_, i) => i).filter(i => lignes.slice(1).some(l => typeof l[i] === 'number') && i > 0));
      }
      enregistrerPdf(p, nomFichier('tableau-de-bord', t.titre, t.du, t.au));
    } catch (e: any) {
      this.toast.error(e?.message || "L'export a échoué.");
    } finally {
      this.exportEnCours = false;
    }
  }
}
