// Barres empilées : comparaison entre catégories avec leur décomposition.
// orientation 'colonnes' (catégories = mois, en abscisse) ou 'barres' (catégories en lignes, horizontales).
// 2 px de blanc entre segments, extrémité arrondie (4 px) sur le dernier segment ; survol = détail et total.
import { Component, ElementRef, Input, OnChanges, ViewChild } from '@angular/core';
import { AXE, ENCRE2, GRILLE, STYLES_GRAPHE, complet, compact, couleursParts, graduations } from './format';

@Component({
  selector: 'app-graphe-empile',
  template: `
    <div class="gr-legende">
      @for (s of series; track s.cle; let j = $index) {
        <span><i class="gr-pastille" [style.background]="couleurs[j]"></i>{{ s.libelle }}</span>
      }
    </div>
    <div class="gr-zone" (mouseleave)="survol = -1">
      <svg #svg [attr.viewBox]="'0 0 ' + L + ' ' + hauteur" role="img" [attr.aria-label]="titre" xmlns="http://www.w3.org/2000/svg"
           font-family="Poppins, Arial, sans-serif" style="width: 100%; height: auto; display: block">
        @if (orientation === 'colonnes') {
          @for (t of ticks; track t) {
            <line [attr.x1]="G" [attr.x2]="L" [attr.y1]="yv(t)" [attr.y2]="yv(t)" [attr.stroke]="t === 0 ? axe : grille" stroke-width="1" />
            <text [attr.x]="G - 8" [attr.y]="yv(t) + 4" text-anchor="end" font-size="11" [attr.fill]="encre2">{{ etiquette(t) }}</text>
          }
          @for (c of cats; track $index; let i = $index) {
            <g (mouseenter)="survol = i">
              <rect [attr.x]="G + i * bande" y="0" [attr.width]="bande" [attr.height]="H - B" [attr.fill]="survol === i ? '#f3f4f6' : 'transparent'" />
              @for (s of series; track s.cle; let j = $index) { <path [attr.d]="segmentV(i, j)" [attr.fill]="couleurs[j]" /> }
              @if (afficher(i)) {
                <text [attr.x]="G + i * bande + bande / 2" [attr.y]="H - 6" text-anchor="middle" font-size="11" [attr.fill]="encre2">{{ c.libelle }}</text>
              }
            </g>
          }
        } @else {
          @for (c of cats; track $index; let i = $index) {
            <g (mouseenter)="survol = i" [attr.opacity]="survol >= 0 && survol !== i ? 0.45 : 1">
              <rect x="0" [attr.y]="yb(i) - 6" [attr.width]="L" [attr.height]="PAS" fill="transparent" />
              <text [attr.x]="LIB - 10" [attr.y]="yb(i) + EP / 2 + 4" text-anchor="end" font-size="12" [attr.fill]="encre2">{{ court(c.libelle) }}</text>
              @for (s of series; track s.cle; let j = $index) { <path [attr.d]="segmentH(i, j)" [attr.fill]="couleurs[j]" /> }
              <text [attr.x]="LIB + largeurH(c.total) + 8" [attr.y]="yb(i) + EP / 2 + 4" font-size="12" font-weight="600" fill="#191919">{{ etiquette(c.total) }}</text>
            </g>
          }
          <line [attr.x1]="LIB" [attr.x2]="LIB" y1="0" [attr.y2]="hauteur" [attr.stroke]="axe" stroke-width="1" />
        }
      </svg>
      @if (survol >= 0 && cats[survol]) {
        <div class="gr-bulle" [style.left.%]="orientation === 'colonnes' ? ((G + survol * bande + bande / 2) / L) * 100 : 70"
             [style.top.px]="orientation === 'colonnes' ? 0 : null" [style.top.%]="orientation === 'barres' ? (yb(survol) / hauteur) * 100 : null">
          <b>{{ cats[survol].libelle }}</b>
          @for (s of series; track s.cle; let j = $index) {
            @if (cats[survol].v[j]) { <div><i class="gr-pastille" [style.background]="couleurs[j]"></i>{{ s.libelle }} : {{ detail(cats[survol].v[j]) }}</div> }
          }
          <div style="border-top: 1px solid #eee; margin-top: 3px; padding-top: 3px">Total : <b>{{ detail(cats[survol].total) }}</b></div>
        </div>
      }
    </div>`,
  styles: [STYLES_GRAPHE],
})
export class GrapheEmpileComponent implements OnChanges {
  @Input() donnees: { libelle: string; valeurs: Record<string, string | number> }[] = [];
  @Input() series: { cle: string; libelle: string }[] = [];
  @Input() orientation: 'colonnes' | 'barres' = 'colonnes';
  @Input() palette = 'categorielle';
  @Input() unite = 'montant';
  @Input() devise = '';
  @Input() titre = '';
  @Input() L = 1100;
  @Input() H = 280;
  @ViewChild('svg', { static: true }) svg!: ElementRef<SVGSVGElement>;

  readonly G = 56; readonly B = 24;
  get LIB(): number { return this.L < 800 ? 130 : 190; }
  readonly EP = 20; readonly PAS = 34;
  readonly grille = GRILLE; readonly axe = AXE; readonly encre2 = ENCRE2;
  cats: { libelle: string; v: number[]; total: number }[] = [];
  couleurs: string[] = [];
  ticks: number[] = [0, 1];
  max = 1;
  survol = -1;

  ngOnChanges(): void {
    this.cats = (this.donnees ?? []).map(d => {
      const v = this.series.map(s => Number(d.valeurs?.[s.cle]) || 0);
      return { libelle: d.libelle, v, total: v.reduce((a, b) => a + b, 0) };
    });
    this.couleurs = couleursParts(this.palette, this.series.map(s => s.cle));
    this.max = Math.max(...this.cats.map(c => c.total), 0) || 1;
    this.ticks = graduations(this.max);
  }

  get hauteur(): number { return this.orientation === 'colonnes' ? this.H : this.cats.length * this.PAS + 8; }
  get bande(): number { return (this.L - this.G) / Math.max(this.cats.length, 1); }
  yv(v: number): number { const m = this.ticks[this.ticks.length - 1] || 1; return (this.H - this.B) - (v / m) * (this.H - this.B - 12); }
  yb(i: number): number { return 8 + i * this.PAS; }
  largeurH(v: number): number { return (v / this.max) * (this.L - this.LIB - 90); }

  /** Segment j de la colonne i : 2 px de blanc sous chaque segment, arrondi 4 px en haut du dernier */
  segmentV(i: number, j: number): string {
    const c = this.cats[i], v = c.v[j];
    if (v <= 0) return '';
    const w = Math.min(24, this.bande * 0.6), x = this.G + i * this.bande + (this.bande - w) / 2;
    const bas = this.yv(c.v.slice(0, j).reduce((a, b) => a + b, 0)) - (j && c.v.slice(0, j).some(x => x > 0) ? 2 : 0);
    const haut = this.yv(c.v.slice(0, j + 1).reduce((a, b) => a + b, 0));
    const h = Math.max(bas - haut, 1), dernier = !c.v.slice(j + 1).some(x => x > 0), r = dernier ? Math.min(4, w / 2, h) : 0;
    return `M${x},${bas}v-${h - r}a${r},${r} 0 0 1 ${r},-${r}h${w - 2 * r}a${r},${r} 0 0 1 ${r},${r}v${h - r}z`;
  }
  segmentH(i: number, j: number): string {
    const c = this.cats[i], v = c.v[j];
    if (v <= 0) return '';
    const avant = c.v.slice(0, j).reduce((a, b) => a + b, 0);
    const x0 = this.LIB + this.largeurH(avant) + (avant > 0 ? 2 : 0), w = Math.max(this.largeurH(v) - (avant > 0 ? 2 : 0), 1);
    const y = this.yb(i), h = this.EP, dernier = !c.v.slice(j + 1).some(x => x > 0), r = dernier ? Math.min(4, w, h / 2) : 0;
    return `M${x0},${y}h${w - r}a${r},${r} 0 0 1 ${r},${r}v${h - 2 * r}a${r},${r} 0 0 1 -${r},${r}h-${w - r}z`;
  }
  afficher(i: number): boolean { const pas = Math.ceil(this.cats.length / 12); return i % pas === 0; }
  court(t: string): string { return t.length > 26 ? t.slice(0, 25) + '…' : t; }
  etiquette(v: number): string { return compact(v); }
  detail(v: number): string { return this.unite === 'montant' ? `${complet(v)} ${this.devise}` : complet(v); }
}
