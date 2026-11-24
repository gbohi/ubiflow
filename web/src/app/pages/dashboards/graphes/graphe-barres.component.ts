// Barres horizontales classées (une teinte) : libellé, barre, valeur au bout ; survol = détail.
import { Component, ElementRef, Input, OnChanges, ViewChild } from '@angular/core';
import { BARRE, complet, compact } from './format';

@Component({
  selector: 'app-graphe-barres',
  template: `
    <div class="gr-zone" (mouseleave)="survol = -1">
      <svg #svg [attr.viewBox]="'0 0 ' + L + ' ' + H" role="img" [attr.aria-label]="titre" xmlns="http://www.w3.org/2000/svg"
           font-family="Poppins, Arial, sans-serif" style="width: 100%; height: auto; display: block">
        @for (d of lignes; track $index; let i = $index) {
          <g (mouseenter)="survol = i" [attr.opacity]="survol >= 0 && survol !== i ? 0.45 : 1" style="cursor: default">
            <rect x="0" [attr.y]="y(i) - 4" [attr.width]="L" [attr.height]="PAS" fill="transparent" />
            <text [attr.x]="LIB - 8" [attr.y]="y(i) + EP / 2 + 4" text-anchor="end" font-size="11" fill="#52514e">{{ court(d.libelle) }}</text>
            <path [attr.d]="barre(d.v)" [attr.fill]="couleur" [attr.transform]="'translate(0,' + y(i) + ')'" />
            <text [attr.x]="LIB + largeur(d.v) + 6" [attr.y]="y(i) + EP / 2 + 4" font-size="11" fill="#0b0b0b" font-weight="600">{{ etiquette(d.v) }}</text>
          </g>
        }
        <line [attr.x1]="LIB" [attr.x2]="LIB" y1="0" [attr.y2]="H" stroke="#e4e3df" stroke-width="1" />
      </svg>
      @if (survol >= 0 && lignes[survol]) {
        <div class="gr-bulle" [style.top.%]="(y(survol) / H) * 100">
          <b>{{ lignes[survol].libelle }}</b><br>{{ detail(lignes[survol].v) }}
        </div>
      }
    </div>`,
  styles: [`.gr-zone { position: relative; } .gr-bulle { position: absolute; right: 0; transform: translateY(-110%); background: #fff;
    border: 1px solid #e4e3df; border-radius: 6px; padding: 4px 8px; font-size: 12px; box-shadow: 0 2px 6px rgba(0,0,0,.08);
    pointer-events: none; white-space: nowrap; z-index: 2; }`],
})
export class GrapheBarresComponent implements OnChanges {
  @Input() donnees: { libelle: string; valeur: string | number }[] = [];
  @Input() unite = 'montant';
  @Input() devise = '';
  @Input() titre = '';
  /** Largeur logique du dessin : plus petite = texte plus grand dans un conteneur étroit. */
  @Input() L = 640;
  @Input() LIB = 170;
  @ViewChild('svg', { static: true }) svg!: ElementRef<SVGSVGElement>;

  readonly EP = 14; readonly PAS = 26;
  readonly couleur = BARRE;
  lignes: { libelle: string; v: number }[] = [];
  max = 1;
  survol = -1;

  get H(): number { return Math.max(this.lignes.length * this.PAS, this.PAS); }

  ngOnChanges(): void {
    this.lignes = (this.donnees ?? []).map(d => ({ libelle: d.libelle, v: Number(d.valeur) || 0 }));
    this.max = Math.max(...this.lignes.map(l => l.v), 1);
  }

  y(i: number): number { return i * this.PAS + 6; }
  largeur(v: number): number { return v <= 0 ? 0 : Math.max(2, (v / this.max) * (this.L - this.LIB - 90)); }
  /** Barre : départ carré sur la ligne de base, bout arrondi (4 px) */
  barre(v: number): string {
    const w = this.largeur(v), h = this.EP, r = Math.min(4, w / 2, h / 2), x = this.LIB, y0 = 0;
    if (w <= 0) return '';
    return `M${x},${y0} h${w - r} a${r},${r} 0 0 1 ${r},${r} v${h - 2 * r} a${r},${r} 0 0 1 -${r},${r} h-${w - r} z`;
  }
  court(t: string): string { return t.length > 26 ? t.slice(0, 25) + '…' : t; }
  etiquette(v: number): string { return this.unite === 'montant' ? compact(v) : complet(v); }
  detail(v: number): string { return this.unite === 'montant' ? `${complet(v)} ${this.devise}` : complet(v); }
}
