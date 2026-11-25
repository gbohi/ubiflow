// Courbe(s) mensuelle(s) : évolution dans le temps, un seul axe. Trait 2 px, point final cerclé,
// voile à 10 % pour une série unique ; survol = repère vertical et valeurs du mois.
import { Component, ElementRef, Input, OnChanges, ViewChild } from '@angular/core';
import { AXE, ENCRE2, GRILLE, SERIES, STYLES_GRAPHE, complet, compact, graduations } from './format';

@Component({
  selector: 'app-graphe-courbe',
  template: `
    @if (series.length > 1) {
      <div class="gr-legende">
        @for (s of series; track s.cle; let j = $index) {
          <span><i class="gr-pastille" [style.background]="couleurs[j]" style="height: 3px; width: 14px; border-radius: 2px"></i>{{ s.libelle }}</span>
        }
      </div>
    }
    <div class="gr-zone" (mousemove)="bouger($event)" (mouseleave)="survol = -1">
      <svg #svg [attr.viewBox]="'0 0 ' + L + ' ' + H" role="img" [attr.aria-label]="titre" xmlns="http://www.w3.org/2000/svg"
           font-family="Poppins, Arial, sans-serif" style="width: 100%; height: auto; display: block">
        @for (t of ticks; track t) {
          <line [attr.x1]="G" [attr.x2]="L - D" [attr.y1]="yv(t)" [attr.y2]="yv(t)" [attr.stroke]="t === 0 ? axe : grille" stroke-width="1" />
          <text [attr.x]="G - 8" [attr.y]="yv(t) + 4" text-anchor="end" font-size="11" [attr.fill]="encre2">{{ etiquette(t) }}</text>
        }
        @for (m of points; track $index; let i = $index) {
          @if (afficherMois(i)) {
            <text [attr.x]="x(i)" [attr.y]="H - 6" text-anchor="middle" font-size="11" [attr.fill]="encre2">{{ m.libelle }}</text>
          }
        }
        @if (survol >= 0) { <line [attr.x1]="x(survol)" [attr.x2]="x(survol)" y1="6" [attr.y2]="H - B" [attr.stroke]="axe" stroke-width="1" /> }
        @if (series.length === 1) { <path [attr.d]="aire(0)" [attr.fill]="couleurs[0]" fill-opacity="0.1" /> }
        @for (s of series; track s.cle; let j = $index) {
          <path [attr.d]="trace(j)" fill="none" [attr.stroke]="couleurs[j]" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
          @if (points.length) {
            <circle [attr.cx]="x(points.length - 1)" [attr.cy]="yv(points[points.length - 1].v[j])" r="4" [attr.fill]="couleurs[j]" stroke="#fff" stroke-width="2" />
          }
          @if (survol >= 0) {
            <circle [attr.cx]="x(survol)" [attr.cy]="yv(points[survol].v[j])" r="5" [attr.fill]="couleurs[j]" stroke="#fff" stroke-width="2" />
          }
        }
        @if (series.length === 1 && points.length) {
          <text [attr.x]="x(points.length - 1) - 8" [attr.y]="yv(points[points.length - 1].v[0]) - 10" text-anchor="end" font-size="11"
                font-weight="600" fill="#191919">{{ etiquette(points[points.length - 1].v[0]) }}</text>
        }
      </svg>
      @if (survol >= 0 && points[survol]) {
        <div class="gr-bulle" [style.left.%]="(x(survol) / L) * 100">
          <b>{{ points[survol].libelle }}</b>
          @for (s of series; track s.cle; let j = $index) {
            <div><i class="gr-pastille" [style.background]="couleurs[j]"></i>{{ s.libelle }} : {{ detail(points[survol].v[j]) }}</div>
          }
        </div>
      }
    </div>`,
  styles: [STYLES_GRAPHE],
})
export class GrapheCourbeComponent implements OnChanges {
  @Input() donnees: { libelle: string; valeurs: Record<string, string | number> }[] = [];
  @Input() series: { cle: string; libelle: string }[] = [];
  @Input() unite = 'montant';
  @Input() devise = '';
  @Input() titre = '';
  @Input() L = 1100;
  @Input() H = 280;
  @ViewChild('svg', { static: true }) svg!: ElementRef<SVGSVGElement>;

  readonly G = 56; readonly B = 24; readonly D = 16;
  readonly couleurs = SERIES; readonly grille = GRILLE; readonly axe = AXE; readonly encre2 = ENCRE2;
  points: { libelle: string; v: number[] }[] = [];
  ticks: number[] = [0, 1];
  survol = -1;

  ngOnChanges(): void {
    this.points = (this.donnees ?? []).map(d => ({ libelle: d.libelle, v: this.series.map(s => Number(d.valeurs?.[s.cle]) || 0) }));
    this.ticks = graduations(Math.max(...this.points.flatMap(p => p.v), 0));
  }

  private get pas(): number { return (this.L - this.G - this.D - 20) / Math.max(this.points.length - 1, 1); }
  x(i: number): number { return this.G + 10 + i * this.pas; }
  yv(v: number): number { const max = this.ticks[this.ticks.length - 1] || 1; return (this.H - this.B) - (v / max) * (this.H - this.B - 14); }
  trace(j: number): string { return this.points.map((p, i) => `${i ? 'L' : 'M'}${this.x(i)},${this.yv(p.v[j])}`).join(''); }
  aire(j: number): string {
    if (!this.points.length) return '';
    return `${this.trace(j)}L${this.x(this.points.length - 1)},${this.H - this.B}L${this.x(0)},${this.H - this.B}Z`;
  }
  bouger(e: MouseEvent): void {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const xs = ((e.clientX - r.left) / r.width) * this.L;
    this.survol = Math.max(0, Math.min(this.points.length - 1, Math.round((xs - this.G - 10) / this.pas)));
  }
  afficherMois(i: number): boolean { const pas = Math.ceil(this.points.length / 12); return i % pas === 0; }
  etiquette(v: number): string { return this.unite === 'jours' ? complet(v, 1) : compact(v); }
  detail(v: number): string {
    if (this.unite === 'montant') return `${complet(v)} ${this.devise}`;
    if (this.unite === 'jours') return `${complet(v, 1)} j`;
    return complet(v);
  }
}
