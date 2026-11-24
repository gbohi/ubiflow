// src/app/pages/demandes/clotures/clotures.component.ts
//
// Clôtures de mission soumises, à contrôler (rôle défini par le type : comptabilité par défaut).

import { Component, OnInit, inject } from '@angular/core';
import { Router } from '@angular/router';
import { ToastrService } from 'ngx-toastr';
import { DemandesService, iconeType, teinteType } from 'src/app/core/services/demandes/demandes.service';
import { messageErreur } from 'src/app/core/services/organisation/organisation.service';
import { ColonneExport } from 'src/app/shared/export-liste/export-liste.component';

@Component({
  selector: 'app-clotures',
  templateUrl: './clotures.component.html',
})
export class CloturesComponent implements OnInit {
  private readonly service = inject(DemandesService);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastrService);

  readonly icone = iconeType;
  readonly teinte = teinteType;
  lignes: any[] = [];
  chargement = true;
  readonly colonnesExport: ColonneExport[] = [
    { libelle: 'Référence', champ: 'reference' }, { libelle: 'Type', champ: 'type_libelle' },
    { libelle: 'Demandeur', champ: 'demandeur_nom' }, { libelle: 'Objet', champ: 'objet' },
    { libelle: 'Approuvé', champ: 'montant_approuve', format: 'montant', devise: 'devise' },
    { libelle: 'Payé', champ: 'montant_paye', format: 'montant', devise: 'devise' },
    { libelle: 'Soumise le', champ: 'soumise_le', format: 'dateheure' },
  ];

  ngOnInit(): void {
    this.service.cloturesAControler().subscribe({
      next: l => { this.lignes = l; this.chargement = false; },
      error: e => { this.chargement = false; this.toast.error(messageErreur(e)); },
    });
  }

  ouvrir(l: any): void { this.router.navigate(['/demandes', l.id]); }
}
