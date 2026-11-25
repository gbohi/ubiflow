// Colonnes mensuelles groupées (une à trois séries, un seul axe), légende, survol = valeurs du mois.
import { Component, ElementRef, Input, OnChanges, ViewChild } from '@angular/core';
import { SERIES, complet, compact, graduations } from './format';

@Component({
  selector: 'app-graphe-colonnes',
  template: `
    @if (series.length > 1) {
      <div class="d-flex flex-wrap gap-3 small mb-1 gr-legende">
        @for (s of series; track s.cle; let i = $index) {
          <span><i class="gr-pastille" [style.background]="couleurs[i]"></i>{{ s.libelle }}</span>
        }
      </div>
    }
    <div class="gr-zone" (mouseleave)="survol = -1">
      <svg #svg [attr.viewBox]="'0 0 ' + L + ' ' + H" role="img" [attr.aria-label]="titre" xmlns="http://www.w3.org/2000/svg"
           font-family="Poppins, Arial, sans-serif" style="width: 100%; height: auto; display: block">
        @for (t of ticks; track t) {
          <line [attr.x1]="G" [attr.x2]="L" [attr.y1]="yv(t)" [attr.y2]="yv(t)" stroke="#e4e3df" stroke-width="1" />
          <text [attr.x]="G - 6" [attr.y]="yv(t) + 4" text-anchor="end" font-size="10" fill="#52514e">{{ etiquette(t) }}</text>
        }
        @for (m of mois; track $index; let i = $index) {
          <g (mouseenter)="survol = i">
            <rect [attr.x]="G + i * groupe" y="0" [attr.width]="groupe" [attr.height]="H - B" [attr.fill]="survol === i ? '#f1f0ec' : 'transparent'" />
            @for (s of series; track s.cle; let j = $index) {
              <path [attr.d]="colonne(i, j, m.v[j])" [attr.fill]="couleurs[j]" />
            }
            @if (afficherMois(i)) {
              @if (etiquettesLongues) {
                <text [attr.x]="G + i * groupe + groupe / 2" [attr.y]="H - B + 14" text-anchor="middle" font-size="10" fill="#52514e">
                  @for (ligne of lignesEtiquette(m.libelle); track $index; let k = $index) {
                    <tspan [attr.x]="G + i * groupe + groupe / 2" [attr.dy]="k ? 13 : 0">{{ ligne }}</tspan>
                  }
                </text>
              } @else {
                <text [attr.x]="G + i * groupe + groupe / 2" [attr.y]="H - 6" text-anchor="middle" font-size="10" fill="#52514e">{{ m.libelle }}</text>
              }
            }
          </g>
        }
        <line [attr.x1]="G" [attr.x2]="L" [attr.y1]="H - B" [attr.y2]="H - B" stroke="#c9c8c2" stroke-width="1" />
      </svg>
      @if (survol >= 0 && mois[survol]) {
        <div class="gr-bulle" [style.left.%]="((G + survol * groupe + groupe / 2) / L) * 100">
          <b>{{ mois[survol].libelle }}</b>
          @for (s of series; track s.cle; let j = $index) {
            <div><i class="gr-pastille" [style.background]="couleurs[j]"></i>{{ s.libelle }} : {{ detail(mois[survol].v[j]) }}</div>
          }
        </div>
      }
    </div>`,
  styles: [`.gr-zone { position: relative; } .gr-pastille { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; }
    .gr-legende { color: #52514e; }
    .gr-bulle { position: absolute; top: 0; transform: translateX(-50%); background: #fff; border: 1px solid #e4e3df; border-radius: 6px;
      padding: 4px 8px; font-size: 12px; box-shadow: 0 2px 6px rgba(0,0,0,.08); pointer-events: none; white-space: nowrap; z-index: 2; }`],
})
export class GrapheColonnesComponent implements OnChanges {
  @Input() donnees: { libelle: string; valeurs: Record<string, string | number> }[] = [];
  @Input() series: { cle: string; libelle: string }[] = [];
  @Input() unite = 'montant';
  @Input() devise = '';
  @Input() titre = '';
  @Input() L = 1100;
  @Input() H = 280;
  /** Libellés de catégories (types de demande…) : sur deux lignes, sans saut de libellé */
  @Input() etiquettesLongues = false;
  @ViewChild('svg', { static: true }) svg!: ElementRef<SVGSVGElement>;

  readonly G = 52;
  get B(): number { return this.etiquettesLongues ? 40 : 22; }
  readonly couleurs = SERIES;
  mois: { libelle: string; v: number[] }[] = [];
  ticks: number[] = [0, 1];
  survol = -1;

  get groupe(): number { return (this.L - this.G) / Math.max(this.mois.length, 1); }

  ngOnChanges(): void {
    this.mois = (this.donnees ?? []).map(d => ({ libelle: d.libelle, v: this.series.map(s => Number(d.valeurs?.[s.cle]) || 0) }));
    this.ticks = graduations(Math.max(...this.mois.flatMap(m => m.v), 0));
  }

  yv(v: number): number { const max = this.ticks[this.ticks.length - 1] || 1; return (this.H - this.B) - (v / max) * (this.H - this.B - 10); }

  /** Colonne : largeur ≤ 24 px, 2 px d'écart entre colonnes voisines, sommet arrondi (4 px), base carrée */
  colonne(i: number, j: number, v: number): string {
    if (v <= 0) return '';
    const n = this.series.length;
    const w = Math.min(24, (this.groupe * 0.7 - (n - 1) * 2) / n);
    const x = this.G + i * this.groupe + (this.groupe - (n * w + (n - 1) * 2)) / 2 + j * (w + 2);
    const y = this.yv(v), base = this.H - this.B, h = Math.max(base - y, 1), r = Math.min(4, w / 2, h);
    return `M${x},${base} v-${h - r} a${r},${r} 0 0 1 ${r},-${r} h${w - 2 * r} a${r},${r} 0 0 1 ${r},${r} v${h - r} z`;
  }
  afficherMois(i: number): boolean { return this.etiquettesLongues || i % Math.ceil(this.mois.length / 12) === 0; }
  /** Coupe un libellé en deux lignes au plus, aux espaces, en abrégeant si besoin */
  lignesEtiquette(t: string): string[] {
    const max = Math.max(8, Math.floor(this.groupe / 5.8));
    if (t.length <= max) return [t];
    const mots = t.split(' '); let l1 = '';
    while (mots.length && (l1 + ' ' + mots[0]).trim().length <= max) l1 = (l1 + ' ' + mots.shift()).trim();
    let l2 = mots.join(' ');
    if (l2.length > max) l2 = l2.slice(0, max - 1) + '…';
    return l1 ? [l1, l2] : [t.slice(0, max - 1) + '…'];
  }
  etiquette(v: number): string { return compact(v); }
  detail(v: number): string { return this.unite === 'montant' ? `${complet(v)} ${this.devise}` : complet(v); }
}
