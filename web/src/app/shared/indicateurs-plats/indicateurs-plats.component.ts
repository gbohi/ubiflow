// Statistiques « Plats & popularité » et « Montants » : composant commun à la
// page Statistiques (UbiPharm : GET statistiques/indicateurs/) et aux
// statistiques du prestataire (GET prestataire/statistiques/indicateurs/,
// sans les montants facturés aux employés). Graphiques ApexCharts :
// histogrammes (mois, agences, plats), camemberts (types, modes de
// règlement), courbes (évolution de la popularité) ; export Excel.
import { Component, DestroyRef, Input, OnChanges, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient, HttpParams } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NgApexchartsModule } from 'ng-apexcharts';
import { environment } from 'src/environments/environment';
import { exporterExcel, nomFichier } from 'src/app/core/helpers/exports';

export interface PlatIndicateur { plat_id: number; plat: string; type_plat: string; commandes: number; servis: number; popularite: number }
export interface LigneMontant { employes?: number; prestataires: number; repas: number; supplements: number; [cle: string]: any }
export interface Indicateurs {
  debut: string; fin: string;
  kpis: { nb_repas: number; nb_plats: number; nb_menus: number; moyenne_par_menu: number; nb_supplements: number;
          plat_plus: PlatIndicateur | null; plat_moins: PlatIndicateur | null };
  par_plat: PlatIndicateur[];
  par_menu: { menu_id: number; date: string; agence: string; equipe: string; commandes: number; servis: number }[];
  preferences: { agences: { agence: string; commandes: number }[];
                 plats: { plat: string; commandes: number; parts: Record<string, number>; nb: Record<string, number> }[] };
  evolution: { granularite: 'mois' | 'semaine'; periodes: string[]; series: { plat: string; parts: number[]; commandes: number[] }[] };
  montants: {
    total_employes?: number; total_prestataires: number;
    par_mois: (LigneMontant & { annee: number; mois: number; libelle: string; court: string })[];
    par_agence: LigneMontant[]; par_plat: LigneMontant[]; par_type: LigneMontant[]; par_prestataire: LigneMontant[];
    par_mode?: { mode: string; libelle: string; montant: number; nb: number }[];
  };
}

const C = ['#0F3A6E', '#3EC970', '#F7B84B', '#2F80ED', '#F06548', '#7B61FF', '#9AA9BE', '#14B8A6'];
const fcfa = (v: number) => `${Math.round(v || 0).toLocaleString('fr-FR')} F`;
const court = (v: number) => v >= 1e6 ? `${(v / 1e6).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} M`
  : v >= 1e3 ? `${Math.round(v / 1e3).toLocaleString('fr-FR')} k` : `${Math.round(v)}`;

@Component({
  selector: 'app-indicateurs-plats',
  standalone: true,
  imports: [CommonModule, NgApexchartsModule],
  templateUrl: './indicateurs-plats.component.html',
  styleUrls: ['./indicateurs-plats.component.scss'],
})
export class IndicateursPlatsComponent implements OnChanges {
  private http = inject(HttpClient);
  private destroyRef = inject(DestroyRef);

  /** 'ubipharm' : montants employés et prestataires ; 'prestataire' : ce qui lui est dû */
  @Input() source: 'ubipharm' | 'prestataire' = 'ubipharm';
  @Input() debut = '';
  @Input() fin = '';
  @Input() agence: number | string | null = null;
  @Input() typeequipe: number | string | null = null;
  /** Bloc affiché : plats, montants, ou les deux */
  @Input() vue: 'plats' | 'montants' | 'tout' = 'tout';

  d: Indicateurs | null = null;
  chargement = false;
  erreur: string | null = null;
  menusAffiches = 10;
  readonly fcfa = fcfa;
  /** Nombres et pourcentages à la française (1 305 · 40,2) */
  nb(v: number | null | undefined, dec = 0): string {
    return (v ?? 0).toLocaleString('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: dec });
  }
  jour(iso: string): string {
    const d = new Date(iso + 'T12:00:00');
    return d.toLocaleDateString('fr-FR', { weekday: 'short', day: '2-digit', month: '2-digit' });
  }

  g: Record<string, any> = {};

  get ubipharm(): boolean { return this.source === 'ubipharm'; }

  ngOnChanges(): void {
    if (this.debut && this.fin) this.charger();
  }

  charger(): void {
    const url = this.ubipharm ? `${environment.apiUrl}/api/api/statistiques/indicateurs/`
      : `${environment.apiUrl}/api/api/prestataire/statistiques/indicateurs/`;
    let p = new HttpParams().set('debut', this.debut).set('fin', this.fin);
    if (this.agence) p = p.set('agence', String(this.agence));
    if (this.typeequipe && this.ubipharm) p = p.set('typeequipe', String(this.typeequipe));
    this.chargement = true;
    this.http.get<Indicateurs>(url, { params: p }).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: d => { this.d = d; this.chargement = false; this.erreur = null; this.menusAffiches = 10; this.construire(d); },
      error: e => { this.chargement = false; this.erreur = typeof e === 'string' ? e : 'Les indicateurs n\'ont pas pu être chargés.'; },
    });
  }

  // ── Graphiques ─────────────────────────────────────────────
  private construire(d: Indicateurs): void {
    const base = (type: string, height: number) => ({ type, height, fontFamily: 'inherit', toolbar: { show: false }, animations: { enabled: false } });
    const grille = { borderColor: '#EEF2F7' };
    const top = d.par_plat.slice(0, 10);
    this.g = {};

    this.g['popularite'] = top.length ? {
      series: [{ name: 'Commandes', data: top.map(p => p.commandes) }],
      chart: base('bar', Math.max(200, 50 + top.length * 30)), colors: [C[0]],
      plotOptions: { bar: { horizontal: true, barHeight: '62%', borderRadius: 3, dataLabels: { position: 'top' } } },
      dataLabels: { enabled: true, offsetX: 30, style: { colors: ['#092440'], fontSize: '11px' },
                    formatter: (v: number, o: any) => `${v} · ${top[o.dataPointIndex]?.popularite.toLocaleString('fr-FR')} %` },
      xaxis: { categories: top.map(p => p.plat) }, grid: grille, tooltip: { y: { formatter: (v: number) => `${v} commandes` } },
    } : null;

    const ev = d.evolution;
    this.g['evolution'] = ev.series.length && ev.periodes.length > 1 ? {
      series: ev.series.map(s => ({ name: s.plat, data: s.parts })),
      chart: base('line', 280), colors: C, stroke: { curve: 'smooth', width: 2.5 }, markers: { size: ev.periodes.length > 20 ? 0 : 3 },
      dataLabels: { enabled: false }, xaxis: { categories: ev.periodes, labels: { rotate: 0, hideOverlappingLabels: true, style: { fontSize: '10px' } } },
      yaxis: { min: 0, labels: { formatter: (v: number) => `${Math.round(v)} %` } },
      legend: { position: 'bottom', fontSize: '12px' }, grid: grille,
      tooltip: { shared: true, intersect: false, y: { formatter: (v: number) => `${v.toLocaleString('fr-FR')} % des commandes` } },
    } : null;

    const m = d.montants;
    const mois = m.par_mois;
    const series = this.ubipharm
      ? [{ name: 'Facturé aux employés', data: mois.map(x => x.employes ?? 0) }, { name: 'Dû aux prestataires', data: mois.map(x => x.prestataires) }]
      : [{ name: 'Montant dû', data: mois.map(x => x.prestataires) }];
    this.g['mois'] = mois.length ? {
      series, chart: base('bar', 300), colors: this.ubipharm ? [C[0], C[1]] : [C[1]],
      plotOptions: { bar: { columnWidth: mois.length > 6 ? '70%' : '45%', borderRadius: 3 } },
      dataLabels: { enabled: mois.length <= 6, formatter: court, style: { fontSize: '10px' }, offsetY: -2 },
      xaxis: { categories: mois.map(x => x.court) }, yaxis: { labels: { formatter: court } },
      legend: { position: 'bottom', fontSize: '12px' }, grid: grille, tooltip: { shared: true, intersect: false, y: { formatter: fcfa } },
    } : null;

    const ag = m.par_agence.slice(0, 10);
    this.g['agence'] = ag.length ? {
      series: this.ubipharm
        ? [{ name: 'Facturé aux employés', data: ag.map(x => x.employes ?? 0) }, { name: 'Dû aux prestataires', data: ag.map(x => x.prestataires) }]
        : [{ name: 'Montant dû', data: ag.map(x => x.prestataires) }],
      chart: base('bar', Math.max(200, 60 + ag.length * (this.ubipharm ? 44 : 30))), colors: this.ubipharm ? [C[0], C[1]] : [C[1]],
      plotOptions: { bar: { horizontal: true, barHeight: '70%', borderRadius: 3 } }, dataLabels: { enabled: false },
      xaxis: { categories: ag.map(x => x['agence']), labels: { formatter: court } },
      legend: { position: 'bottom', fontSize: '12px' }, grid: grille, tooltip: { shared: true, intersect: false, y: { formatter: fcfa } },
    } : null;

    const pl = m.par_plat.slice(0, 10);
    this.g['plat'] = pl.length ? {
      series: [{ name: this.ubipharm ? 'Dû aux prestataires' : 'Montant dû', data: pl.map(x => x.prestataires) }],
      chart: base('bar', Math.max(200, 50 + pl.length * 30)), colors: [C[3]],
      plotOptions: { bar: { horizontal: true, barHeight: '62%', borderRadius: 3 } }, dataLabels: { enabled: false },
      xaxis: { categories: pl.map(x => x['plat']), labels: { formatter: court } }, grid: grille, tooltip: { y: { formatter: fcfa } },
    } : null;

    const donut = (valeurs: number[], libelles: string[], total: string) => valeurs.some(v => v > 0) ? {
      series: valeurs, labels: libelles, chart: base('donut', 270), colors: C,
      legend: { position: 'bottom', fontSize: '12px' }, dataLabels: { enabled: true, formatter: (v: number) => `${Math.round(v)} %` },
      plotOptions: { pie: { donut: { size: '62%', labels: { show: true, value: { fontSize: '16px', fontWeight: 700, formatter: (v: string) => fcfa(Number(v)) },
        total: { show: true, label: total, fontSize: '11px', formatter: (w: any) => fcfa(w.globals.seriesTotals.reduce((a: number, b: number) => a + b, 0)) } } } } },
      tooltip: { y: { formatter: fcfa } },
    } : null;
    this.g['type'] = donut(m.par_type.map(x => x.prestataires), m.par_type.map(x => x['type_plat']), this.ubipharm ? 'dû aux prestataires' : 'montant dû');
    this.g['mode'] = m.par_mode ? donut(m.par_mode.map(x => x.montant), m.par_mode.map(x => x.libelle), 'facturé aux employés') : null;
    this.g['prestataire'] = this.ubipharm && m.par_prestataire.length > 1
      ? donut(m.par_prestataire.map(x => x.prestataires), m.par_prestataire.map(x => x['prestataire']), 'dû aux prestataires') : null;
  }

  // ── Affichage ──────────────────────────────────────────────
  maxPop(): number { return Math.max(1, ...(this.d?.par_plat ?? []).map(p => p.popularite)); }

  couleurPart(v: number): string {
    const a = 0.08 + Math.min(v, 60) / 60 * 0.75;
    return `rgba(62, 201, 112, ${a.toFixed(2)})`;
  }

  get menus() { return (this.d?.par_menu ?? []).slice(0, this.menusAffiches); }

  // ── Export ─────────────────────────────────────────────────
  exporter(): void {
    const d = this.d;
    if (!d) return;
    const m = d.montants;
    const emp = this.ubipharm;
    const feuilles = [
      { nom: 'Plats', lignes: [['Plat', 'Type', 'Commandes', 'Servis', 'Popularité (%)'],
        ...d.par_plat.map(p => [p.plat, p.type_plat, p.commandes, p.servis, p.popularite])] },
      { nom: 'Par menu', lignes: [['Date', 'Agence', 'Équipe', 'Commandes', 'Servis'],
        ...d.par_menu.map(x => [x.date, x.agence, x.equipe, x.commandes, x.servis])] },
      { nom: 'Préférences agences', lignes: [['Plat', ...d.preferences.agences.map(a => `${a.agence} (%)`)],
        ...d.preferences.plats.map(p => [p.plat, ...d.preferences.agences.map(a => p.parts[a.agence] ?? 0)])] },
      { nom: 'Évolution', lignes: [['Plat', ...d.evolution.periodes],
        ...d.evolution.series.map(s => [s.plat, ...s.parts])] },
      { nom: 'Montants par mois', lignes: [['Mois', ...(emp ? ['Facturé aux employés'] : []), 'Dû aux prestataires', 'Repas', 'Desserts'],
        ...m.par_mois.map(x => [x.libelle, ...(emp ? [x.employes ?? 0] : []), x.prestataires, x.repas, x.supplements])] },
      { nom: 'Montants par agence', lignes: [['Agence', ...(emp ? ['Facturé aux employés'] : []), 'Dû aux prestataires', 'Repas', 'Desserts'],
        ...m.par_agence.map(x => [x['agence'], ...(emp ? [x.employes ?? 0] : []), x.prestataires, x.repas, x.supplements])] },
      { nom: 'Montants par type', lignes: [['Type de plat', ...(emp ? ['Facturé aux employés'] : []), 'Dû aux prestataires', 'Repas', 'Desserts'],
        ...m.par_type.map(x => [x['type_plat'], ...(emp ? [x.employes ?? 0] : []), x.prestataires, x.repas, x.supplements])] },
    ];
    if (m.par_mode) feuilles.push({ nom: 'Modes de règlement', lignes: [['Mode', 'Montant', 'Repas'], ...m.par_mode.map(x => [x.libelle, x.montant, x.nb])] });
    exporterExcel(nomFichier('indicateurs-plats-montants', d.debut, d.fin) + '.xlsx', feuilles as any);
  }
}
