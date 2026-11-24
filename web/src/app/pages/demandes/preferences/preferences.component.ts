// src/app/pages/demandes/preferences/preferences.component.ts
//
// Préférences de notification : l'application reçoit tout ; l'utilisateur choisit
// l'e-mail et le push par événement (certains événements ne se désactivent pas).

import { Component, OnInit, inject } from '@angular/core';
import { ToastrService } from 'ngx-toastr';
import { DemandesService } from 'src/app/core/services/demandes/demandes.service';
import { messageErreur } from 'src/app/core/services/organisation/organisation.service';

@Component({
  selector: 'app-preferences',
  templateUrl: './preferences.component.html',
})
export class PreferencesComponent implements OnInit {
  private readonly service = inject(DemandesService);
  private readonly toast = inject(ToastrService);

  donnees: any = null;
  enCours = false;

  ngOnInit(): void { this.service.preferencesNotification().subscribe(d => this.donnees = d); }

  enregistrer(): void {
    this.enCours = true;
    this.service.enregistrerPreferences(this.donnees.evenements.filter((e: any) => e.desactivable)
      .map((e: any) => ({ evenement: e.evenement, email: e.email, push: e.push }))).subscribe({
      next: d => { this.donnees = d; this.enCours = false; this.toast.success('Préférences enregistrées.'); },
      error: e => { this.enCours = false; this.toast.error(messageErreur(e)); },
    });
  }
}
