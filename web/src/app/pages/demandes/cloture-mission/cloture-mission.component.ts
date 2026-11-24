// src/app/pages/demandes/cloture-mission/cloture-mission.component.ts
//
// Clôture d'une mission (§9, mode B) : dates réelles, dépenses réelles par
// rubrique de la note de frais, observations, pièces de clôture ; récapitulatif
// recalculé par le serveur (brouillon enregistré automatiquement) ; contrôle.

import { Component, DestroyRef, EventEmitter, Input, OnChanges, Output, ViewChild, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ModalDirective } from 'ngx-bootstrap/modal';
import { ToastrService } from 'ngx-toastr';
import { Subject, debounceTime, switchMap, catchError, of } from 'rxjs';
import { Cloture, Demande, DemandesService } from 'src/app/core/services/demandes/demandes.service';
import { messageErreur } from 'src/app/core/services/organisation/organisation.service';

export const RUBRIQUES_CLOTURE = [
  { cle: 'hotel', libelle: "Frais d'hôtel", aide: 'Petit déjeuner compris' },
  { cle: 'transport', libelle: 'Transport', aide: 'Location de véhicule, taxis' },
  { cle: 'telephone', libelle: 'Frais de téléphone', aide: '' },
  { cle: 'divers', libelle: 'Divers', aide: 'Précisez ci-dessous', detail: 'divers_detail' },
  { cle: 'reception', libelle: 'Réception', aide: '' },
  { cle: 'detaxe', libelle: 'Détaxe (à reverser)', aide: 'Taxes remboursées à l’étranger : déduites' },
  { cle: 'a_refacturer', libelle: 'Autres frais à refacturer', aide: 'Précisez ci-dessous', detail: 'a_refacturer_detail' },
];

@Component({
  selector: 'app-cloture-mission',
  templateUrl: './cloture-mission.component.html',
})
export class ClotureMissionComponent implements OnChanges {
  private readonly service = inject(DemandesService);
  private readonly toast = inject(ToastrService);
  private readonly destroyRef = inject(DestroyRef);

  @Input({ required: true }) demande!: Demande;
  @Output() modifiee = new EventEmitter<void>();
  @ViewChild('retourModal', { static: false }) retourModal?: ModalDirective;

  readonly rubriques = RUBRIQUES_CLOTURE;
  cloture: Cloture | null = null;
  saisie = { depart_reel: '', retour_reel: '', observations: '', depenses: {} as Record<string, any> };
  erreurs: any = null;
  enCours = false;
  sauvegarde = false;
  motifRetour = '';
  private readonly sauver$ = new Subject<void>();

  constructor() {
    this.sauver$.pipe(
      debounceTime(700),
      switchMap(() => { this.sauvegarde = true; return this.service.enregistrerCloture(this.demande.id, this.charge()).pipe(catchError(e => { this.erreurs = e?.champs ?? null; return of(null); })); }),
      takeUntilDestroyed(this.destroyRef),
    ).subscribe(c => { this.sauvegarde = false; if (c) { this.erreurs = null; this.cloture = { ...c }; } });
  }

  ngOnChanges(): void {
    const c = this.demande?.cloture;
    if (!c) return;
    this.cloture = c;
    this.saisie = { depart_reel: c.depart_reel ?? '', retour_reel: c.retour_reel ?? '', observations: c.observations ?? '',
                    depenses: { ...(c.depenses ?? {}) } };
    if (!this.saisie.depart_reel && this.demande.mission?.depart_le) this.saisie.depart_reel = String(this.demande.mission.depart_le).slice(0, 10);
    if (!this.saisie.retour_reel && this.demande.mission?.retour_le) this.saisie.retour_reel = String(this.demande.mission.retour_le).slice(0, 10);
  }

  get modifiable(): boolean { return !!this.cloture?.actions.modifier; }
  get calcul(): Record<string, any> { return this.cloture?.calcul ?? {}; }
  get devise(): string { return this.calcul['devise'] || this.demande.devise; }

  private charge() {
    const depenses: Record<string, any> = {};
    for (const r of this.rubriques) {
      depenses[r.cle] = this.saisie.depenses[r.cle] || 0;
      if (r.detail) depenses[r.detail] = this.saisie.depenses[r.detail] || '';
    }
    return { depart_reel: this.saisie.depart_reel || null, retour_reel: this.saisie.retour_reel || null,
             observations: this.saisie.observations, depenses } as any;
  }

  modifier(): void { if (this.modifiable) this.sauver$.next(); }

  soumettre(): void {
    if (this.enCours) return;
    if (!confirm('Soumettre les éléments de clôture ? Ils ne seront plus modifiables, sauf retour du contrôleur.')) return;
    this.enCours = true;
    this.service.enregistrerCloture(this.demande.id, this.charge()).subscribe({
      next: () => this.service.actionCloture(this.demande.id, 'soumettre').subscribe({
        next: () => { this.enCours = false; this.toast.success('Éléments de clôture soumis.'); this.modifiee.emit(); },
        error: e => this.echec(e),
      }),
      error: e => this.echec(e),
    });
  }

  valider(): void {
    if (this.enCours || !confirm('Valider la clôture ? Les dépenses déclarées seront retenues.')) return;
    this.enCours = true;
    this.service.actionCloture(this.demande.id, 'valider').subscribe({
      next: () => { this.enCours = false; this.toast.success('Clôture validée.'); this.modifiee.emit(); },
      error: e => this.echec(e),
    });
  }

  retourner(): void {
    if (this.enCours) return;
    this.enCours = true;
    this.service.actionCloture(this.demande.id, 'retourner', this.motifRetour).subscribe({
      next: () => { this.enCours = false; this.retourModal?.hide(); this.toast.success('Éléments retournés au demandeur.'); this.modifiee.emit(); },
      error: e => this.echec(e),
    });
  }

  private echec(e: any): void {
    this.enCours = false;
    this.erreurs = e?.champs ?? null;
    const docs = e?.champs?.documents;
    this.toast.error(docs ? (Array.isArray(docs) ? docs.join(' ') : String(docs)) : messageErreur(e, 'Vérifiez les éléments de clôture.'));
  }

  erreur(cle: string): string | null {
    const e = this.erreurs?.[cle];
    return e ? (Array.isArray(e) ? e.join(' ') : String(e)) : null;
  }
}
