// Carte des destinations de mission.
// « Côte d'Ivoire » : un cercle par ville, aire proportionnelle au nombre de missions.
// « International » : pays colorés selon le nombre de missions (une teinte, du clair au foncé), avec la légende de l'échelle.
// Fond de carte pré-projeté (src/assets/geo/carte.json, généré par scripts/generer-carte.js), chargé une seule fois.
import { HttpClient } from '@angular/common/http';
import { Component, ElementRef, Input, OnChanges, ViewChild, inject } from '@angular/core';
import { Observable, shareReplay } from 'rxjs';
import { BARRE, STYLES_GRAPHE, complet } from './format';

interface Vue { lonMin: number; latMax: number; k: number; cosLat?: number; largeur: number; hauteur: number; pays: { iso: string; d: string }[]; }
interface Fond { ci: Vue; monde: Vue; }
export interface PointCarte { ville: string; pays: string; iso: string; valeur: number; lat: number | null; lon: number | null; }

let fond$: Observable<Fond> | null = null;
// Rampe séquentielle bleue (5 classes) pour les pays
const CLASSES = ['#cce3fd', '#9dc8f7', '#519ced', '#2370cd', '#0e3d7e'];

@Component({
  selector: 'app-graphe-carte',
  template: `
    <div class="d-flex align-items-center gap-2 mb-2 flex-wrap">
      <div class="btn-group btn-group-sm" role="group" aria-label="Zone">
        <button type="button" class="btn" [class.btn-primary]="zone === 'ci'" [class.btn-light]="zone !== 'ci'" (click)="zone = 'ci'">Côte d'Ivoire</button>
        <button type="button" class="btn" [class.btn-primary]="zone === 'monde'" [class.btn-light]="zone !== 'monde'" (click)="zone = 'monde'">International</button>
      </div>
      @if (zone === 'monde' && echelle.length) {
        <div class="ca-echelle ms-auto">
          <span>moins</span>@for (c of echelle; track $index) { <i [style.background]="c"></i> }<span>plus de missions</span>
        </div>
      } @else if (zone === 'ci') {
        <span class="ms-auto small text-muted">Aire du cercle = nombre de missions</span>
      }
    </div>
    <div class="gr-zone" (mouseleave)="survol = null">
      @if (vue) {
        <svg #svg [attr.viewBox]="'0 0 ' + vue.largeur + ' ' + vue.hauteur" role="img" [attr.aria-label]="titre" xmlns="http://www.w3.org/2000/svg"
             font-family="Poppins, Arial, sans-serif" style="width: 100%; height: auto; display: block; background: #f6f9fc; border-radius: 8px">
          @for (p of vue.pays; track $index) {
            <path [attr.d]="p.d" [attr.fill]="remplissage(p.iso)" stroke="#fff" [attr.stroke-width]="zone === 'ci' ? 1.2 : 0.5"
                  (mouseenter)="survolPays(p.iso, $event)" />
          }
          @if (zone === 'ci') {
            @for (pt of pointsCi; track pt.ville) {
              <circle [attr.cx]="pt.x" [attr.cy]="pt.y" [attr.r]="rayon(pt.valeur)" [attr.fill]="bleu" fill-opacity="0.85" stroke="#fff" stroke-width="2"
                      (mouseenter)="survolPoint(pt, $event)" />
            }
            @for (pt of pointsCi.slice(0, 6); track pt.ville) {
              <text [attr.x]="pt.x + rayon(pt.valeur) + 5" [attr.y]="pt.y + 4" font-size="13" font-weight="600" fill="#191919"
                    stroke="#f6f9fc" stroke-width="3" paint-order="stroke">{{ pt.ville }} · {{ pt.valeur }}</text>
            }
          }
        </svg>
      } @else {
        <div class="text-center text-muted small py-5">Chargement de la carte…</div>
      }
      @if (survol) {
        <div class="gr-bulle" [style.left.px]="survol.x" [style.top.px]="survol.y"><b>{{ survol.titre }}</b><div>{{ survol.texte }}</div></div>
      }
    </div>
    @if (sansCoordonnees.length) {
      <p class="small text-muted mt-2 mb-0">Sans coordonnées (non placées) : {{ sansCoordonnees.join(', ') }}. Renseignez-les dans Lieux et distances.</p>
    }`,
  styles: [STYLES_GRAPHE, `
    .ca-echelle { display: flex; align-items: center; gap: 3px; font-size: 11px; color: #5b6470; }
    .ca-echelle i { width: 22px; height: 10px; display: inline-block; border-radius: 2px; }
    .ca-echelle span { margin: 0 4px; }`],
})
export class GrapheCarteComponent implements OnChanges {
  private readonly http = inject(HttpClient);
  @Input() points: PointCarte[] = [];
  @Input() pays: { iso: string; libelle: string; valeur: number }[] = [];
  @Input() titre = '';
  @ViewChild('svg') svgRef?: ElementRef<SVGSVGElement>;

  readonly bleu = BARRE;
  fond: Fond | null = null;
  zone: 'ci' | 'monde' = 'ci';
  pointsCi: (PointCarte & { x: number; y: number })[] = [];
  sansCoordonnees: string[] = [];
  echelle: string[] = [];
  survol: { titre: string; texte: string; x: number; y: number } | null = null;
  private seuils: number[] = [];
  private maxVille = 1;

  /** Pour l'export PDF (même accès que les autres graphiques) */
  get svg(): ElementRef<SVGSVGElement> { return this.svgRef!; }

  constructor() {
    fond$ ??= this.http.get<Fond>('assets/geo/carte.json').pipe(shareReplay(1));
    fond$.subscribe(f => { this.fond = f; this.calculer(); });
  }

  ngOnChanges(): void {
    const local = this.points.filter(p => p.iso === 'CI').reduce((s, p) => s + p.valeur, 0);
    const etranger = this.pays.filter(p => p.iso !== 'CI').reduce((s, p) => s + p.valeur, 0);
    this.zone = local || !etranger ? 'ci' : 'monde';
    this.calculer();
  }

  get vue(): Vue | null { return this.fond ? this.fond[this.zone] : null; }

  private calculer(): void {
    if (!this.fond) return;
    const ci = this.fond.ci;
    const projeter = (lat: number, lon: number) => ({ x: (lon - ci.lonMin) * (ci.cosLat ?? 1) * ci.k, y: (ci.latMax - lat) * ci.k });
    const locaux = this.points.filter(p => p.iso === 'CI');
    this.pointsCi = locaux.filter(p => p.lat !== null && p.lon !== null)
      .map(p => ({ ...p, ...projeter(p.lat!, p.lon!) })).sort((a, b) => b.valeur - a.valeur);
    this.sansCoordonnees = this.points.filter(p => p.lat === null || p.lon === null).map(p => p.ville);
    this.maxVille = Math.max(...this.pointsCi.map(p => p.valeur), 1);
    // Pays : 5 classes égales de 1 au maximum (hors Côte d'Ivoire, pays d'origine)
    const valeurs = this.pays.filter(p => p.iso !== 'CI').map(p => p.valeur);
    const max = Math.max(...valeurs, 0);
    const n = Math.min(CLASSES.length, Math.max(max, 1));
    this.seuils = Array.from({ length: n }, (_, i) => Math.ceil(((i + 1) * max) / n));
    this.echelle = max ? CLASSES.slice(CLASSES.length - n) : [];
  }

  rayon(v: number): number { return 5 + 22 * Math.sqrt(v / this.maxVille); }

  remplissage(iso: string): string {
    if (this.zone === 'ci') return iso === 'CI' ? '#ffffff' : '#e9edf2';
    if (iso === 'CI') return '#c7ced8';
    const v = this.pays.find(p => p.iso === iso)?.valeur ?? 0;
    if (!v) return '#e9edf2';
    const i = this.seuils.findIndex(s => v <= s);
    return this.echelle[i < 0 ? this.echelle.length - 1 : i];
  }

  private position(e: MouseEvent): { x: number; y: number } {
    const zone = (e.target as Element).closest('.gr-zone')!.getBoundingClientRect();
    return { x: e.clientX - zone.left, y: Math.max(e.clientY - zone.top - 64, 0) };
  }
  survolPoint(pt: PointCarte, e: MouseEvent): void {
    this.survol = { titre: pt.ville, texte: `${complet(pt.valeur)} mission${pt.valeur > 1 ? 's' : ''}`, ...this.position(e) };
  }
  survolPays(iso: string, e: MouseEvent): void {
    if (this.zone !== 'monde') { this.survol = null; return; }
    const p = this.pays.find(x => x.iso === iso);
    if (!p || iso === 'CI') { this.survol = iso === 'CI' ? { titre: "Côte d'Ivoire", texte: 'pays de départ', ...this.position(e) } : null; return; }
    const villes = this.points.filter(x => x.iso === iso).map(x => `${x.ville} (${x.valeur})`).join(', ');
    this.survol = { titre: p.libelle, texte: `${complet(p.valeur)} mission${p.valeur > 1 ? 's' : ''}${villes ? ' · ' + villes : ''}`, ...this.position(e) };
  }
}
