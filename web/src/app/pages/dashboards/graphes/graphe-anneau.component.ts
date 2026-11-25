// Anneau : répartition d'un total en quelques parts (6 au plus, le reste en « Autres » côté serveur).
// Total au centre, légende à côté avec valeur et part ; 2 px de blanc entre les parts ; survol = détail.
import { Component, ElementRef, Input, OnChanges, ViewChild } from '@angular/core';
import { STYLES_GRAPHE, complet, compact, couleursParts } from './format';

@Component({
  selector: 'app-graphe-anneau',
  template: `
    <div class="an-boite">
      <div class="gr-zone an-dessin">
        <svg #svg viewBox="0 0 220 220" role="img" [attr.aria-label]="titre" xmlns="http://www.w3.org/2000/svg"
             font-family="Poppins, Arial, sans-serif" style="width: 100%; height: auto; display: block">
          @for (p of parts; track p.cle; let i = $index) {
            <path [attr.d]="arc(i)" [attr.fill]="couleurs[i]" stroke="#fff" stroke-width="2" stroke-linejoin="round"
                  [attr.opacity]="survol >= 0 && survol !== i ? 0.35 : 1" (mouseenter)="survol = i" (mouseleave)="survol = -1" />
          }
          <text x="110" y="106" text-anchor="middle" font-size="22" font-weight="600" fill="#191919">{{ centre }}</text>
          <text x="110" y="128" text-anchor="middle" font-size="11" fill="#5b6470">{{ sousCentre }}</text>
        </svg>
      </div>
      <ul class="an-legende">
        @for (p of parts; track p.cle; let i = $index) {
          <li [class.estompe]="survol >= 0 && survol !== i" (mouseenter)="survol = i" (mouseleave)="survol = -1">
            <i class="gr-pastille" [style.background]="couleurs[i]"></i>
            <span class="an-lib">{{ p.libelle }}</span>
            <span class="an-val">{{ detail(p.v) }}</span>
            <span class="an-pct">{{ pourcent(p.v) }}</span>
          </li>
        }
      </ul>
    </div>`,
  styles: [STYLES_GRAPHE, `
    .an-boite { display: flex; align-items: center; gap: 20px; flex-wrap: wrap; }
    .an-dessin { width: 190px; flex: none; }
    .an-legende { list-style: none; padding: 0; margin: 0; flex: 1 1 200px; font-size: 13px; }
    .an-legende li { display: flex; align-items: center; gap: 4px; padding: 5px 0; border-bottom: 1px solid #f0f1f3; cursor: default; }
    .an-legende li:last-child { border-bottom: 0; }
    .an-legende li.estompe { opacity: .45; }
    .an-lib { flex: 1; color: #191919; }
    .an-val { font-weight: 600; color: #191919; white-space: nowrap; }
    .an-pct { width: 46px; text-align: right; color: #5b6470; font-size: 12px; }`],
})
export class GrapheAnneauComponent implements OnChanges {
  @Input() donnees: { cle?: string; libelle: string; valeur: string | number; teinte?: number }[] = [];
  @Input() palette = 'categorielle';
  @Input() unite = 'nombre';
  @Input() devise = '';
  @Input() titre = '';
  @ViewChild('svg', { static: true }) svg!: ElementRef<SVGSVGElement>;

  parts: { cle: string; libelle: string; v: number; teinte?: number }[] = [];
  couleurs: string[] = [];
  total = 0;
  survol = -1;

  ngOnChanges(): void {
    this.parts = (this.donnees ?? []).map((d, i) => ({ cle: d.cle ?? String(i), libelle: d.libelle, v: Number(d.valeur) || 0, teinte: d.teinte }))
      .filter(p => p.v > 0);
    this.couleurs = couleursParts(this.palette, this.parts.map(p => p.cle), this.parts.map(p => p.teinte));
    this.total = this.parts.reduce((s, p) => s + p.v, 0);
  }

  get centre(): string { return this.unite === 'montant' ? compact(this.total) : complet(this.total); }
  get sousCentre(): string { return this.unite === 'montant' ? `${this.devise} au total` : 'au total'; }

  /** Arc de la part i (anneau 64 → 100 de rayon autour de 110,110) */
  arc(i: number): string {
    const avant = this.parts.slice(0, i).reduce((s, p) => s + p.v, 0);
    const a0 = (avant / this.total) * 2 * Math.PI - Math.PI / 2;
    let a1 = ((avant + this.parts[i].v) / this.total) * 2 * Math.PI - Math.PI / 2;
    if (this.parts.length === 1) a1 -= 0.0001;
    const R = 100, r = 64, c = 110, grand = a1 - a0 > Math.PI ? 1 : 0;
    const p = (rad: number, a: number) => `${c + rad * Math.cos(a)},${c + rad * Math.sin(a)}`;
    return `M${p(R, a0)}A${R},${R} 0 ${grand} 1 ${p(R, a1)}L${p(r, a1)}A${r},${r} 0 ${grand} 0 ${p(r, a0)}Z`;
  }
  pourcent(v: number): string { return this.total ? `${Math.round((100 * v) / this.total)} %` : ''; }
  detail(v: number): string { return this.unite === 'montant' ? `${complet(v)} ${this.devise}` : complet(v); }
}
