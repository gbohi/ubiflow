// src/app/pages/demandes/paiement-modal/paiement-modal.component.ts
//
// Saisie d'un règlement (file à payer, fiche de la demande) : montant (reste à
// payer par défaut, imposé si le type ne se paie pas en plusieurs fois), date,
// mode, référence, bénéficiaire, justificatif.

import { Component, EventEmitter, Output, ViewChild, inject } from '@angular/core';
import { ModalDirective } from 'ngx-bootstrap/modal';
import { ToastrService } from 'ngx-toastr';
import { Demande } from 'src/app/core/services/demandes/demandes.service';
import { MODES_PAIEMENT, Reglement, TresorerieService } from 'src/app/core/services/tresorerie/tresorerie.service';
import { messageErreur } from 'src/app/core/services/organisation/organisation.service';

@Component({
  selector: 'app-paiement-modal',
  templateUrl: './paiement-modal.component.html',
})
export class PaiementModalComponent {
  private readonly service = inject(TresorerieService);
  private readonly toast = inject(ToastrService);

  @ViewChild('modal', { static: true }) modal!: ModalDirective;
  @Output() paye = new EventEmitter<Reglement>();

  readonly modes = MODES_PAIEMENT;
  readonly aujourdhui = new Date().toISOString().slice(0, 10);
  demande: Demande | null = null;
  fractionne = true;
  fiche = { montant: null as any, date_paiement: '', mode: 'virement', reference: '', beneficiaire: '' };
  justificatif: File | null = null;
  erreurs: any = null;
  enCours = false;

  get reste(): number {
    const d = this.demande;
    return d ? Number(d.montant_approuve ?? d.montant_demande ?? 0) - Number(d.montant_paye ?? 0) : 0;
  }

  ouvrir(d: Demande, fractionne = true): void {
    this.demande = d;
    this.fractionne = fractionne;
    this.fiche = { montant: this.reste, date_paiement: this.aujourdhui, mode: 'virement', reference: '',
                   beneficiaire: d.demandeur_nom };
    this.justificatif = null;
    this.erreurs = null;
    this.modal.show();
  }

  choisirFichier(e: Event): void { this.justificatif = (e.target as HTMLInputElement).files?.[0] ?? null; }

  enregistrer(): void {
    if (!this.demande || this.enCours) return;
    this.enCours = true;
    this.erreurs = null;
    this.service.payer({ demande: this.demande.id, ...this.fiche }, this.justificatif).subscribe({
      next: r => {
        this.enCours = false;
        this.modal.hide();
        this.toast.success(`Paiement de ${r.montant} ${r.devise} enregistré.`);
        this.paye.emit(r);
      },
      error: e => { this.enCours = false; this.erreurs = e?.champs ?? null; this.toast.error(messageErreur(e, 'Paiement refusé.')); },
    });
  }

  erreur(cle: string): string | null {
    const e = this.erreurs?.[cle];
    return e ? (Array.isArray(e) ? e.join(' ') : String(e)) : null;
  }
}
