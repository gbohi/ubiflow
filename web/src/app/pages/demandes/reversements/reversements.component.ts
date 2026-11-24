// src/app/pages/demandes/reversements/reversements.component.ts
//
// Reversements dus par les demandeurs (§8.4) : à percevoir, perçus, abandonnés.
// La comptabilité enregistre la perception ; l'abandon (motivé) est réservé aux
// administrateurs des finances.

import { Component, OnInit, ViewChild, inject } from '@angular/core';
import { ModalDirective } from 'ngx-bootstrap/modal';
import { ToastrService } from 'ngx-toastr';
import { Subject, debounceTime } from 'rxjs';
import {
  MODES_PAIEMENT, ROLES_ADMIN_FINANCES, Reversement, TresorerieService,
} from 'src/app/core/services/tresorerie/tresorerie.service';
import { messageErreur } from 'src/app/core/services/organisation/organisation.service';
import { TokenStorageService } from 'src/app/core/services/token-storage.service';
import { aUnRole } from 'src/app/core/helpers/roles';

@Component({
  selector: 'app-reversements',
  templateUrl: './reversements.component.html',
})
export class ReversementsComponent implements OnInit {
  private readonly service = inject(TresorerieService);
  private readonly toast = inject(ToastrService);

  readonly adminFinances = aUnRole(inject(TokenStorageService).getUser(), ROLES_ADMIN_FINANCES);
  readonly modes = MODES_PAIEMENT;
  readonly aujourdhui = new Date().toISOString().slice(0, 10);
  readonly onglets = [{ cle: 'a_percevoir', libelle: 'À percevoir' }, { cle: 'percu', libelle: 'Perçus' },
                      { cle: 'abandonne', libelle: 'Abandonnés' }];
  etat = 'a_percevoir';
  recherche = '';
  lignes: Reversement[] = [];
  total = 0;
  page = 1;
  chargement = true;
  private readonly recherche$ = new Subject<void>();

  @ViewChild('perceptionModal', { static: false }) perceptionModal?: ModalDirective;
  @ViewChild('abandonModal', { static: false }) abandonModal?: ModalDirective;
  courant: Reversement | null = null;
  perception = { percu_le: '', mode: 'virement', reference: '' };
  justificatif: File | null = null;
  motifAbandon = '';
  enCours = false;

  ngOnInit(): void {
    this.recherche$.pipe(debounceTime(300)).subscribe(() => this.charger(1));
    this.charger();
  }

  charger(page = this.page): void {
    this.page = page;
    this.chargement = true;
    this.service.reversements({ etat: this.etat, search: this.recherche.trim(), page }).subscribe({
      next: r => { this.lignes = r.results; this.total = r.count; this.chargement = false; },
      error: e => { this.chargement = false; this.toast.error(messageErreur(e)); },
    });
  }

  changer(etat: string): void { this.etat = etat; this.charger(1); }
  rechercher(): void { this.recherche$.next(); }

  ouvrirPerception(r: Reversement): void {
    this.courant = r;
    this.perception = { percu_le: this.aujourdhui, mode: 'virement', reference: '' };
    this.justificatif = null;
    this.perceptionModal?.show();
  }

  choisirFichier(e: Event): void { this.justificatif = (e.target as HTMLInputElement).files?.[0] ?? null; }

  percevoir(): void {
    if (!this.courant || this.enCours) return;
    this.enCours = true;
    this.service.percevoir(this.courant.id, this.perception, this.justificatif).subscribe({
      next: () => { this.enCours = false; this.perceptionModal?.hide(); this.toast.success('Reversement enregistré.'); this.charger(); },
      error: e => { this.enCours = false; this.toast.error(messageErreur(e)); },
    });
  }

  ouvrirAbandon(r: Reversement): void { this.courant = r; this.motifAbandon = ''; this.abandonModal?.show(); }

  abandonner(): void {
    if (!this.courant || this.enCours) return;
    this.enCours = true;
    this.service.abandonner(this.courant.id, this.motifAbandon).subscribe({
      next: () => { this.enCours = false; this.abandonModal?.hide(); this.toast.success('Reversement abandonné.'); this.charger(); },
      error: e => { this.enCours = false; this.toast.error(messageErreur(e, (e?.champs?.motif ?? []).join(' ') || 'Refusé.')); },
    });
  }
}
