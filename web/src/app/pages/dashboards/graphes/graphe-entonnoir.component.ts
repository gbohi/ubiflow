// Entonnoir : progression entre les étapes d'un processus (soumises → approuvées → payées → clôturées).
// Barres centrées, rampe bleue ordonnée (du clair au foncé) ; à droite, part du départ et passage depuis l'étape précédente.
import { Component, ElementRef, Input, OnChanges, ViewChild } from '@angular/core';
import { ENCRE2, RAMPE, STYLES_GRAPHE, complet } from './format';

@Component({
  selector: 'app-graphe-entonnoir',
  template: `
    <div class="gr-zone" (mouseleave)="survol = -1">
      <svg #svg [attr.viewBox]="'0 0 ' + L + ' ' + (etapes.length * PAS + 4)" role="img" [attr.aria-label]="titre" xmlns="http://www.w3.org/2000/svg"
           font-family="Poppins, Arial, sans-serif" style="width: 100%; height: auto; display: block">
        @for (e of etapes; track $index; let i = $index) {
          <g (mouseenter)="survol = i" [attr.opacity]="survol >= 0 && survol !== i ? 0.5 : 1">
            <text x="0" [attr.y]="y(i) + EP / 2 + 5" font-size="13" fill="#191919">{{ e.libelle }}</text>
            <rect [attr.x]="centre - largeur(e.v) / 2" [attr.y]="y(i)" [attr.width]="largeur(e.v)" [attr.height]="EP" rx="4" [attr.fill]="couleur(i)" />
            <text [attr.x]="centre" [attr.y]="y(i) + EP / 2 + 5" text-anchor="middle" font-size="13" font-weight="600"
                  [attr.fill]="i < 2 ? '#0b0b0b' : '#fff'">{{ complet(e.v) }}</text>
            <text [attr.x]="L" [attr.y]="y(i) + EP / 2 - 1" text-anchor="end" font-size="12" font-weight="600" fill="#191919">{{ part(i) }}</text>
            @if (i > 0) {
              <text [attr.x]="L" [attr.y]="y(i) + EP / 2 + 13" text-anchor="end" font-size="11" [attr.fill]="encre2">{{ passage(i) }}</text>
            } @else {
              <text [attr.x]="L" [attr.y]="y(i) + EP / 2 + 13" text-anchor="end" font-size="11" [attr.fill]="encre2">point de départ</text>
            }
          </g>
        }
      </svg>
    </div>`,
  styles: [STYLES_GRAPHE],
})
export class GrapheEntonnoirComponent implements OnChanges {
  @Input() donnees: { libelle: string; valeur: string | number }[] = [];
  @Input() titre = '';
  @ViewChild('svg', { static: true }) svg!: ElementRef<SVGSVGElement>;

  readonly L = 640; readonly PAS = 58; readonly EP = 36; readonly LIB = 120; readonly DROITE = 150;
  readonly encre2 = ENCRE2; readonly complet = complet;
  etapes: { libelle: string; v: number }[] = [];
  survol = -1;

  ngOnChanges(): void { this.etapes = (this.donnees ?? []).map(d => ({ libelle: d.libelle, v: Number(d.valeur) || 0 })); }

  get centre(): number { return this.LIB + (this.L - this.LIB - this.DROITE) / 2; }
  y(i: number): number { return 4 + i * this.PAS; }
  largeur(v: number): number {
    const max = this.etapes[0]?.v || 1, plein = this.L - this.LIB - this.DROITE;
    return Math.max((v / max) * plein, v > 0 ? 44 : 2);
  }
  couleur(i: number): string { return RAMPE[Math.min(i, RAMPE.length - 1)]; }
  part(i: number): string { const d = this.etapes[0]?.v; return d ? `${Math.round((100 * this.etapes[i].v) / d)} % du départ` : ''; }
  passage(i: number): string {
    const p = this.etapes[i - 1]?.v;
    return p ? `${Math.round((100 * this.etapes[i].v) / p)} % de l'étape précédente` : '—';
  }
}
