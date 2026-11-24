// src/app/shared/numerotation/numerotation.directive.ts
import { AfterViewInit, Directive, ElementRef, Input, OnChanges, OnDestroy } from '@angular/core';

/**
 * Numérotation des lignes de toutes les listes : s'applique d'office à chaque
 * `<table class="lst-table">` (colonne « N° » ajoutée en tête). Pour une liste
 * paginée, indiquer le numéro de la première ligne de la page :
 *
 *   <table class="lst-table" [numeroDebut]="(page - 1) * 10 + 1">
 *
 * `sansNumero` désactive la colonne sur un tableau particulier ; un tableau qui
 * a déjà sa colonne `th.lst-c-num` n'est pas modifié.
 */
@Directive({ selector: 'table.lst-table' })
export class NumerotationDirective implements AfterViewInit, OnChanges, OnDestroy {
  @Input() numeroDebut = 1;
  @Input() sansNumero: boolean | '' = false;

  private observateur?: MutationObserver;
  private pret = false;

  constructor(private readonly el: ElementRef<HTMLTableElement>) {}

  private get actif(): boolean { return this.sansNumero === false; }

  ngAfterViewInit(): void {
    const table = this.el.nativeElement;
    // Liste déjà numérotée par son gabarit (colonne « lst-c-num » écrite à la main) : rien à faire
    if (!this.actif || table.querySelector('thead th.lst-c-num')) return;
    const entete = table.tHead?.rows[0];
    if (entete) {
      const th = document.createElement('th');
      th.className = 'lst-c-num';
      th.textContent = 'N°';
      entete.insertBefore(th, entete.firstChild);
    }
    this.observateur = new MutationObserver(() => this.numeroter());
    for (const corps of Array.from(table.tBodies)) this.observateur.observe(corps, { childList: true });
    this.pret = true;
    this.numeroter();
  }

  ngOnChanges(): void { if (this.pret) this.numeroter(); }

  ngOnDestroy(): void { this.observateur?.disconnect(); }

  private numeroter(): void {
    let n = Number(this.numeroDebut) || 1;
    for (const corps of Array.from(this.el.nativeElement.tBodies)) {
      for (const ligne of Array.from(corps.rows)) {
        const cellules = Array.from(ligne.cells);
        // Ligne « aucun résultat » ou de chargement : une seule cellule sur toute la largeur
        if (cellules.length === 1 && cellules[0].colSpan > 1) {
          if (!cellules[0].dataset['numColspan']) {
            cellules[0].colSpan += 1;
            cellules[0].dataset['numColspan'] = '1';
          }
          continue;
        }
        let cellule = cellules[0]?.classList.contains('lst-c-num') ? cellules[0] : null;
        if (!cellule) {
          cellule = document.createElement('td');
          cellule.className = 'lst-c-num';
          cellule.dataset['label'] = 'N°';
          ligne.insertBefore(cellule, ligne.firstChild);
        }
        cellule.textContent = String(n++);
      }
    }
  }
}
