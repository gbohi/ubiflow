// src/app/layouts/recherche-globale/recherche-globale.component.ts
//
// Recherche globale de la barre du haut : référence, objet ou demandeur.
// Résultats limités aux demandes que l'utilisateur a le droit de voir
// (contrôle fait par le serveur). Raccourci « / », navigation au clavier.

import { Component, DestroyRef, ElementRef, HostListener, ViewChild, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { Subject, of } from 'rxjs';
import { catchError, debounceTime, distinctUntilChanged, switchMap, tap } from 'rxjs/operators';
import { CLASSES_STATUT, formaterMontant, iconeType, teinteType } from 'src/app/core/services/demandes/demandes.service';
import { PilotageService, ResultatRecherche } from 'src/app/core/services/pilotage/pilotage.service';

@Component({
  selector: 'app-recherche-globale',
  template: `
    <div class="rg" [class.ouverte]="ouverte">
      <i class="ri-search-line rg-loupe"></i>
      <input #champ type="search" class="rg-champ" [value]="terme" (input)="saisir(champ.value)" (focus)="ouvrir()"
             (keydown)="clavier($event)" placeholder="Rechercher une demande, une référence, un nom…"
             role="combobox" aria-label="Rechercher une demande" [attr.aria-expanded]="ouverte" aria-controls="rg-liste" autocomplete="off">
      @if (!terme) { <kbd class="rg-kbd">/</kbd> }
      @if (ouverte && terme.trim().length >= 2) {
        <div class="rg-panneau" id="rg-liste" role="listbox">
          @if (chargement && !resultats.length) {
            <div class="rg-info"><span class="spinner-border spinner-border-sm me-2"></span>Recherche…</div>
          } @else if (!resultats.length) {
            <div class="rg-info">Aucune demande ne correspond à « {{ terme.trim() }} ».</div>
          } @else {
            <div class="rg-titre">Demandes · {{ total }} résultat{{ total > 1 ? 's' : '' }}</div>
            @for (r of resultats; track r.id; let i = $index) {
              <a class="rg-ligne" role="option" [class.active]="i === actif" [attr.aria-selected]="i === actif"
                 (mousedown)="$event.preventDefault()" (click)="aller(r)" (mouseenter)="actif = i">
                <span class="lst-av carre" [ngClass]="teinte(r.type_code)"><i [class]="icone(r.type_icone)"></i></span>
                <span class="rg-texte">
                  <span class="rg-objet">{{ r.objet || '(sans objet)' }}</span>
                  <span class="rg-sous">{{ r.reference }} · {{ r.type }} · {{ r.demandeur }}</span>
                </span>
                <span class="rg-fin">
                  <span class="lst-tag" [ngClass]="classe(r.statut)">{{ r.statut_libelle }}</span>
                  @if (r.montant) { <span class="rg-montant">{{ montant(r.montant, r.devise) }}</span> }
                </span>
              </a>
            }
            @if (total > resultats.length) {
              <div class="rg-info">Précisez votre recherche pour voir les {{ total - resultats.length }} autres résultats.</div>
            }
          }
        </div>
      }
    </div>`,
  styles: [`
    :host { display: block; flex: 1; max-width: 460px; margin-left: 12px; }
    .rg { position: relative; }
    .rg-loupe { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: #8A97A6; font-size: 16px; }
    .rg-champ { width: 100%; height: 38px; border: 1px solid #E3E8EF; border-radius: 10px; padding: 0 38px 0 36px; font-size: 13px;
                background: #fff; color: #05253E; outline: none; }
    .rg-champ:focus { border-color: #9FB2C6; box-shadow: 0 0 0 3px rgba(5, 37, 62, .06); }
    .rg-kbd { position: absolute; right: 10px; top: 50%; transform: translateY(-50%); font-size: 11px; color: #5B6B7D;
              background: #F1F4F8; border: 1px solid #E3E8EF; border-radius: 5px; padding: 1px 6px; box-shadow: none; }
    .rg-panneau { position: absolute; top: 44px; left: 0; right: 0; min-width: 520px; background: #fff; border: 1px solid #E3E8EF;
                  border-radius: 12px; box-shadow: 0 12px 32px rgba(5, 37, 62, .14); padding: 6px; z-index: 1100; }
    .rg-titre { font-size: 11px; text-transform: uppercase; letter-spacing: .8px; color: #8A97A6; padding: 8px 10px 4px; font-weight: 600; }
    .rg-info { padding: 12px; font-size: 13px; color: #5B6B7D; }
    .rg-ligne { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border-radius: 8px; cursor: pointer; color: #0E1E2E; }
    .rg-ligne.active { background: #F2F5F9; }
    .rg-texte { flex: 1; min-width: 0; display: flex; flex-direction: column; }
    .rg-objet { font-weight: 600; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .rg-sous { font-size: 11.5px; color: #5B6B7D; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .rg-fin { display: flex; flex-direction: column; align-items: flex-end; gap: 3px; }
    .rg-montant { font-size: 12px; font-weight: 600; white-space: nowrap; }
    @media (max-width: 991.98px) { :host { max-width: 260px; } .rg-panneau { min-width: 0; } .rg-kbd { display: none; } }
  `],
})
export class RechercheGlobaleComponent {
  private readonly service = inject(PilotageService);
  private readonly router = inject(Router);
  private readonly hote = inject(ElementRef);
  private readonly destroyRef = inject(DestroyRef);
  @ViewChild('champ', { static: true }) champ!: ElementRef<HTMLInputElement>;

  terme = '';
  resultats: ResultatRecherche[] = [];
  total = 0;
  actif = 0;
  ouverte = false;
  chargement = false;
  private readonly saisie$ = new Subject<string>();

  readonly icone = iconeType;
  readonly teinte = (code: string) => teinteType(code);
  readonly montant = formaterMontant;
  classe(statut: string): string { return CLASSES_STATUT[statut] ?? ''; }

  constructor() {
    this.saisie$.pipe(
      debounceTime(250),
      distinctUntilChanged(),
      tap(() => this.chargement = true),
      switchMap(q => q.length < 2 ? of({ total: 0, demandes: [] })
        : this.service.rechercher(q).pipe(catchError(() => of({ total: 0, demandes: [] })))),
      takeUntilDestroyed(this.destroyRef),
    ).subscribe(r => { this.resultats = r.demandes; this.total = r.total; this.actif = 0; this.chargement = false; });
  }

  saisir(v: string): void { this.terme = v; this.ouverte = true; this.saisie$.next(v.trim()); }
  ouvrir(): void { this.ouverte = true; }

  aller(r: ResultatRecherche): void {
    this.ouverte = false;
    this.terme = '';
    this.resultats = [];
    this.saisie$.next('');
    this.champ.nativeElement.blur();
    this.router.navigate(['/demandes', r.id]);
  }

  clavier(e: KeyboardEvent): void {
    if (e.key === 'ArrowDown') { this.actif = Math.min(this.actif + 1, this.resultats.length - 1); e.preventDefault(); }
    else if (e.key === 'ArrowUp') { this.actif = Math.max(this.actif - 1, 0); e.preventDefault(); }
    else if (e.key === 'Enter' && this.resultats[this.actif]) { this.aller(this.resultats[this.actif]); e.preventDefault(); }
    else if (e.key === 'Escape') { this.ouverte = false; this.champ.nativeElement.blur(); }
  }

  /** « / » place le curseur dans la recherche (hors champs de saisie) */
  @HostListener('document:keydown', ['$event'])
  raccourci(e: KeyboardEvent): void {
    const cible = e.target as HTMLElement;
    if (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(cible?.tagName) && !cible?.isContentEditable) {
      e.preventDefault();
      this.champ.nativeElement.focus();
    }
  }

  @HostListener('document:click', ['$event'])
  clicExterieur(e: MouseEvent): void {
    if (!this.hote.nativeElement.contains(e.target)) this.ouverte = false;
  }
}
