// Statistiques complémentaires : desserts, participation, affluence au
// comptoir, comptes repas, comparaison des prestataires, contrôle du
// comptoir (contestations, badges perdus), jeux. UbiPharm : GET
// statistiques/complements/ ; prestataire : desserts, affluence et
// contestations de ses retraits (GET prestataire/statistiques/indicateurs/?complements=seuls).
import { Component, DestroyRef, Input, OnChanges, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient, HttpParams } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NgApexchartsModule } from 'ng-apexcharts';
import { environment } from 'src/environments/environment';
import { exporterExcel, nomFichier } from 'src/app/core/helpers/exports';

export type BlocComplement = 'desserts' | 'participation' | 'affluence' | 'comptes' | 'prestataires' | 'controle' | 'jeux';

const C = ['#0F3A6E', '#3EC970', '#F7B84B', '#2F80ED', '#F06548', '#7B61FF', '#9AA9BE', '#14B8A6'];
const fcfa = (v: number | null | undefined) => `${Math.round(v || 0).toLocaleString('fr-FR')} F`;
const court = (v: number) => v >= 1e6 ? `${(v / 1e6).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} M`
  : v >= 1e3 ? `${Math.round(v / 1e3).toLocaleString('fr-FR')} k` : `${Math.round(v)}`;

@Component({
  selector: 'app-stats-complements',
  standalone: true,
  imports: [CommonModule, NgApexchartsModule],
  templateUrl: './stats-complements.component.html',
  styleUrls: ['../indicateurs-plats/indicateurs-plats.component.scss'],
})
export class StatsComplementsComponent implements OnChanges {
  private http = inject(HttpClient);
  private destroyRef = inject(DestroyRef);

  @Input() source: 'ubipharm' | 'prestataire' = 'ubipharm';
  @Input() debut = '';
  @Input() fin = '';
  @Input() agence: number | string | null = null;
  @Input() typeequipe: number | string | null = null;
  /** Blocs affichés (par défaut : tous ceux de la source) */
  @Input() blocs: BlocComplement[] | null = null;

  d: any = null;
  chargement = false;
  erreur: string | null = null;
  jamaisAffiches = 12;
  g: Record<string, any> = {};
  readonly fcfa = fcfa;

  get ubipharm(): boolean { return this.source === 'ubipharm'; }
  voir(b: BlocComplement): boolean {
    const dispo: BlocComplement[] = this.ubipharm
      ? ['desserts', 'participation', 'affluence', 'comptes', 'prestataires', 'controle', 'jeux']
      : ['desserts', 'affluence', 'controle'];
    return dispo.includes(b) && (!this.blocs || this.blocs.includes(b));
  }

  nb(v: number | null | undefined, dec = 0): string {
    return v == null ? '—' : v.toLocaleString('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: dec });
  }
  pct(v: number | null | undefined): string { return v == null ? '—' : `${this.nb(v, 1)} %`; }

  ngOnChanges(): void { if (this.debut && this.fin) this.charger(); }

  charger(): void {
    const url = this.ubipharm ? `${environment.apiUrl}/api/api/statistiques/complements/`
      : `${environment.apiUrl}/api/api/prestataire/statistiques/indicateurs/`;
    let p = new HttpParams().set('debut', this.debut).set('fin', this.fin);
    if (this.agence) p = p.set('agence', String(this.agence));
    if (this.typeequipe && this.ubipharm) p = p.set('typeequipe', String(this.typeequipe));
    if (!this.ubipharm) p = p.set('complements', 'seuls');
    this.chargement = true;
    this.http.get<any>(url, { params: p }).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: d => { this.d = d; this.chargement = false; this.erreur = null; this.jamaisAffiches = 12; this.construire(d); },
      error: e => { this.chargement = false; this.erreur = typeof e === 'string' ? e : 'Les statistiques n\'ont pas pu être chargées.'; },
    });
  }

  private construire(d: any): void {
    const base = (type: string, height: number) => ({ type, height, fontFamily: 'inherit', toolbar: { show: false }, animations: { enabled: false } });
    const grille = { borderColor: '#EEF2F7' };
    this.g = {};
    const ds = d.desserts?.par_dessert ?? [];
    this.g['desserts'] = ds.length ? {
      series: ds.map((x: any) => x.choisis), labels: ds.map((x: any) => x.plat), chart: base('donut', 260), colors: C,
      legend: { position: 'bottom', fontSize: '12px' }, dataLabels: { enabled: true, formatter: (v: number) => `${Math.round(v)} %` },
      plotOptions: { pie: { donut: { size: '62%', labels: { show: true, total: { show: true, label: 'desserts choisis', fontSize: '11px',
        formatter: (w: any) => this.nb(w.globals.seriesTotals.reduce((a: number, b: number) => a + b, 0)) } } } } },
    } : null;

    const pa = d.participation?.par_agence ?? [];
    this.g['participation'] = pa.length ? {
      series: [{ name: 'Taux de participation', data: pa.map((x: any) => x.taux_participation ?? 0) },
               { name: 'Taux de commande journalier', data: pa.map((x: any) => x.taux_journalier ?? 0) }],
      chart: base('bar', Math.max(220, 70 + pa.length * 50)), colors: [C[0], C[1]],
      plotOptions: { bar: { horizontal: true, barHeight: '70%', borderRadius: 3, dataLabels: { position: 'top' } } },
      dataLabels: { enabled: true, offsetX: 26, style: { colors: ['#092440'], fontSize: '11px' }, formatter: (v: number) => `${Math.round(v)} %` },
      xaxis: { categories: pa.map((x: any) => x.agence), max: 100, labels: { formatter: (v: number) => `${Math.round(v)} %` } },
      legend: { position: 'bottom', fontSize: '12px' }, grid: grille, tooltip: { y: { formatter: (v: number) => `${this.nb(v, 1)} %` } },
    } : null;

    const af = d.affluence?.tranches ?? [];
    this.g['affluence'] = af.length ? {
      series: [{ name: 'Retraits (moyenne par jour)', data: af.map((t: any) => t.moyenne) }],
      chart: base('bar', 260), colors: [C[3]],
      plotOptions: { bar: { columnWidth: '75%', borderRadius: 3 } }, dataLabels: { enabled: false },
      xaxis: { categories: af.map((t: any) => t.tranche), labels: { rotate: -45, style: { fontSize: '10px' } } },
      grid: grille, tooltip: { y: { formatter: (v: number, o: any) => `${this.nb(v, 1)} en moyenne · ${af[o.dataPointIndex]?.retraits} au total` } },
    } : null;

    const cm = d.comptes_repas?.par_mois ?? [];
    this.g['comptes'] = cm.length ? {
      series: [{ name: 'Recharges', type: 'column', data: cm.map((x: any) => x.recharges) },
               { name: 'Repas débités', type: 'column', data: cm.map((x: any) => x.debits) }],
      chart: base('bar', 280), colors: [C[1], C[0]],
      plotOptions: { bar: { columnWidth: '55%', borderRadius: 3 } }, dataLabels: { enabled: false },
      xaxis: { categories: cm.map((x: any) => x.libelle) }, yaxis: { labels: { formatter: court } },
      legend: { position: 'bottom', fontSize: '12px' }, grid: grille, tooltip: { shared: true, intersect: false, y: { formatter: fcfa } },
    } : null;
    this.g['modes'] = cm.length ? {
      series: [{ name: 'Compte repas', data: cm.map((x: any) => x.repas_compte) }, { name: 'Retenue sur salaire', data: cm.map((x: any) => x.repas_retenue) }],
      chart: { ...base('bar', 260), stacked: true, stackType: '100%' }, colors: [C[1], C[0]],
      plotOptions: { bar: { columnWidth: '50%' } }, dataLabels: { enabled: true, formatter: (v: number) => `${Math.round(v)} %`, style: { fontSize: '10px' } },
      xaxis: { categories: cm.map((x: any) => x.libelle) }, legend: { position: 'bottom', fontSize: '12px' }, grid: grille,
      tooltip: { y: { formatter: (v: number) => `${v} repas` } },
    } : null;

    const ct = d.controle?.par_mois ?? [];
    this.g['controle'] = ct.length ? {
      series: [{ name: 'Contestations', data: ct.map((x: any) => x.contestations) }, { name: 'Acceptées', data: ct.map((x: any) => x.acceptees) },
               ...(this.ubipharm ? [{ name: 'Badges perdus', data: ct.map((x: any) => x.badges_perdus) }] : [])],
      chart: base('bar', 260), colors: [C[2], C[4], C[6]],
      plotOptions: { bar: { columnWidth: '60%', borderRadius: 3 } }, dataLabels: { enabled: false },
      xaxis: { categories: ct.map((x: any) => x.libelle) }, yaxis: { labels: { formatter: (v: number) => `${Math.round(v)}` } },
      legend: { position: 'bottom', fontSize: '12px' }, grid: grille,
    } : null;

    const jm = d.jeux?.par_mois ?? [];
    this.g['jeux'] = jm.length && jm.some((x: any) => x.parties || x.gagnants) ? {
      series: [{ name: 'Parties', data: jm.map((x: any) => x.parties) }, { name: 'Joueurs', data: jm.map((x: any) => x.joueurs) },
               { name: 'Gagnants', data: jm.map((x: any) => x.gagnants) }],
      chart: base('bar', 260), colors: [C[5], C[3], C[1]], plotOptions: { bar: { columnWidth: '60%', borderRadius: 3 } },
      dataLabels: { enabled: false }, xaxis: { categories: jm.map((x: any) => x.libelle) }, legend: { position: 'bottom', fontSize: '12px' }, grid: grille,
    } : null;
  }

  get jamais(): any[] { return (this.d?.participation?.jamais ?? []).slice(0, this.jamaisAffiches); }

  exporter(): void {
    const d = this.d;
    if (!d) return;
    const f: { nom: string; lignes: any[][] }[] = [];
    if (d.desserts) f.push({ nom: 'Desserts', lignes: [['Dessert', 'Choisis', 'Servis', 'Part (%)'], ...d.desserts.par_dessert.map((x: any) => [x.plat, x.choisis, x.servis, x.part])] });
    if (d.participation) {
      f.push({ nom: 'Participation', lignes: [['Agence', 'Effectif', 'Ont commandé', 'Participation (%)', 'Repas', 'Repas par employé', 'Jours de service', 'Commande journalière (%)'],
        ...d.participation.par_agence.map((x: any) => [x.agence, x.effectif, x.commandeurs, x.taux_participation, x.repas, x.repas_par_employe, x.jours_service, x.taux_journalier])] });
      f.push({ nom: 'Jamais commandé', lignes: [['Employé', 'Matricule'], ...d.participation.jamais.map((x: any) => [x.nom, x.matricule])] });
    }
    if (d.affluence) f.push({ nom: 'Affluence', lignes: [['Tranche', 'Retraits', 'Moyenne par jour'], ...d.affluence.tranches.map((t: any) => [t.tranche, t.retraits, t.moyenne])] });
    if (d.comptes_repas) {
      f.push({ nom: 'Comptes repas', lignes: [['Mois', 'Recharges', 'Nb recharges', 'Repas débités', 'Repas compte', 'Repas retenue'],
        ...d.comptes_repas.par_mois.map((x: any) => [x.libelle, x.recharges, x.nb_recharges, x.debits, x.repas_compte, x.repas_retenue])] });
      f.push({ nom: 'Soldes bas', lignes: [['Employé', 'Matricule', 'Solde'], ...d.comptes_repas.soldes_bas.map((x: any) => [x.nom, x.matricule, x.solde])] });
    }
    if (d.prestataires) f.push({ nom: 'Prestataires', lignes: [['Prestataire', 'Agences', 'Repas', 'Desserts', 'Taux de retrait (%)', 'Note', 'Avis', 'Contestations', 'Coût moyen repas'],
      ...d.prestataires.map((x: any) => [x.prestataire, x.agences.join(', '), x.repas, x.supplements, x.taux_retrait, x.note, x.nb_avis, x.contestations, x.cout_moyen_repas])] });
    if (d.controle) f.push({ nom: 'Contrôle', lignes: [['Mois', 'Contestations', 'Acceptées', 'Badges perdus'], ...d.controle.par_mois.map((x: any) => [x.libelle, x.contestations, x.acceptees, x.badges_perdus])] });
    if (d.jeux) f.push({ nom: 'Jeux', lignes: [['Mois', 'Parties', 'Joueurs', 'Gagnants'], ...d.jeux.par_mois.map((x: any) => [x.libelle, x.parties, x.joueurs, x.gagnants])] });
    exporterExcel(nomFichier('statistiques-complementaires', d.debut, d.fin) + '.xlsx', f as any);
  }
}
