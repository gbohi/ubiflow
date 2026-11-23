// src/app/pages/parametres/journal/journal.component.ts
//
// Journal d'activité : opérations de paramétrage, délégations, réaffectations,
// retraits de pièces… (administrateurs et contrôleurs).

import { Component, OnInit, inject } from '@angular/core';
import { ToastrService } from 'ngx-toastr';
import { DemandesService } from 'src/app/core/services/demandes/demandes.service';
import { messageErreur } from 'src/app/core/services/organisation/organisation.service';

@Component({
  selector: 'app-journal',
  templateUrl: './journal.component.html',
})
export class JournalComponent implements OnInit {
  private readonly service = inject(DemandesService);
  private readonly toast = inject(ToastrService);

  lignes: any[] = [];
  total = 0;
  page = 1;
  filtres = { du: '', au: '', action: '', search: '' };
  detail: any = null;
  chargement = false;

  readonly libelles: Record<string, string> = {
    'parametrage.creation': 'Paramétrage — création', 'parametrage.modification': 'Paramétrage — modification',
    'parametrage.suppression': 'Paramétrage — suppression', 'workflow.version_creee': 'Circuit — nouvelle version',
    'workflow.publication': 'Circuit — publication', 'workflow.brouillon_supprime': 'Circuit — brouillon supprimé',
    'workflow.reaffectation': 'Validation réaffectée', 'delegation.creation': 'Délégation créée',
    'delegation.revocation': 'Délégation révoquée', 'document.retrait': 'Pièce retirée',
  };

  ngOnInit(): void { this.charger(); }

  charger(page = 1): void {
    this.page = page;
    this.chargement = true;
    this.service.journal({ ...this.filtres, page }).subscribe({
      next: r => { this.lignes = r.results; this.total = r.count; this.chargement = false; },
      error: e => { this.chargement = false; this.toast.error(messageErreur(e)); },
    });
  }

  json(v: any): string { return v ? JSON.stringify(v, null, 2) : '—'; }
}
